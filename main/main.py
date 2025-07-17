import requests
import json
import configparser
import os
import time
import threading
import tkinter as tk
import tkinter.font as tkFont
import queue
import sys
import multiprocessing
from typing import Generator, Dict, Any, Tuple
import random
import base64
import mss
from PIL import Image
import numpy as np
import pygame
import atexit
import datetime
import re

# 导入其他模块
from character_window import run_character_window
from time_display import run_time_display
from music_player import MusicPlayer
from memory_manager import MemoryManager  # 导入记忆管理器

# 初始化pygame mixer
pygame.mixer.init()
atexit.register(pygame.mixer.quit)


class EmotionState:
    """管理AI情感状态"""

    def __init__(self, config: configparser.ConfigParser):
        self.emotion_type = "平静"  # 初始情感状态
        self.emotion_intensity = 0  # 初始情感强度
        self.decay_rate = config.getfloat('Emotion', 'emotion_decay', fallback=1.0)
        self.max_intensity = config.getfloat('Emotion', 'max_intensity', fallback=250.0)
        self.impact_factor = config.getfloat('Emotion', 'emotion_impact_factor', fallback=1.0)
        self.lock = threading.Lock()
        self.running = True

        # 记录上次情感类型，用于检测变化
        self.previous_emotion = "平静"

        # 启动情感衰减线程
        self.decay_thread = threading.Thread(target=self.emotion_decay_loop, daemon=True)
        self.decay_thread.start()

    def update_emotion(self, delta: float):
        """更新情感状态（受上限约束）"""
        with self.lock:
            # 记录变化前的情绪
            prev_type = self.emotion_type

            # 应用情绪影响系数
            adjusted_delta = delta * self.impact_factor

            # 更新情感强度（确保在0和上限之间）
            self.emotion_intensity = max(0, min(self.max_intensity, self.emotion_intensity + adjusted_delta))

            # 检查情感类型是否变化
            emotion_changed = prev_type != self.emotion_type
            return emotion_changed

    def set_emotion(self, emotion_type: str, intensity: float):
        """设置情感类型和强度（应用影响系数）"""
        with self.lock:
            # 记录变化前的情绪
            prev_type = self.emotion_type

            # 应用情绪影响系数
            adjusted_intensity = intensity * self.impact_factor

            self.emotion_type = emotion_type
            self.emotion_intensity = max(0, min(self.max_intensity, adjusted_intensity))

            # 检查情感类型是否变化
            emotion_changed = prev_type != emotion_type
            return emotion_changed

    def emotion_decay_loop(self):
        """情感衰减循环"""
        while self.running:
            time.sleep(1)  # 每秒衰减一次
            with self.lock:
                # 记录变化前的情绪
                prev_type = self.emotion_type

                # 应用情感衰减
                self.emotion_intensity = max(0, self.emotion_intensity - self.decay_rate)

                # 如果强度为0，重置情感类型为平静
                if self.emotion_intensity == 0:
                    self.emotion_type = "平静"

                # 检查情感类型是否变化
                emotion_changed = prev_type != self.emotion_type
                if emotion_changed and hasattr(self, 'emotion_change_callback'):
                    self.emotion_change_callback(self.emotion_type)

    def get_state(self) -> Tuple[str, float]:
        """获取当前情感状态"""
        with self.lock:
            return self.emotion_type, self.emotion_intensity

    def stop(self):
        """停止情感管理线程"""
        self.running = False
        if self.decay_thread.is_alive():
            self.decay_thread.join(timeout=0.5)


