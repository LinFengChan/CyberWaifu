import os
import random
import tkinter as tk
from tkinter import font as tkFont
from PIL import Image, ImageTk, ImageDraw, ImageFont
import configparser
import multiprocessing
import queue
import time
import math
import subprocess
import sys
from time_display import run_time_display
from music_player import MusicPlayer

class Bubble:
    def __init__(self, canvas, config):
        self.canvas = canvas
        self.config = config
        self.text = ""
        self.visible = False
        self.bubble_id = None
        self.text_ids = []  # 存储所有文本ID的列表
        self.position = (0, 0)
        self.font = tkFont.Font(
            family=self.config.get('UI', 'bubble_font', fallback='Microsoft YaHei'),
            size=self.config.getint('UI', 'bubble_font_size', fallback=12)
        )
        self.text_color = self.config.get('UI', 'bubble_text_color', fallback='#333333')
        self.bg_color = self.config.get('UI', 'bubble_bg_color', fallback='rgba(255, 255, 255, 200)')
        self.corner_radius = self.config.getint('UI', 'bubble_corner_radius', fallback=10)
        self.max_width = 230  # 固定为230像素，超过换行
        self.line_height = self.font.metrics("linespace")  # 获取行高
        self.ascent = self.font.metrics("ascent")  # 获取字体基线以上的高度

        # 解析背景颜色
        if self.bg_color.startswith('rgba'):
            parts = self.bg_color[5:-1].split(',')
            self.bg_r = int(parts[0].strip())
            self.bg_g = int(parts[1].strip())
            self.bg_b = int(parts[2].strip())
            self.bg_alpha = int(parts[3].strip())
        else:
            # 默认半透明白色
            self.bg_r, self.bg_g, self.bg_b = 255, 255, 255
            self.bg_alpha = 200

        # 初始化跳动指示器相关属性
        self.jump_indicator_id = None
        self.jump_timer = None

    def show(self, text, position=None):
        # 过滤空文本
        if not text.strip():
            return

        self.text = text
        self.visible = True

        if position:
            self.position = position
        else:
            # 根据窗口位置决定气泡位置
            win_x = self.canvas.winfo_rootx()
            win_width = self.canvas.winfo_width()
            screen_width = self.canvas.winfo_screenwidth()

            # 如果窗口在屏幕右半边，气泡在左上部
            if win_x > screen_width // 2:
                bubble_x = win_width * 0.2
            else:  # 否则在右上部
                bubble_x = win_width * 0.8

            self.position = (
                bubble_x,
                random.randint(20, int(self.canvas.winfo_height() * 0.3))
            )

        self.update_bubble()

    def hide(self):
        # 删除气泡和所有文本
        if self.bubble_id:
            self.canvas.delete(self.bubble_id)
            self.bubble_id = None

        # 删除所有文本项
        for text_id in self.text_ids:
            self.canvas.delete(text_id)
        self.text_ids = []

        self.visible = False

    def update_text(self, new_text):
        # 过滤空文本
        if not new_text.strip():
            return

        self.text = new_text
        if self.visible:
            self.update_bubble()

    def wrap_text(self):
        """将文本换行以适应最大宽度"""
        if not self.text.strip():
            return []

        lines = []
        current_line = ""

        # 按字符换行，确保精确控制
        for char in self.text:
            test_line = current_line + char
            # 测量当前行宽度
            line_width = self.font.measure(test_line)

            # 如果超过最大宽度或者遇到换行符
            if line_width > self.max_width or char == '\n':
                lines.append(current_line)
                current_line = char if char != '\n' else ""
            else:
                current_line = test_line

        # 添加最后一行
        if current_line:
            lines.append(current_line)

        return lines

    def update_bubble(self):
        # 先删除旧的气泡和文本
        if self.bubble_id:
            self.canvas.delete(self.bubble_id)
            self.bubble_id = None

        # 删除所有文本项
        for text_id in self.text_ids:
            self.canvas.delete(text_id)
        self.text_ids = []

        # 计算文本尺寸 - 确保文本不为空
        text_lines = self.wrap_text()
        if not text_lines:  # 如果没有文本行，则隐藏气泡
            self.hide()
            return

        # 计算最大行宽和总高度
        max_line_width = 0
        for line in text_lines:
            line_width = self.font.measure(line)
            if line_width > max_line_width:
                max_line_width = line_width

        total_height = len(text_lines) * self.line_height

        # 计算气泡尺寸
        padding = 10
        bubble_width = min(max_line_width + 2 * padding, self.max_width + 2 * padding)
        bubble_height = total_height + 2 * padding

        # 确保气泡不会超出立绘边界
        x, y = self.position
        win_width = self.canvas.winfo_width()
        win_height = self.canvas.winfo_height()

        # 调整气泡位置使其完全在立绘内
        if x + bubble_width / 2 > win_width:
            x = win_width - bubble_width / 2 - 10
        if x - bubble_width / 2 < 0:
            x = bubble_width / 2 + 10
        if y + bubble_height / 2 > win_height:
            y = win_height - bubble_height / 2 - 10
        if y - bubble_height / 2 < 0:
            y = bubble_height / 2 + 10

        self.position = (x, y)

        # 创建一个半透明的图像作为气泡背景
        bubble_img = Image.new('RGBA', (int(bubble_width), int(bubble_height)),
                               (self.bg_r, self.bg_g, self.bg_b, self.bg_alpha))
        draw = ImageDraw.Draw(bubble_img)

        # 绘制圆角矩形
        draw.rounded_rectangle([(0, 0), (bubble_width, bubble_height)],
                               radius=self.corner_radius,
                               fill=(self.bg_r, self.bg_g, self.bg_b, self.bg_alpha))

        # 转换为PhotoImage
        bubble_photo = ImageTk.PhotoImage(bubble_img)

        # 在画布上创建气泡
        self.bubble_id = self.canvas.create_image(
            x, y,
            image=bubble_photo,
            anchor="center"
        )
        self.canvas.bubble_photo = bubble_photo  # 保持引用

        # 添加文本 - 精确计算位置
        # 计算文本起始Y位置（垂直居中）
        start_y = y - total_height / 2 + self.ascent

        for i, line in enumerate(text_lines):
            # 计算文本行宽度
            line_width = self.font.measure(line)

            # 创建文本（水平居中）
            text_id = self.canvas.create_text(
                x,
                start_y + i * self.line_height,
                text=line,
                fill=self.text_color,
                font=self.font,
                anchor="center",
                tags="bubble_text"
            )
            self.text_ids.append(text_id)

    def show_jump_indicator(self, position=None):
        """显示跳动指示器"""
        # 先隐藏旧的指示器
        self.hide_jump_indicator()

        if position:
            self.position = position

        # 创建跳动指示器（小三角形）
        size = 10
        x, y = self.position
        # 在气泡上方显示
        indicator_y = y - 30

        # 创建指示器图像
        indicator_img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(indicator_img)
        draw.polygon([(0, size), (size, size), (size // 2, 0)], fill=(255, 100, 100, 200))

        # 转换为PhotoImage
        indicator_photo = ImageTk.PhotoImage(indicator_img)

        # 在画布上创建指示器
        self.jump_indicator_id = self.canvas.create_image(
            x, indicator_y,
            image=indicator_photo,
            anchor="center"
        )
        self.canvas.jump_indicator_photo = indicator_photo  # 保持引用

        # 设置2秒后隐藏
        if self.jump_timer:
            self.canvas.after_cancel(self.jump_timer)
        self.jump_timer = self.canvas.after(2000, self.hide_jump_indicator)

    def hide_jump_indicator(self):
        """隐藏跳动指示器"""
        if self.jump_indicator_id:
            self.canvas.delete(self.jump_indicator_id)
            self.jump_indicator_id = None
        if self.jump_timer:
            self.canvas.after_cancel(self.jump_timer)
            self.jump_timer = None


class CharacterWindow:
    def __init__(self, emotion_queue, bubble_queue, config_path='config.ini'):
        # 加载配置
        self.parser = configparser.ConfigParser()
        self.parser.read(config_path, encoding='utf-8')

        # 获取缩放比例 (1-100)
        self.scale = self.parser.getfloat('UI', 'scale', fallback=50.0) / 100.0

        # 存储队列
        self.emotion_queue = emotion_queue
        self.bubble_queue = bubble_queue

        # 初始化窗口
        self.window = tk.Tk()
        self.window.title("Character Window")

        # 设置无边框和透明背景
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)  # 保持置顶

        # 兼容透明设置
        self.transparent_color = "#abcdef"
        try:
            self.window.attributes("-transparent", True)
        except tk.TclError:
            self.window.attributes("-transparentcolor", self.transparent_color)
            self.window.configure(bg=self.transparent_color)

        # 初始位置（屏幕右上角）
        screen_width = self.window.winfo_screenwidth()
        self.window.geometry(f"+{screen_width - 400}+50")

        # 创建画布
        try:
            self.canvas = tk.Canvas(self.window, bg='systemTransparent', highlightthickness=0)
        except tk.TclError:
            self.canvas = tk.Canvas(self.window, bg=self.transparent_color, highlightthickness=0)

        self.canvas.pack(fill=tk.BOTH, expand=True)

        # 初始情感状态
        self.current_emotion = "平静"
        self.photo = None
        self.images_cache = {}  # 图片缓存

        # 加载初始立绘
        self.update_character_image("平静")

        # 添加拖动功能
        self.canvas.bind('<Button-1>', self.start_move)
        self.canvas.bind('<ButtonRelease-1>', self.stop_move)
        self.canvas.bind('<B1-Motion>', self.do_move)

        # 绑定双击事件
        self.canvas.bind('<Double-Button-1>', self.on_double_click)

        # 添加右键菜单
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(label="显示/隐藏播放器", command=self.toggle_music_player)
        self.context_menu.add_command(label="刷新歌曲", command=self.refresh_music)
        self.context_menu.add_command(label="打开音乐路径", command=self.open_music_dir)
        self.context_menu.add_separator()
        self.context_menu.add_checkbutton(label="置顶", command=self.toggle_topmost)

        # 添加关闭按钮
        self.close_button = tk.Button(
            self.window,
            text="X",
            command=self.close_window,
            bg="red",
            fg="white",
            width=2,
            relief="flat"
        )
        self.close_button.place(x=0, y=0, anchor="nw")

        # 初始化移动变量
        self.x = None
        self.y = None

        # 初始化气泡
        self.bubble = Bubble(self.canvas, self.parser)
        self.bubble_timer = None

        # 创建播放器（初始隐藏）
        self.music_player = MusicPlayer(self.window)
        self.music_player.place_forget()  # 初始隐藏
        self.player_visible = False

        # 启动队列检查
        self.check_queues()

        # 启动主循环
        self.window.mainloop()

    def show_context_menu(self, event):
        """显示右键菜单"""
        self.context_menu.post(event.x_root, event.y_root)

    def toggle_music_player(self):
        """切换播放器的显示和隐藏"""
        if self.player_visible:
            self.music_player.place_forget()
            self.player_visible = False
        else:
            # 在立绘下方显示播放器
            self.music_player.place(relx=0.5, rely=1.0, anchor="s", y=10)
            self.player_visible = True

    def refresh_music(self):
        """刷新歌曲列表"""
        self.music_player.load_music()

    def open_music_dir(self):
        """打开音乐目录"""
        music_dir = "music"
        if not os.path.exists(music_dir):
            os.makedirs(music_dir)
        # 根据操作系统打开文件夹
        if sys.platform == "win32":
            os.startfile(music_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", music_dir])
        else:
            subprocess.Popen(["xdg-open", music_dir])

    def toggle_topmost(self):
        """切换置顶状态"""
        current_state = self.window.attributes("-topmost")
        self.window.attributes("-topmost", not current_state)

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
            x = self.window.winfo_x() + deltax
            y = self.window.winfo_y() + deltay
            self.window.geometry(f"+{x}+{y}")

    def on_double_click(self, event):
        """双击立绘时触发"""
        # 通知主进程显示时间
        try:
            # 创建一个临时队列用于通信
            time_queue = multiprocessing.Queue()
            time_process = multiprocessing.Process(
                target=run_time_display,
                args=(time_queue,)
            )
            time_process.start()
            time_queue.put("show")
            time_process.join(timeout=0.1)
        except Exception as e:
            print(f"显示时间失败: {str(e)}")

    def close_window(self):
        self.window.destroy()

    def update_character_image(self, emotion):
        """更新角色立绘"""
        self.current_emotion = emotion

        # 随机选择1或2
        image_number = random.randint(1, 2)

        # 构建图片路径
        image_path = os.path.join("images", f"{emotion}_{image_number}.png")

        # 检查文件是否存在
        if not os.path.exists(image_path):
            print(f"立绘文件不存在: {image_path}")
            return

        # 使用缓存或加载图片
        cache_key = f"{emotion}_{image_number}"
        if cache_key in self.images_cache:
            pil_image = self.images_cache[cache_key]
        else:
            try:
                # 使用PIL打开带透明通道的图片
                pil_image = Image.open(image_path)

                # 确保保留透明通道
                if pil_image.mode != 'RGBA':
                    pil_image = pil_image.convert('RGBA')

                # 应用缩放
                if self.scale != 1.0:
                    new_width = int(pil_image.width * self.scale)
                    new_height = int(pil_image.height * self.scale)
                    pil_image = pil_image.resize((new_width, new_height), Image.LANCZOS)

                # 缓存图片
                self.images_cache[cache_key] = pil_image
            except Exception as e:
                print(f"加载立绘失败: {str(e)}")
                return

        # 更新显示
        try:
            self.photo = ImageTk.PhotoImage(pil_image)

            # 更新画布
            self.canvas.delete("character")
            self.canvas.create_image(
                0,
                0,
                image=self.photo,
                anchor="nw",
                tags="character"
            )

            # 更新窗口尺寸以适应图片
            self.window.geometry(f"{pil_image.width}x{pil_image.height}")

            print(f"更新立绘: {emotion}_{image_number}.png (缩放: {self.scale * 100}%)")

        except Exception as e:
            print(f"显示立绘失败: {str(e)}")

    def play_jump_animation(self):
        """播放立绘跳动动画"""
        original_y = self.window.winfo_y()
        jump_height = random.randint(10, 15)  # 随机跳动幅度10-15像素
        duration = 400  # 400毫秒
        frames = 20
        frame_delay = duration // frames

        # 动画路径：上-下-上-原位
        path = [
            (0, -jump_height),  # 向上
            (0, jump_height),  # 向下
            (0, -jump_height * 0.3),  # 向上（小幅度）
            (0, jump_height * 0.3)  # 向下回原位
        ]

        current_frame = 0
        total_frames = len(path)

        def animate():
            nonlocal current_frame
            if current_frame < total_frames:
                dx, dy = path[current_frame]
                x = self.window.winfo_x()
                y = original_y + dy
                self.window.geometry(f"+{x}+{int(y)}")
                current_frame += 1
                self.window.after(frame_delay, animate)
            else:
                # 动画结束，回到原位
                x = self.window.winfo_x()
                self.window.geometry(f"+{x}+{original_y}")

        animate()

    def update_bubble(self, text):
        """更新气泡内容"""
        # 过滤空文本
        if not text.strip():
            return

        if not self.bubble.visible:
            # 根据窗口位置决定气泡位置
            win_x = self.window.winfo_x()
            win_width = self.window.winfo_width()
            screen_width = self.window.winfo_screenwidth()

            # 如果窗口在屏幕右半边，气泡在左上部
            if win_x > screen_width // 2:
                bubble_x = win_width * 0.2
            else:  # 否则在右上部
                bubble_x = win_width * 0.8

            position = (
                bubble_x,
                random.randint(20, int(self.window.winfo_height() * 0.3))
            )
            self.bubble.show(text, position)
        else:
            self.bubble.update_text(text)

        # 设置5秒后隐藏气泡
        if self.bubble_timer:
            self.window.after_cancel(self.bubble_timer)
        self.bubble_timer = self.window.after(5000, self.hide_bubble)

    def hide_bubble(self):
        """隐藏气泡"""
        self.bubble.hide()

    def check_queues(self):
        """检查队列中的消息"""
        try:
            # 检查情感队列
            while True:
                emotion = self.emotion_queue.get_nowait()
                print(f"收到情感更新: {emotion}")
                self.update_character_image(emotion)
        except queue.Empty:
            pass

        try:
            # 检查气泡队列
            while True:
                bubble_data = self.bubble_queue.get_nowait()
                # 处理跳动信号
                if 'jump' in bubble_data and bubble_data['jump']:
                    print("收到跳动信号")
                    self.play_jump_animation()
                    # 显示跳动指示器
                    self.bubble.show_jump_indicator()
                # 处理文本更新
                elif 'text' in bubble_data:
                    text = bubble_data.get('text', '')
                    print(f"收到气泡消息: {text}")
                    self.update_bubble(text)
        except queue.Empty:
            pass

        # 每100毫秒检查一次
        self.window.after(100, self.check_queues)


def run_character_window(emotion_queue, bubble_queue):
    """启动立绘窗口"""
    window = CharacterWindow(emotion_queue, bubble_queue)