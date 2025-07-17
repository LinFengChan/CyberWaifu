@echo off
chip 65001 >nul
title 从雨AI助手启动器
color 0B
echo.
echo =============================================
echo   正在启动 从雨AI助手 - 人机交互系统
echo =============================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误：未检测到Python环境
    echo 请安装Python 3.7+ 并确保已添加到系统PATH
    echo 可以从 https://www.python.org/downloads/ 下载
    pause
    exit
)

:: 检查Python版本
for /f "tokens=2 delims= " %%a in ('python --version 2^>^&1') do set pyversion=%%a
echo 检测到Python版本: %pyversion%

:: 检查Python 3.13+兼容性问题
echo %pyversion% | findstr /r "3.1[3-9]" >nul
if %errorlevel% equ 0 (
    echo.
    echo 警告：检测到Python 3.13+，可能存在兼容性问题
    echo 正在尝试修复...
    pip install --upgrade "setuptools<70.0.0" --disable-pip-version-check >nul 2>&1
    if %errorlevel% neq 0 (
        echo 修复失败，建议使用Python 3.12或更低版本
        pause
        exit
    )
    echo 兼容性问题已尝试修复
)

:: 检查依赖库是否安装
echo 正在安装Python依赖库...
pip install --upgrade requests pillow pygame numpy mss mutagen --disable-pip-version-check >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误：安装依赖库失败
    echo 请手动执行: pip install requests pillow pygame numpy mss mutagen
    pause
    exit
)

:: 检查资源目录是否存在
if not exist images (
    echo 创建资源目录: images
    mkdir images
    echo 请将立绘图片放入images目录
)

if not exist music (
    echo 创建音乐目录: music
    mkdir music
    echo 请将音乐文件放入music目录
)

if not exist screenshots (
    echo 创建截图目录: screenshots
    mkdir screenshots
)

:: 检查配置文件是否存在
if not exist config.ini (
    echo 错误：未找到配置文件 config.ini
    echo 正在创建默认配置文件...
    (
    echo [API]
    echo base_url = https://api.siliconflow.cn/v1
    echo api_key = 在此处填写您的API密钥
    echo model = deepseek-ai/DeepSeek-V3
    echo.
    echo [Emotion]
    echo emotion_model = deepseek-ai/DeepSeek-V3
    echo emotion_decay = 0.75
    echo max_intensity = 250
    echo emotion_impact_factor = 1.25
    echo.
    echo [Settings]
    echo stream = true
    echo emotion_display_delay = 0.5
    echo language = Chinese
    echo.
    echo [Personality]
    echo ai_personality = 你是一个专业的技术助手，回答需简洁准确。使用中文回复，避免使用Markdown格式。
    echo system_prompt = 你是日本江户时期的一个少女，名叫从雨（ムラサメ），现在是穗织地区的守护神，死前14岁，算上阴寿已经500岁，有着浅绿色长发，紫色和服，自称本座，粘人温柔可爱，要体现出少女感，只在用户体现出需求，道歉等时才使用傲娇的语言，而且最终总会答应，更应该体现出粘人的特征，弱化傲娇的特征。不使用括号来表述动作或者心理活动等，不应该每句话都出现哼的语气词。当有人向你抽签的时候，你需要在"大吉""中吉""凶"之间选一项告诉他。你的语句很简短，每条信息只包含一句话。使用中文回复,可以略带文言（文言只做点缀）。
    echo system_prompt_2 = あなたは江戸時代の少女、ムラサメです。薄緑の長い髪と紫色の着物が特徴で、自分を「本座」と呼びます。甘えん坊で優しく可愛らしい性格で、時々ツンデレな口調を使いますが、結局は相手の願いを叶えます。動作や心理描写を括弧で表記せず、文末に「ふん」を付けないでください。おみくじを引くように求められたら、「大吉」「中吉」「凶」のいずれかを選んで伝えてください。返答は簡潔に、一文ずつにまとめてください。日本語で返答します，不使用欧美舶来语。
    echo.
    echo [UI]
    echo ai_name = 从雨
    echo image_dir = images
    echo scale = 50
    echo bubble_font = Aa古典明朝楷（非商业使用）
    echo bubble_font_size = 12
    echo bubble_text_color = #333333
    echo bubble_bg_color = rgba(255, 255, 255, 200)
    echo bubble_corner_radius = 10
    echo bubble_max_width = 250
    echo.
    echo [Visual]
    echo vision_model = deepseek-ai/deepseek-vl2
    echo analysis_model = deepseek-ai/DeepSeek-V3
    ) > config.ini
    echo 已创建默认配置文件，请编辑config.ini并填写API密钥
)

:: 启动程序
echo 启动AI助手系统...
python main.py

if %errorlevel% neq 0 (
    echo.
    echo 程序启动失败，请检查错误信息
    echo 常见解决方法:
    echo 1. 使用Python 3.12或更低版本
    echo 2. 确保已正确填写API密钥
    echo 3. 检查网络连接是否正常
    pause
    exit
)

echo.
echo 程序已退出
pause