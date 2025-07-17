import os
import pygame
import threading
import time
import tkinter as tk
from tkinter import ttk
from mutagen.mp3 import MP3
import subprocess
import sys


class MusicPlayer(tk.Frame):
    def __init__(self, parent, music_dir="music", *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.music_dir = music_dir
        self.playlist = []
        self.current_index = 0
        self.playing = False
        self.paused = False
        self.volume = 0.5

        # 创建UI
        self.configure(bg='#f0f0f0', padx=5, pady=5)

        # 标题栏
        self.title_bar = tk.Frame(self, bg='#e0e0e0', height=20)
        self.title_bar.pack(fill=tk.X)

        # 标题
        self.title_label = tk.Label(self.title_bar, text="音乐播放器", bg='#e0e0e0', fg='black')
        self.title_label.pack(side=tk.LEFT, padx=5)

        # 关闭按钮
        self.close_button = tk.Button(
            self.title_bar,
            text="×",
            command=self.hide_player,
            bg='#e0e0e0',
            fg='black',
            bd=0,
            font=("Arial", 14)
        )
        self.close_button.pack(side=tk.RIGHT)

        # 控制按钮
        self.control_frame = tk.Frame(self, bg='#f0f0f0')
        self.control_frame.pack(fill=tk.X, pady=5)

        self.prev_button = tk.Button(
            self.control_frame,
            text="⏮",
            command=self.prev,
            width=3,
            font=("Arial", 10)
        )
        self.prev_button.pack(side=tk.LEFT, padx=2)

        self.play_button = tk.Button(
            self.control_frame,
            text="▶",
            command=self.toggle_play,
            width=3,
            font=("Arial", 10)
        )
        self.play_button.pack(side=tk.LEFT, padx=2)

        self.next_button = tk.Button(
            self.control_frame,
            text="⏭",
            command=self.next,
            width=3,
            font=("Arial", 10)
        )
        self.next_button.pack(side=tk.LEFT, padx=2)

        # 刷新按钮
        self.refresh_button = tk.Button(
            self.control_frame,
            text="↻",
            command=self.load_music,
            width=3,
            font=("Arial", 10)
        )
        self.refresh_button.pack(side=tk.LEFT, padx=2)

        # 打开文件夹按钮
        self.open_button = tk.Button(
            self.control_frame,
            text="📁",
            command=self.open_music_dir,
            width=3,
            font=("Arial", 10)
        )
        self.open_button.pack(side=tk.LEFT, padx=2)

        # 进度条
        self.progress_frame = tk.Frame(self, bg='#f0f0f0')
        self.progress_frame.pack(fill=tk.X, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Scale(
            self.progress_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.progress_var,
            command=self.set_position
        )
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # 时间标签
        self.time_label = tk.Label(
            self.progress_frame,
            text="00:00/00:00",
            bg='#f0f0f0',
            font=("Arial", 8)
        )
        self.time_label.pack(side=tk.RIGHT, padx=5)

        # 音量控制
        self.volume_frame = tk.Frame(self, bg='#f0f0f0')
        self.volume_frame.pack(fill=tk.X, pady=5)

        self.volume_label = tk.Label(
            self.volume_frame,
            text="🔈",
            bg='#f0f0f0',
            font=("Arial", 10)
        )
        self.volume_label.pack(side=tk.LEFT, padx=2)

        self.volume_var = tk.DoubleVar(value=self.volume * 100)
        self.volume_scale = ttk.Scale(
            self.volume_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.volume_var,
            command=self.set_volume,
            length=100
        )
        self.volume_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # 歌曲信息
        self.song_label = tk.Label(
            self,
            text="加载音乐中...",
            bg='#f0f0f0',
            font=("Arial", 8),
            anchor="w"
        )
        self.song_label.pack(fill=tk.X, padx=5, pady=2)

        # 加载音乐
        self.load_music()

        # 启动进度更新线程
        self.update_thread = threading.Thread(target=self.update_progress, daemon=True)
        self.update_thread.start()

    def hide_player(self):
        """隐藏播放器"""
        self.place_forget()

    def load_music(self):
        # 打印当前工作目录和音乐目录路径
        cwd = os.getcwd()
        music_path = os.path.join(cwd, self.music_dir)
        print(f"尝试从目录加载音乐: {music_path}")

        if not os.path.exists(music_path):
            print(f"音乐目录不存在，创建目录: {music_path}")
            os.makedirs(music_path)

        self.playlist = []
        for f in os.listdir(music_path):
            if f.endswith(('.mp3', '.wav', '.ogg')):
                file_path = os.path.join(music_path, f)
                self.playlist.append(file_path)
                print(f"找到音乐文件: {file_path}")

        if self.playlist:
            self.song_label.config(text=f"准备播放: {os.path.basename(self.playlist[0])}")
            print(f"找到 {len(self.playlist)} 个音乐文件")
        else:
            self.song_label.config(text=f"没有找到音乐文件，请将音乐放入 {music_path}")
            print(f"没有在 {music_path} 中找到音乐文件")

    def toggle_play(self):
        if not self.playlist:
            return
        if not self.playing:
            self.play()
        else:
            self.pause()

    def play(self):
        if not self.playlist:
            return
        if self.paused:
            pygame.mixer.music.unpause()
            self.paused = False
            self.play_button.config(text="⏸")
        else:
            try:
                pygame.mixer.music.load(self.playlist[self.current_index])
                pygame.mixer.music.play()
                self.playing = True
                self.paused = False
                self.play_button.config(text="⏸")
                # 更新歌曲信息
                song_name = os.path.basename(self.playlist[self.current_index])
                self.song_label.config(text=f"正在播放: {song_name}")
            except Exception as e:
                print(f"播放音乐失败: {str(e)}")
                self.song_label.config(text=f"播放失败: {str(e)}")

    def pause(self):
        pygame.mixer.music.pause()
        self.paused = True
        self.play_button.config(text="▶")

    def stop(self):
        pygame.mixer.music.stop()
        self.playing = False
        self.paused = False
        self.play_button.config(text="▶")

    def next(self):
        if not self.playlist:
            return
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.stop()
        self.play()

    def prev(self):
        if not self.playlist:
            return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.stop()
        self.play()

    def set_volume(self, value):
        self.volume = float(value) / 100.0
        pygame.mixer.music.set_volume(self.volume)

    def set_position(self, value):
        if not self.playing or not pygame.mixer.music.get_busy():
            return
        # 计算位置（百分比）
        pos = float(value)
        # 获取歌曲总长度（秒）
        length = self.get_song_length()
        if length > 0:
            # 设置到指定位置
            pygame.mixer.music.set_pos(pos * length / 100.0)

    def get_song_length(self):
        """获取当前歌曲的总长度（秒）"""
        if not self.playlist or self.current_index >= len(self.playlist):
            return 0

        try:
            file_path = self.playlist[self.current_index]
            if file_path.endswith('.mp3'):
                audio = MP3(file_path)
                return audio.info.length
            else:
                # 对于非MP3文件，使用pygame的Sound
                sound = pygame.mixer.Sound(file_path)
                return sound.get_length()
        except Exception as e:
            print(f"获取歌曲长度失败: {str(e)}")
            return 0

    def open_music_dir(self):
        """打开音乐目录"""
        if not os.path.exists(self.music_dir):
            os.makedirs(self.music_dir)
        # 根据操作系统打开文件夹
        if sys.platform == "win32":
            os.startfile(self.music_dir)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", self.music_dir])
        else:
            subprocess.Popen(["xdg-open", self.music_dir])

    def update_progress(self):
        while True:
            if self.playing and pygame.mixer.music.get_busy() and not self.paused:
                # 获取当前播放位置（秒）
                current_time = pygame.mixer.music.get_pos() / 1000.0
                # 获取当前歌曲的总长度
                total_time = self.get_song_length()
                if total_time > 0:
                    # 更新进度条
                    progress = min(100, max(0, current_time * 100 / total_time))
                    self.progress_var.set(progress)

                    # 更新时间标签
                    current_str = time.strftime('%M:%S', time.gmtime(current_time))
                    total_str = time.strftime('%M:%S', time.gmtime(total_time))
                    self.time_label.config(text=f"{current_str}/{total_str}")
            time.sleep(0.5)