import json
import os
import re
import requests
import datetime


class MemoryManager:
    def __init__(self, max_memories=18, memory_model="deepseek-ai/DeepSeek-V3", base_url="", headers=None):
        self.max_memories = max_memories
        self.memory_model = memory_model
        self.base_url = base_url
        self.headers = headers or {}
        self.memories = []
        self.memory_file = "memories.json"
        self.summary_file = "memory_summary.txt"

        # 加载记忆
        self.load_memories()

    def load_memories(self):
        """从文件加载记忆"""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    self.memories = json.load(f)
                print(f"已加载 {len(self.memories)} 条记忆")
            except Exception as e:
                print(f"加载记忆失败: {str(e)}")
                self.memories = []

        # 加载记忆摘要
        if os.path.exists(self.summary_file):
            try:
                with open(self.summary_file, 'r', encoding='utf-8') as f:
                    self.summary = f.read().strip()
                print(f"已加载记忆摘要")
            except Exception as e:
                print(f"加载记忆摘要失败: {str(e)}")
                self.summary = ""
        else:
            self.summary = ""

    def save_memories(self):
        """保存记忆到文件"""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memories, f, ensure_ascii=False, indent=2)
            print(f"已保存 {len(self.memories)} 条记忆")

            # 保存记忆摘要
            with open(self.summary_file, 'w', encoding='utf-8') as f:
                f.write(self.summary)
            print("已保存记忆摘要")
        except Exception as e:
            print(f"保存记忆失败: {str(e)}")

    def add_memory(self, user_input, ai_response, emotion_type, emotion_delta):
        """添加新的记忆"""
        if not user_input and not ai_response:
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 构建记忆对象
        memory = {
            "timestamp": timestamp,
            "emotion_type": emotion_type,
            "emotion_delta": emotion_delta
        }

        if user_input:
            memory["user_input"] = user_input
        if ai_response:
            memory["ai_response"] = ai_response

        # 添加到记忆列表
        self.memories.append(memory)

        # 确保不超过最大记忆数
        if len(self.memories) > self.max_memories:
            self.memories = self.memories[-self.max_memories:]

        # 生成新的摘要
        self.generate_summary()

    def generate_summary(self):
        """使用AI模型生成记忆摘要"""
        if not self.memories:
            self.summary = "暂无记忆"
            return

        # 准备记忆文本
        memory_text = ""
        for i, memory in enumerate(self.memories, 1):
            entry = f"记忆 #{i} ({memory['timestamp']}):\n"
            if 'user_input' in memory:
                entry += f"用户: {memory['user_input']}\n"
            if 'ai_response' in memory:
                entry += f"AI: {memory['ai_response']}\n"
            entry += f"情感变化: {memory['emotion_type']} ({memory['emotion_delta']})\n\n"
            memory_text += entry

        # 构造提示词
        prompt = (
            "你是一个记忆摘要生成器。请根据以下AI与用户的互动记录，生成简洁的记忆摘要。\n"
            "要求：\n"
            "1. 摘要应简洁，每段记忆用1-2句话描述\n"
            "2. 突出重要事件和情感变化\n"
            "3. 结合情感变化描述（例如：用户夸奖了AI，AI感到开心）\n"
            "4. 按时间顺序从旧到新排列\n"
            "5. 不要包含时间戳\n"
            "6. 总长度不超过500字\n\n"
            f"互动记录：\n{memory_text}"
        )

        # 构造请求
        payload = {
            "model": self.memory_model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的记忆摘要生成助手。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 600
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            if response.status_code != 200:
                print(f"生成记忆摘要失败: {response.status_code} - {response.text}")
                self.summary = "无法生成记忆摘要"
                return

            data = response.json()
            self.summary = data['choices'][0]['message']['content'].strip()
            print("已生成新的记忆摘要")
        except Exception as e:
            print(f"生成记忆摘要异常: {str(e)}")
            self.summary = "无法生成记忆摘要"

    def get_summary(self):
        """获取记忆摘要"""
        return self.summary

    def has_memories(self):
        """检查是否有记忆"""
        return len(self.memories) > 0