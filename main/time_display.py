import tkinter as tk
import time
import multiprocessing
import os


def run_time_display(time_queue=None):
    """显示时间窗口"""
    window = TimeDisplay(time_queue)


class TimeDisplay:
    def __init__(self, time_queue=None):
        # 创建窗口
        self.window = tk.Tk()
        self.window.title("Time Display")

        # 设置无边框窗口
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)  # 保持置顶
        self.window.attributes("-alpha", 0.0)  # 初始透明

        # 设置初始位置（屏幕顶部中央）
        screen_width = self.window.winfo_screenwidth()
        self.window.geometry(f"+{screen_width // 2 - 100}+10")

        # 创建标签
        self.time_label = tk.Label(
            self.window,
            text="",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="black",
            padx=10,
            pady=5
        )
        self.time_label.pack(fill=tk.BOTH, expand=True)

        # 启动时间更新
        self.update_time()

        # 如果有队列，监听显示请求
        if time_queue:
            self.time_queue = time_queue
            self.window.after(100, self.check_queue)
        else:
            # 直接显示
            self.show_time()

        self.window.mainloop()

    def check_queue(self):
        """检查队列中的显示请求"""
        try:
            if not self.time_queue.empty():
                message = self.time_queue.get_nowait()
                if message == "show":
                    self.show_time()
        except:
            pass
        self.window.after(100, self.check_queue)

    def show_time(self):
        """显示时间窗口"""
        # 更新位置（屏幕顶部中央）
        screen_width = self.window.winfo_screenwidth()
        self.window.geometry(f"200x40+{screen_width // 2 - 100}+10")

        # 设置透明度
        self.window.attributes("-alpha", 1.0)

        # 5秒后渐隐
        self.fade_out()

    def fade_out(self):
        """渐隐效果"""
        alpha = self.window.attributes("-alpha")
        if alpha > 0.1:
            alpha -= 0.05
            self.window.attributes("-alpha", alpha)
            self.window.after(50, self.fade_out)
        else:
            self.window.attributes("-alpha", 0.0)

    def update_time(self):
        """更新时间显示"""
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.config(text=current_time)
        self.window.after(1000, self.update_time)


if __name__ == "__main__":
    run_time_display()