class SiliconFlowClient:
    def __init__(self, config_path: str = 'config.ini'):
        # 加载配置
        self.parser = self._load_config(config_path)

        # API配置
        self.headers = {
            "Authorization": f"Bearer {self.parser.get('API', 'api_key')}",
            "Content-Type": "application/json"
        }
        self.base_url = self.parser.get('API', 'base_url')
        self.model = self.parser.get('API', 'model')
        self.stream = self.parser.getboolean('Settings', 'stream')
        self.ai_name = self.parser.get('UI', 'ai_name', fallback='AI')  # 可自定义的AI名称

        # 情感分析配置
        self.emotion_model = self.parser.get('Emotion', 'emotion_model')
        self.ai_personality = self.parser.get('Personality', 'ai_personality', fallback='一个AI助手')

        # 视觉模型配置
        self.vision_model = self.parser.get('Visual', 'vision_model', fallback='deepseek-ai/deepseek-vl2')
        self.analysis_model = self.parser.get('Visual', 'analysis_model', fallback='deepseek-ai/DeepSeek-V3')

        # 记忆模型配置
        self.memory_model = self.parser.get('Memory', 'memory_model', fallback='deepseek-ai/DeepSeek-V3')

        # 初始化记忆管理器
        self.memory_manager = MemoryManager(
            self.parser.getint('Memory', 'max_memories', fallback=18),
            self.memory_model,
            self.base_url,
            self.headers
        )

        # 初始化情感状态管理器
        self.emotion_state = EmotionState(self.parser)

        # 情感显示控制
        self.emotion_display_active = False
        self.emotion_display_thread = None
        self.last_emotion_line = ""

        # 语言设置处理
        self.language = self.parser.get('Settings', 'language', fallback='Chinese').strip().lower()
        # 根据语言选择系统提示
        if self.language == 'japanese':
            self.system_prompt = self.parser.get('Personality', 'system_prompt_2')
        else:
            self.system_prompt = self.parser.get('Personality', 'system_prompt')

        # 设置情感变化回调
        self.emotion_state.emotion_change_callback = self.on_emotion_changed

        # 当前回复文本
        self.current_response = ""
        self.has_jumped = False  # 用于标记是否已经跳动过

        # 视觉分析相关
        self.last_input_time = time.time()  # 记录最后输入时间
        self.visual_analysis_active = True  # 视觉分析线程运行标志
        self.user_interrupted = False  # 用户是否中断视觉分析
        self.visual_thread = None  # 视觉分析线程
        self.screenshot_dir = "screenshots"  # 截图保存目录
        os.makedirs(self.screenshot_dir, exist_ok=True)  # 创建截图目录

        # 启动视觉分析线程
        self.start_visual_analysis_thread()

    def start_visual_analysis_thread(self):
        """启动视觉分析线程"""
        self.visual_thread = threading.Thread(target=self.visual_analysis_loop, daemon=True)
        self.visual_thread.start()

    def visual_analysis_loop(self):
        """视觉分析循环，等待随机时间后执行分析"""
        while self.visual_analysis_active:
            # 随机等待50-200秒
            wait_time = random.randint(50, 200)
            print(f"\033[33m视觉分析将在 {wait_time} 秒后启动...\033[0m")
            time.sleep(wait_time)

            # 检查是否有新输入
            if time.time() - self.last_input_time < 5:
                print("\033[33m用户有新输入，跳过本次视觉分析\033[0m")
                continue

            # 执行视觉分析
            self.perform_visual_analysis()

    def capture_screenshot(self):
        """使用mss捕获屏幕截图"""
        with mss.mss() as sct:
            # 获取主显示器
            monitor = sct.monitors[1]
            # 截图
            sct_img = sct.grab(monitor)
            # 转换为PIL图像
            img = Image.frombytes('RGB', sct_img.size, sct_img.rgb)
            # 保存为临时文件
            timestamp = int(time.time())
            img_path = os.path.join(self.screenshot_dir, f"screenshot_{timestamp}.png")
            img.save(img_path)
            return img_path

    def encode_image(self, image_path):
        """将图像编码为base64"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def analyze_image(self, image_path):
        """使用视觉模型分析图像"""
        base64_image = self.encode_image(image_path)

        # 改进的视觉分析提示词，关注与用户相关的上下文
        vision_prompt = (
            "请详细描述当前屏幕内容，特别注意以下方面：\n"
            "1. 用户正在使用的应用程序或浏览的网页内容\n"
            "2. 屏幕上可见的文字信息\n"
            "3. 与用户当前活动相关的视觉元素\n"
            "4. 可能暗示用户需求或兴趣的内容\n"
            "5. 时间相关的信息（如时钟、日历）"
        )

        # 构造请求
        payload = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": vision_prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 1000
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=120
            )
            if response.status_code != 200:
                print(f"视觉分析请求失败: {response.status_code} - {response.text}")
                return None
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            print(f"视觉分析异常: {str(e)}")
            return None

    def generate_context_prompt(self, image_description):
        """根据视觉分析结果生成上下文提示"""
        emotion_type, emotion_intensity = self.emotion_state.get_state()

        # 改进的分析提示词，增强与屏幕内容的关联
        system_prompt = (
            f"你正在扮演{self.ai_name}（{self.ai_personality}）。当前情感状态: {emotion_type}，强度: {emotion_intensity:.1f}。\n"
            "请根据以下屏幕内容分析，思考如何自然地与用户互动：\n\n"
            "### 屏幕内容分析\n"
            f"{image_description}\n\n"
            "### 互动要求\n"
            "1. 回复必须基于屏幕内容，但不要直接描述屏幕\n"
            "2. 结合当前情感状态，使用符合人格的语气\n"
            "3. 内容应简短（1-2句话），自然引发对话\n"
            "4. 避免直接提问，而是分享观察或感受\n"
            "5. 如果屏幕内容与用户工作相关，提供鼓励或帮助\n\n"
            "请输出AI应该对用户说的话："
        )

        # 构造请求
        payload = {
            "model": self.analysis_model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                }
            ],
            "max_tokens": 300
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            if response.status_code != 200:
                print(f"上下文分析请求失败: {response.status_code} - {response.text}")
                return None
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            print(f"上下文分析异常: {str(e)}")
            return None

    def perform_visual_analysis(self):
        """执行视觉分析流程"""
        # 检查是否有新输入
        if time.time() - self.last_input_time < 5:
            print("\033[33m用户有新输入，取消视觉分析\033[0m")
            return

        print("\033[33m检测到用户长时间未输入，开始视觉分析...\033[0m")

        # 1. 截图
        screenshot_path = self.capture_screenshot()
        print(f"截图已保存: {screenshot_path}")

        # 2. 视觉模型分析
        image_description = self.analyze_image(screenshot_path)
        if not image_description:
            print("视觉分析失败，跳过后续步骤")
            os.remove(screenshot_path)
            return
        print(f"视觉分析结果: {image_description}")

        # 3. 生成上下文提示
        context_prompt = self.generate_context_prompt(image_description)
        if not context_prompt:
            print("上下文提示生成失败")
            os.remove(screenshot_path)
            return
        print(f"生成的上下文提示: {context_prompt}")

        # 4. 检查用户是否在分析期间输入（打断）
        if time.time() - self.last_input_time < 5:
            print("用户已输入，取消自动回复")
            os.remove(screenshot_path)
            return

        # 5. 使用上下文提示调用主模型生成回复
        # 构造请求（非流式）
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": context_prompt
                }
            ],
            "stream": False
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            if response.status_code != 200:
                print(f"自动回复请求失败: {response.status_code} - {response.text}")
                os.remove(screenshot_path)
                return

            data = response.json()
            ai_response = data['choices'][0]['message']['content']

            # 输出回复
            print(f"\033[34m{self.ai_name}（自动回复）: {ai_response}\033[0m")

            # 发送气泡更新
            self.send_bubble_update(ai_response, is_final=True)

            # 发送跳动信号给立绘窗口
            if hasattr(self, 'bubble_queue'):
                try:
                    self.bubble_queue.put({'jump': True})
                except Exception as e:
                    print(f"发送跳动信号失败: {str(e)}")

        except Exception as e:
            print(f"自动回复异常: {str(e)}")
        finally:
            # 删除截图
            os.remove(screenshot_path)

    def _load_config(self, config_path: str) -> configparser.ConfigParser:
        """加载配置文件"""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"配置文件 {config_path} 不存在")

        parser = configparser.ConfigParser()
        parser.read(config_path, encoding='utf-8')
        return parser

    def analyze_emotion(self, user_input: str) -> Tuple[str, float]:
        """使用DeepSeek-R1分析用户输入的情感影响"""
        # 获取当前情感状态
        current_emotion, current_intensity = self.emotion_state.get_state()

        # 获取记忆摘要
        memory_summary = self.memory_manager.get_summary()

        # 构造情感分析请求
        system_prompt = (
            f"你是一个情感分析助手。请分析用户输入对AI助手的情感影响。\n"
            f"AI助手的人设：{self.ai_personality}\n"
            f"当前情感状态：{current_emotion}，强度：{current_intensity:.1f}\n"
            f"以下是之前的互动记忆摘要：\n{memory_summary}\n\n"
        )

        if current_emotion == "平静":
            system_prompt += (
                "请从以下情感中选择一个最合适的：平静, 开心, 生气, 悲伤, 厌恶, 尴尬, 期待, 恐惧, 惊讶\n"
                "然后返回一个-100到100之间的数值表示情感强度变化（正值增强，负值减弱）。\n"
                "输出格式：`情感类型 数值`（例如：`开心 50`）"
            )
        else:
            system_prompt += (
                "请返回一个-100到100之间的数值表示情感强度变化（正值增强当前情感，负值减弱当前情感）。\n"
                "只返回一个数字，不要包含其他任何内容。"
            )

        payload = {
            "model": self.emotion_model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ]
        }

        try:
            # 发送情感分析请求
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                print(f"情感分析失败: {response.status_code} - {response.text}")
                return current_emotion, 0

            # 解析响应
            data = response.json()
            response_content = data['choices'][0]['message']['content'].strip()

            if current_emotion == "平静":
                # 解析情感类型和变化值
                parts = response_content.split()
                if len(parts) >= 2:
                    new_emotion = parts[0]
                    try:
                        delta = float(parts[1])
                        # 确保值在合法范围内
                        delta = max(-100, min(100, delta))
                        return new_emotion, delta
                    except ValueError:
                        pass
                # 如果解析失败，返回默认值
                return current_emotion, 0
            else:
                # 非平静状态，只返回变化值
                try:
                    delta = float(response_content)
                    # 确保值在合法范围内
                    delta = max(-100, min(100, delta))
                    return current_emotion, delta
                except ValueError:
                    return current_emotion, 0
        except Exception as e:
            print(f"情感分析错误: {str(e)}")
            return current_emotion, 0

    def _generate_payload(self, prompt: str) -> Dict[str, Any]:
        """构造请求负载，包含情感状态和记忆"""
        emotion_type, emotion_intensity = self.emotion_state.get_state()

        # 获取记忆摘要
        memory_summary = self.memory_manager.get_summary()

        # 在系统提示中加入情感状态和记忆
        enhanced_prompt = (
            f"{self.system_prompt}\n"
            f"[当前情感状态: {emotion_type}，强度: {emotion_intensity:.1f}。"
            f"请根据此情感状态调整回答的语气和风格。]\n"
            f"以下是之前的互动记忆摘要：\n{memory_summary}"
        )

        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": enhanced_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": self.stream
        }

    def get_response(self, prompt: str) -> Generator[str, None, None]:
        """获取API响应（流式/非流式）"""
        payload = self._generate_payload(prompt)
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=self.headers,
            json=payload,
            stream=self.stream,
            timeout=60
        )

        if response.status_code != 200:
            raise Exception(f"API请求失败: {response.status_code} - {response.text}")

        if self.stream:
            # 流式输出处理
            is_first_chunk = True
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        json_data = decoded_line[6:]
                        try:
                            chunk = json.loads(json_data)
                            if chunk.get("object") == "chat.completion.chunk":
                                if 'content' in chunk['choices'][0]['delta']:
                                    content = chunk['choices'][0]['delta']['content']

                                    # 如果是第一个内容块，发送跳动信号
                                    if is_first_chunk:
                                        is_first_chunk = False
                                        if not self.has_jumped:
                                            self.has_jumped = True
                                            try:
                                                self.bubble_queue.put({'jump': True})
                                            except Exception as e:
                                                print(f"发送跳动信号失败: {str(e)}")

                                    yield content
                        except json.JSONDecodeError:
                            # 忽略解析错误（如[DONE]）
                            pass
        else:
            # 非流式输出处理
            data = response.json()
            content = data['choices'][0]['message']['content']

            # 发送跳动信号
            if not self.has_jumped:
                self.has_jumped = True
                try:
                    self.bubble_queue.put({'jump': True})
                except Exception as e:
                    print(f"发送跳动信号失败: {str(e)}")

            yield content

    def process_user_input(self, user_input: str):
        """处理用户输入，包括情感分析并更新状态（应用影响系数）"""
        # 更新最后输入时间
        self.last_input_time = time.time()

        # 重置跳动标志
        self.has_jumped = False

        # 分析用户输入的情感影响
        new_emotion, emotion_delta = self.analyze_emotion(user_input)

        # 获取当前情感状态
        current_emotion, current_intensity = self.emotion_state.get_state()

        # 更新情感状态（应用影响系数）
        if current_emotion == "平静":
            # 平静状态下可以改变情感类型
            emotion_changed = self.emotion_state.set_emotion(new_emotion, emotion_delta)
        else:
            # 非平静状态下只更新情感强度
            emotion_changed = self.emotion_state.update_emotion(emotion_delta)

        return emotion_changed

    def start_emotion_display(self):
        """开始持续显示情感状态（复写同一行）"""
        if self.emotion_display_active:
            return

        self.emotion_display_active = True
        self.emotion_display_thread = threading.Thread(target=self._emotion_display_loop, daemon=True)
        self.emotion_display_thread.start()

    def stop_emotion_display(self):
        """停止显示情感状态"""
        self.emotion_display_active = False
        if self.emotion_display_thread and self.emotion_display_thread.is_alive():
            self.emotion_display_thread.join(timeout=0.5)
            # 清除最后一行
            print("\r" + " " * len(self.last_emotion_line) + "\r", end="", flush=True)

    def _emotion_display_loop(self):
        """持续显示情感状态的循环（复写同一行）"""
        # 先打印一个空行作为情感状态行
        print()

        while self.emotion_display_active:
            emotion_type, emotion_intensity = self.emotion_state.get_state()
            # 深蓝色显示情感状态
            emotion_str = f"\033[34m{emotion_type} {emotion_intensity:.1f}\033[0m"
            self.last_emotion_line = emotion_str

            # 使用回车符\r回到行首并覆盖内容
            print(f"\r{emotion_str}", end="", flush=True)
            time.sleep(1)

    def on_emotion_changed(self, emotion):
        """情感变化回调函数"""
        # 通知立绘进程情感变化
        if hasattr(self, 'emotion_queue'):
            try:
                self.emotion_queue.put(emotion)
                print(f"发送情感更新: {emotion}")
            except Exception as e:
                print(f"发送情感更新失败: {str(e)}")

    def send_bubble_update(self, text, is_final=False):
        """发送气泡更新"""
        if hasattr(self, 'bubble_queue'):
            try:
                self.bubble_queue.put({
                    'text': text,
                    'final': is_final
                })
            except Exception as e:
                print(f"发送气泡更新失败: {str(e)}")

    def shutdown(self):
        """关闭客户端资源"""
        self.emotion_state.stop()
        self.visual_analysis_active = False
        self.memory_manager.save_memories()  # 保存记忆
        print("情感状态管理器和视觉分析线程已关闭")

    def generate_welcome_message(self):
        """根据记忆生成欢迎消息"""
        if not self.memory_manager.has_memories():
            return None

        # 构造请求
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        f"你是一个AI助手，名字是{self.ai_name}。"
                        "请根据之前的互动记忆，用一句简短的话（疑问句或感叹句）向用户表示欢迎。"
                        "不要提及记忆本身，只需自然地表达欢迎之情。"
                        "输出格式：只需输出欢迎语本身，不要包含其他内容。"
                    )
                },
                {
                    "role": "user",
                    "content": f"记忆摘要：\n{self.memory_manager.get_summary()}"
                }
            ],
            "max_tokens": 50
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            if response.status_code != 200:
                print(f"生成欢迎语失败: {response.status_code} - {response.text}")
                return None

            data = response.json()
            return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"生成欢迎语异常: {str(e)}")
            return None


class InputWindow(tk.Tk):
    """用户输入窗口（无边框）"""

    def __init__(self, message_queue, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_queue = message_queue
        self.time_queue = multiprocessing.Queue()  # 时间显示队列

        # 设置无边框窗口
        self.overrideredirect(True)
        self.attributes("-topmost", True)  # 保持置顶
        self.geometry("400x100+100+100")  # 调整高度，去掉音乐播放器

        # 创建输入框和发送按钮
        self.frame = tk.Frame(self, bg='#f0f0f0', padx=5, pady=5)
        self.frame.pack(fill=tk.BOTH, expand=True)

        # 使用grid布局，使输入框和按钮在同一行，并且输入框自适应
        self.frame.columnconfigure(0, weight=1)  # 输入框列权重为1
        self.frame.columnconfigure(1, weight=0)  # 按钮列不扩展
        self.frame.columnconfigure(2, weight=0)  # 关闭按钮列不扩展

        self.user_input = tk.Entry(self.frame)
        self.user_input.grid(row=0, column=0, sticky="ew", padx=(0, 5), ipady=5)  # 增加垂直内边距
        self.user_input.bind("<Return>", self.on_enter_pressed)
        self.user_input.focus_set()

        # 发送按钮 - 设置固定宽度
        self.send_button = tk.Button(self.frame, text="发送", command=self.send_message, width=5)
        self.send_button.grid(row=0, column=1, padx=(0, 5), sticky="ew")

        # 退出按钮 - 设置固定宽度
        self.close_button = tk.Button(self.frame, text="X", command=self.close_window, width=2)
        self.close_button.grid(row=0, column=2, sticky="ew")

        # 添加拖动功能
        self.bind('<Button-1>', self.start_move)
        self.bind('<ButtonRelease-1>', self.stop_move)
        self.bind('<B1-Motion>', self.do_move)

        # 协议处理
        self.protocol("WM_DELETE_WINDOW", self.close_window)

        # 初始化移动变量
        self.x = None
        self.y = None

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def stop_move(self, event):
        self.x = None
        self.y = None

    def do_move(self, event):
        if self.x is not None and self.y is not None:
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.winfo_x() + deltax
            y = self.winfo_y() + deltay
            self.geometry(f"+{x}+{y}")

    def on_enter_pressed(self, event):
        self.send_message()

    def send_message(self):
        user_message = self.user_input.get().strip()
        if user_message:
            self.message_queue.put(user_message)
            self.user_input.delete(0, tk.END)

    def close_window(self):
        self.message_queue.put("exit")
        self.destroy()
        # 确保完全退出
        os._exit(0)

    def show_time(self):
        """显示时间窗口"""
        self.time_queue.put("show")


def run_ai_client(message_queue, emotion_queue, bubble_queue):
    client = SiliconFlowClient()
    client.emotion_queue = emotion_queue  # 设置情感队列
    client.bubble_queue = bubble_queue  # 设置气泡队列

    # 显示命令行标题
    print("\033[90m" + "=" * 50)  # 深灰色
    print(f"{client.ai_name}聊天系统 - 命令行输出")
    print(f"主模型: {client.model}")
    print(f"情感模型: {client.emotion_model}")
    print(f"视觉模型: {client.vision_model}")
    print(f"分析模型: {client.analysis_model}")
    print(f"记忆模型: {client.memory_model}")
    print(f"当前模式: {'流式' if client.stream else '非流式'}")
    print(f"情感衰减率: {client.emotion_state.decay_rate}/秒")
    print(f"情感强度上限: {client.emotion_state.max_intensity}")
    print(f"情绪影响系数: {client.emotion_state.impact_factor}")
    print(f"最大记忆条数: {client.memory_manager.max_memories}")

    # 显示当前语言模式
    lang_display = "中文" if client.language == "chinese" else "日文"
    print(f"语言模式: {lang_display}")

    print(f"AI人格: {client.system_prompt}")
    print("=" * 50)
    print("\033[32m" + f"用户输入在独立窗口中，{client.ai_name}回复显示在此处")  # 绿色
    print("关闭输入窗口退出")
    print("\033[0m" + "=" * 50)  # 重置颜色

    # 如果有记忆，生成欢迎语
    if client.memory_manager.has_memories():
        welcome_message = client.generate_welcome_message()
        if welcome_message:
            print(f"\033[34m{client.ai_name}: {welcome_message}\033[0m")
            client.send_bubble_update(welcome_message, is_final=True)

    # 主循环
    try:
        while True:
            # 从队列获取用户输入（阻塞式等待）
            user_input = message_queue.get()

            if user_input.lower() in ['exit', 'quit']:
                break

            # 处理用户输入
            emotion_changed = client.process_user_input(user_input)

            # 如果情感变化，发送通知
            if emotion_changed:
                emotion_type, _ = client.emotion_state.get_state()
                client.on_emotion_changed(emotion_type)

            # 停止当前的情感状态显示（如果有）
            client.stop_emotion_display()

            # 显示AI回复（白色）
            print(f"{client.ai_name}: ", end="", flush=True)

            # 重置当前回复
            client.current_response = ""

            if client.stream:
                # 流式输出
                full_response = []
                for chunk in client.get_response(user_input):
                    print(chunk, end="", flush=True)
                    full_response.append(chunk)

                    # 更新气泡
                    client.current_response += chunk
                    client.send_bubble_update(client.current_response)

                print()  # 换行
                ai_response = "".join(full_response)

                # 添加记忆
                client.memory_manager.add_memory(
                    user_input=user_input,
                    ai_response=ai_response,
                    emotion_type=client.emotion_state.emotion_type,
                    emotion_delta=client.emotion_state.emotion_intensity
                )

                # 发送最终气泡更新
                client.send_bubble_update(client.current_response, is_final=True)
            else:
                # 非流式输出
                ai_response = next(client.get_response(user_input))
                print(ai_response)

                # 添加记忆
                client.memory_manager.add_memory(
                    user_input=user_input,
                    ai_response=ai_response,
                    emotion_type=client.emotion_state.emotion_type,
                    emotion_delta=client.emotion_state.emotion_intensity
                )

                # 发送气泡更新
                client.send_bubble_update(ai_response, is_final=True)

            # 在AI回复后新起一行显示情感状态
            client.start_emotion_display()

    except Exception as e:
        # 深灰色显示错误信息
        print(f"\033[90m\n错误: {str(e)}\033[0m")
    finally:
        client.shutdown()
        print("\033[90m程序已退出\033[0m")


if __name__ == "__main__":
    # 创建消息队列
    message_queue = queue.Queue()

    # 创建情感更新队列 (进程间通信)
    emotion_queue = multiprocessing.Queue()

    # 创建气泡更新队列 (进程间通信)
    bubble_queue = multiprocessing.Queue()

    # 启动立绘窗口进程
    character_process = multiprocessing.Process(
        target=run_character_window,
        args=(emotion_queue, bubble_queue),
        daemon=True
    )
    character_process.start()

    # 启动时间显示进程
    time_process = multiprocessing.Process(
        target=run_time_display,
        daemon=True
    )
    time_process.start()

    # 启动AI处理线程
    ai_thread = threading.Thread(
        target=run_ai_client,
        args=(message_queue, emotion_queue, bubble_queue),
        daemon=True
    )
    ai_thread.start()

    # 在主线程运行输入窗口
    input_window = InputWindow(message_queue)
    input_window.mainloop()

    # 确保所有线程退出
    character_process.terminate()
    time_process.terminate()
    sys.exit(0)