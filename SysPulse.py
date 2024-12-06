import psutil
import GPUtil
import time
import tkinter as tk
from tkinter import ttk
from threading import Thread
import wmi
import pythoncom
import configparser
import os
import platform
from pystray import Icon, Menu, MenuItem
from PIL import Image
import win32gui
import win32con
import win32api
import queue
import sys
import json
import subprocess
import multiprocessing


# 创建无窗口的进程
DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000



class SystemMonitor:
    def __init__(self, root):
        # 初始化 WMI 连接
        self.wmi_connection = None
        self.initialize_wmi()

        self.root = root
        self.root.title("SysPulse")
        self.root.resizable(True, True)
        self.root.configure(bg='#F5F5F7')

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TFrame', background='#F5F5F7')
        self.style.configure('TLabel', background='#F5F5F7', foreground='#333333', font=('SF Pro Text', 12))
        self.style.configure('TButton', background='#8E8E93', foreground='white', font=('SF Pro Text', 12), relief='flat', borderwidth=0, padding=5)
        self.style.map('TButton', background=[('active', '#707073')])
        self.style.configure('TCheckbutton', background='#F5F5F7', foreground='#333333', font=('SF Pro Text', 12))
        self.style.configure('TCombobox', background='#FFFFFF', foreground='#333333', font=('SF Pro Text', 12))
        
        # 加载翻译文件
        self.translations = self.load_translations()
        
        # 默认值
        self.always_on_top_var = tk.BooleanVar(value=False)
        self.font_size_var = tk.StringVar(value="11")
        self.cpu_name_var = tk.BooleanVar(value=True)
        self.cpu_usage_var = tk.BooleanVar(value=True)
        self.cpu_temp_var = tk.BooleanVar(value=True)
        self.memory_var = tk.BooleanVar(value=True)
        self.gpu_name_var = tk.BooleanVar(value=True)
        self.gpu_usage_var = tk.BooleanVar(value=True)
        self.gpu_temp_var = tk.BooleanVar(value=True)
        self.network_speed_var = tk.BooleanVar(value=True)
        self.language_var = tk.StringVar(value="English")
        self.mouse_penetrate_var = tk.BooleanVar(value=False)
        self.borderless_mode_var = tk.BooleanVar(value=False)  # New variable for borderless mode
        self.monitor_resource_usage_var = tk.BooleanVar(value=True)  # New variable for resource usage

        self.show_settings_button_var = tk.BooleanVar(value=True)  # 默认显示Settings按钮
        # Queue for thread-safe UI updates
        self.queue = queue.Queue()
        
        self.main_hwnd = None  # 用于存储主窗口的句柄
        # 添加一个变量来跟踪鼠标穿透
        self.needs_mouse_penetration_update = False
        # 添加透明度变量
        self.transparency_var = tk.IntVar(value=255)  # 255为完全不透明
        # 添加cpu温度错误计数器
        self.cpu_temp_error_count = 0
        self.max_temp_errors = 3
        self.disable_temp_monitoring = False
        # 启动主界面并读取配置文件
        self.create_widgets()
        self.load_config()

        # 启动线程之前，确保主窗口是隐藏的。
        self.root.after(100, self.start_threads)  # 延迟启动线程以确保初始化完成了

        self.root.after(100, self.adjust_window_size)

        # Process queue to update UI from threads
        self.root.after(100, self.process_queue)

    # 定义一个新的方法用于启动线程
    def start_threads(self):
        self.system_thread = Thread(target=self.update_system_info)
        self.system_thread.daemon = True
        self.system_thread.start()

        self.network_thread = Thread(target=self.update_network_speed)
        self.network_thread.daemon = True
        self.network_thread.start()

        self.resource_thread = Thread(target=self.update_resource_usage)
        self.resource_thread.daemon = True
        self.resource_thread.start()

    def initialize_wmi(self):
        # pass
        # 初始化WMI连接"""
        try:
            pythoncom.CoInitialize()
            self.wmi_connection = wmi.WMI(namespace=r"root\OpenHardwareMonitor")
            pass
        except Exception as e:
            # print(f"Error initializing WMI connection: {e}")
            self.wmi_connection = None

    def create_widgets(self):
        # 获取主窗口的句柄
        self.root.update()  # 确保窗口已经创建
        self.main_hwnd = win32gui.FindWindow(None, self.root.title())  # 根据窗口标题获取句柄

        self.main_frame = ttk.Frame(self.root, padding="20", style='TFrame')
        self.main_frame.grid(column=0, row=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.labels = [
            ('cpu_name_label', "CPU: "),
            ('cpu_label', "CPU Usage: "),
            ('cpu_temp_label', "CPU Temp: "),
            ('memory_label', "Memory: "),
            ('gpu_name_label', "GPU: "),
            ('gpu_label', "GPU Usage: "),
            ('gpu_temp_label', "GPU Temp: "),
            ('download_label', "Download Speed: "),
            ('upload_label', "Upload Speed: "),
            ('resource_label', "Resource Usage: ")
        ]

        for i, (attr_name, text) in enumerate(self.labels):
            label = ttk.Label(self.main_frame, text=text, style='TLabel')
            label.grid(column=0, row=i, sticky=tk.W, pady=5)
            setattr(self, attr_name, label)
        # Settings按钮
        self.settings_button = ttk.Button(self.main_frame, text="Settings", command=self.open_settings, style='TButton')
        self.settings_button.grid(column=0, row=len(self.labels), sticky=tk.W, pady=10)

    def open_settings(self): 
        # 检查是否已有Settings窗口，防止重复打开
        if hasattr(self, 'current_settings_window') and self.current_settings_window:
            self.current_settings_window.destroy()
        
        settings_window = tk.Toplevel(self.root)
        settings_window.title(self.translate("Settings"))
        settings_window.configure(bg='#F5F5F7')
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # 保存当前Settings窗口的引用，用于刷新时销毁
        self.current_settings_window = settings_window
        
        main_frame = ttk.Frame(settings_window, padding="20", style='TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=self.translate("Settings"), font=("SF Pro Display", 18, "bold"), style='TLabel').pack(pady=(0, 20))

        ttk.Checkbutton(main_frame, text=self.translate("Always on Top"), variable=self.always_on_top_var, command=self.toggle_always_on_top, style='TCheckbutton').pack(pady=5, anchor='w')

        ttk.Label(main_frame, text=self.translate("Font Size:"), style='TLabel').pack(pady=(10, 5), anchor='w')
        font_sizes = [str(i) for i in range(8, 25)]
        ttk.Combobox(main_frame, textvariable=self.font_size_var, values=font_sizes, state="readonly", style='TCombobox').pack(pady=5, fill='x')
        self.font_size_var.trace("w", self.update_font_size)

        ttk.Label(main_frame, text=self.translate("Language:"), style='TLabel').pack(pady=(10, 5), anchor='w')
        ttk.Radiobutton(main_frame, text="English", variable=self.language_var, value="English", command=self.refresh_settings_window , style='TCheckbutton').pack(anchor="w", pady=2)
        ttk.Radiobutton(main_frame, text="中文", variable=self.language_var, value="Chinese", command=self.refresh_settings_window , style='TCheckbutton').pack(anchor="w", pady=2)

        ttk.Label(main_frame, text=self.translate("Personalization Settings:"), style='TLabel').pack(pady=(10, 5), anchor='w')
        ttk.Checkbutton(main_frame, text=self.translate("Enable Mouse Penetration"), variable=self.mouse_penetrate_var, command=self.toggle_mouse_penetration, style='TCheckbutton').pack(pady=5, anchor='w')
        ttk.Checkbutton(main_frame, text=self.translate("Enable Borderless Mode"), variable=self.borderless_mode_var, command=self.toggle_borderless_mode, style='TCheckbutton').pack(pady=5, anchor='w')
        # 添加透明度滑块 from_最小值为50（约20%不透明度）to最大值为255（完全不透明）
        ttk.Scale(main_frame,from_=50, to=255, variable=self.transparency_var, command=self.update_transparency,  orient='horizontal').pack(pady=5, fill='x')
        
        ttk.Label(main_frame, text=self.translate("Displayed Information:"), style='TLabel').pack(pady=(10, 5), anchor='w')
        for var_name, text in [
            ('cpu_name_var', "CPU: "),
            ('cpu_usage_var', "CPU Usage: "),
            ('cpu_temp_var', "CPU Temp: "),
            ('memory_var', "Memory: "),
            ('gpu_name_var', "GPU: "),
            ('gpu_usage_var', "GPU Usage: "),
            ('gpu_temp_var', "GPU Temp: "),
            ('network_speed_var', "Network Speed: "),
            ('monitor_resource_usage_var', "Monitor Resource Usage: ")
        ]:
            ttk.Checkbutton(main_frame, text=self.translate(text), variable=getattr(self, var_name), style='TCheckbutton').pack(anchor="w", pady=2)    
         
        ttk.Checkbutton(main_frame, text=self.translate("Show Settings Button"), variable=self.show_settings_button_var, command=self.toggle_settings_button_visibility, style='TCheckbutton').pack(pady=(10, 5), anchor='w')
        ttk.Button(main_frame, text=self.translate("Save Settings"), command=self.save_config, style='TButton').pack(pady=(20, 0), fill='x')

        settings_window.update_idletasks()
        width = settings_window.winfo_reqwidth() + 20
        height = settings_window.winfo_reqheight() + 20
        settings_window.geometry(f"{width}x{height}")
    
    def toggle_settings_button_visibility(self):
        # 根据复选框的状态来控制Settings按钮的显示或隐藏
        if self.show_settings_button_var.get():
            self.settings_button.grid(column=0, row=len(self.labels), sticky=tk.W, pady=10)  # 显示Settings按钮
        else:
            self.settings_button.grid_forget()  # 隐藏Settings按钮
    
    def refresh_settings_window(self):
        # 切换语言后，刷新Settings窗口
        self.open_settings()
    
    def toggle_always_on_top(self):
        self.root.attributes("-topmost", self.always_on_top_var.get())
        
    def load_translations(self):
        #  从文件加载翻译
        try:
            with open('translations.json', 'r', encoding='utf-8') as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # print(f"Error loading translations: {e}, using default translations")
            return self.get_default_translations()
        
    def get_default_translations(self):
        # 返回默认的翻译字典
        return {      
            "English": {
                "CPU: ": "CPU: ",
                "CPU Usage: ": "CPU Usage: ",
                "CPU Temp: ": "CPU Temp: ",
                "Memory: ": "Memory: ",
                "GPU: ": "GPU: ",
                "GPU Usage: ": "GPU Usage: ",
                "GPU Temp: ": "GPU Temp: ",
                "Download Speed: ": "Download Speed: ",
                "Upload Speed: ": "Upload Speed: ",
                "Resource Usage: ": "Resource Usage: ",
                "Settings": "Settings",
                "Always on Top": "Always on Top",
                "Font Size:": "Font Size:",
                "Language:": "Language:",
                "Personalization Settings:": "Personalization Settings:",
                "Enable Mouse Penetration": "Enable Mouse Penetration",
                "Enable Borderless Mode": "Enable Borderless Mode",
                "Displayed Information:": "Displayed Information:",
                "CPU Name": "CPU Name",
                "CPU Usage": "CPU Usage",
                "CPU Temperature": "CPU Temperature",
                "Memory Usage": "Memory Usage",
                "GPU Name": "GPU Name",
                "GPU Usage": "GPU Usage",
                "GPU Temperature": "GPU Temperature",
                "Network Speed": "Network Speed",
                "Monitor Resource Usage": "Monitor Resource Usage",
                "Show Settings Button": "Show Settings Button",
                "Save Settings": "Save Settings"
            },
            "Chinese": {
                "CPU: ": "处理器: ",
                "CPU Usage: ": "处理器使用率: ",
                "CPU Temp: ": "处理器温度: ",
                "Memory: ": "内存: ",
                "GPU: ": "显卡: ",
                "GPU Usage: ": "显卡使用率: ",
                "GPU Temp: ": "显卡温度: ",
                "Download Speed: ": "下载速度: ",
                "Upload Speed: ": "上传速度: ",
                "Resource Usage: ": "资源使用情况: ",
                "Settings": "设置",
                "Always on Top": "总在最前",
                "Font Size:": "字体大小:",
                "Language:": "语言:",
                "Personalization Settings:": "个性化设置:",
                "Enable Mouse Penetration": "启用鼠标穿透",
                "Enable Borderless Mode": "启用无边框模式",
                "Displayed Information:": "显示信息:",
                "CPU Name": "处理器名称",
                "CPU Usage": "处理器使用率",
                "CPU Temperature": "处理器温度",
                "Memory Usage": "内存使用情况",
                "GPU Name": "显卡名称",
                "GPU Usage": "显卡使用率",
                "GPU Temperature": "显卡温度",
                "Network Speed": "网络速度",
                "Monitor Resource Usage": "监控资源使用情况",
                "Show Settings Button": "显示设置按钮",
                "Save Settings": "保存设置"
            }
        }     

    
    def update_font_size(self, *args):
        try:
            size = int(self.font_size_var.get())
            self.style.configure('TLabel', font=("SF Pro Text", size))
            self.style.configure('TButton', font=("SF Pro Text", size))
            self.style.configure('TCheckbutton', font=("SF Pro Text", size))
            self.style.configure('TCombobox', font=("SF Pro Text", size))
        except ValueError:
            # print("Invalid font size")
            pass
    
    def update_transparency(self, *args):
        # 更新窗口透明度
        if self.main_hwnd:
            # 获取当前窗口样式
            ex_style = win32gui.GetWindowLong(self.main_hwnd, win32con.GWL_EXSTYLE)
            
            # 确保窗口有 WS_EX_LAYERED 样式
            if not (ex_style & win32con.WS_EX_LAYERED):
                win32gui.SetWindowLong(
                    self.main_hwnd,
                    win32con.GWL_EXSTYLE,
                    ex_style | win32con.WS_EX_LAYERED
                )
            
            # 设置透明度
            win32gui.SetLayeredWindowAttributes(
                self.main_hwnd,
                0,  # 颜色键（这里不使用）
                self.transparency_var.get(),  # 透明度值
                win32con.LWA_ALPHA  # 使用透明度
            )
    
    def load_config(self):
        config = configparser.ConfigParser()
        if os.path.exists('config.ini'):
            config.read('config.ini')
            self.always_on_top_var.set(config.getboolean('Settings', 'always_on_top', fallback=False))
            self.font_size_var.set(config.get('Settings', 'font_size', fallback='12'))
            self.language_var.set(config.get('Settings', 'language', fallback='English'))
            self.mouse_penetrate_var.set(config.getboolean('Settings', 'mouse_penetrate', fallback=False))
            self.borderless_mode_var.set(config.getboolean('Settings', 'borderless_mode', fallback=False))  # Load borderless mode setting
            self.monitor_resource_usage_var.set(config.getboolean('Display', 'monitor_resource_usage', fallback=True))
            self.update_font_size()
            self.transparency_var.set(config.getint('Settings', 'transparency', fallback=255))
            self.update_transparency()
            for var_name in ['cpu_name_var', 'cpu_usage_var', 'cpu_temp_var', 'memory_var', 'gpu_name_var', 'gpu_usage_var', 'gpu_temp_var', 'network_speed_var']:
                getattr(self, var_name).set(config.getboolean('Display', var_name.replace('_var', ''), fallback=True))
        self.toggle_always_on_top()
        self.update_language()
        self.toggle_mouse_penetration()
        self.toggle_borderless_mode()

    def save_config(self):
        config = configparser.ConfigParser()
        config['Settings'] = {
            'always_on_top': str(self.always_on_top_var.get()),
            'font_size': self.font_size_var.get(),
            'language': self.language_var.get(),
            'mouse_penetrate': str(self.mouse_penetrate_var.get()),
            'borderless_mode': str(self.borderless_mode_var.get())
        }
        config['Display'] = {var_name.replace('_var', ''): str(getattr(self, var_name).get())
                             for var_name in ['cpu_name_var', 'cpu_usage_var', 'cpu_temp_var', 'memory_var', 'gpu_name_var', 'gpu_usage_var', 'gpu_temp_var', 'network_speed_var', 'monitor_resource_usage_var']}
        config['Settings']['transparency'] = str(self.transparency_var.get())       
        with open('config.ini', 'w') as configfile:
            config.write(configfile)
        self.update_language()
        self.update_transparency()
        self.toggle_mouse_penetration()
        self.toggle_borderless_mode()

    def get_cpu_name(self):
        return platform.processor()

    def get_cpu_temperature(self):
        # 如果已经禁用了温度监控，直接返回N/A
        if self.disable_temp_monitoring:
            return 'N/A'
            
        if self.wmi_connection is None:
            self.cpu_temp_error_count += 1
            if self.cpu_temp_error_count >= self.max_temp_errors:
                self.disable_temp_monitoring = True
                # print("CPU temperature monitoring has been disabled after multiple failures")
            return 'N/A'
            
        try:
            temperature_infos = self.wmi_connection.Sensor(SensorType='Temperature', Parent='CPU')
            if temperature_infos:
                # 成功获取温度，重置错误计数
                self.cpu_temp_error_count = 0
                return temperature_infos[0].Value
            else:
                self.cpu_temp_error_count += 1
                if self.cpu_temp_error_count >= self.max_temp_errors:
                    self.disable_temp_monitoring = True
                    # print("CPU temperature monitoring has been disabled after multiple failures")
                return 'N/A'
        except Exception as e:
            # print(f"Error getting CPU temperature: {e}")
            self.cpu_temp_error_count += 1
            if self.cpu_temp_error_count >= self.max_temp_errors:
                self.disable_temp_monitoring = True
                # print("CPU temperature monitoring has been disabled after multiple failures")
            return 'N/A'
        # return 'N/A'

    def get_gpu_info(self):
        # 改进的GPU信息获取方法
        try:
            # 设置CUDA_DEVICE_ORDER环境变量
            os.environ['CUDA_DEVICE_ORDER'] = 'PCI_BUS_ID'
            
            # 指定GPU设备ID
            os.environ['CUDA_VISIBLE_DEVICES'] = '0'
            
            gpus = GPUtil.getGPUs()
            if gpus:
                gpu = gpus[0]
                return gpu.name, gpu.load * 100, gpu.temperature
            return 'N/A', 'N/A', 'N/A'
        except Exception as e:
            # print(f"Error getting GPU info: {e}")
            return 'N/A', 'N/A', 'N/A'
    
    def get_cpu_info(self):
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
        except Exception as e:
            # print(f"Error getting CPU usage: {e}")
            cpu_usage = 'N/A'
        
        return cpu_usage

    def get_memory_info(self):
        try:
            memory_info = psutil.virtual_memory()
            total_memory = memory_info.total / (1024 ** 3)
            used_memory = memory_info.used / (1024 ** 3)
            memory_percent = memory_info.percent
        except Exception as e:
            # print(f"Error getting memory info: {e}")
            total_memory = used_memory = memory_percent = 'N/A'
        
        return total_memory, used_memory, memory_percent

    def update_system_info(self):
        cpu_name = platform.processor()
        
        while True:
            try:
                cpu_usage = psutil.cpu_percent(interval=2)
                
                # 只有在未禁用的情况下才获取CPU温度
                cpu_temp = self.get_cpu_temperature() if not self.disable_temp_monitoring else 'N/A'
                
                memory = psutil.virtual_memory()
                total_memory = memory.total / (1024 ** 3)
                used_memory = memory.used / (1024 ** 3)
                memory_percent = memory.percent
                
                gpu_name, gpu_usage, gpu_temp = self.get_gpu_info()
                
                self.queue.put(lambda: self.update_labels(
                    cpu_name, cpu_usage, cpu_temp,
                    used_memory, total_memory, memory_percent,
                    gpu_name, gpu_usage, gpu_temp
                ))
                
                time.sleep(1)
            except Exception as e:
                # print(f"Error in update_system_info: {e}")
                time.sleep(1)

    def update_labels(self, cpu_name, cpu_usage, cpu_temp, used_memory, total_memory, memory_percent, gpu_name, gpu_usage, gpu_temp):
        updates = [
            (self.cpu_name_var, self.cpu_name_label, f"CPU: {cpu_name}"),
            (self.cpu_usage_var, self.cpu_label, f"CPU Usage: {cpu_usage:.1f}%"),
            (self.cpu_temp_var, self.cpu_temp_label, f"CPU Temp: {cpu_temp}°C"),
            (self.memory_var, self.memory_label, f"Memory: {used_memory:.2f} GB / {total_memory:.2f} GB ({memory_percent:.1f}%)"),
            (self.gpu_name_var, self.gpu_name_label, f"GPU: {gpu_name}"),
            (self.gpu_usage_var, self.gpu_label, f"GPU Usage: {gpu_usage:.1f}%"),
            (self.gpu_temp_var, self.gpu_temp_label, f"GPU Temp: {gpu_temp:.1f}°C")
        ]

        for var, label, text in updates:
            if var.get():
                label.grid()
                # 先翻译文本，再更新标签
                translated_text = self.translate(text)
                label.config(text=translated_text)
            else:
                label.grid_remove()

        self.adjust_window_size()

    def update_network_speed(self):
        old_value = psutil.net_io_counters()
        while True:
            try:
                time.sleep(2)  # 增加间隔时间
                new_value = psutil.net_io_counters()
                download_speed = (new_value.bytes_recv - old_value.bytes_recv) / 2048  # KB/s
                upload_speed = (new_value.bytes_sent - old_value.bytes_sent) / 2048  # KB/s
                
                self.queue.put(lambda: self.update_network_labels(download_speed, upload_speed))
                old_value = new_value
            except Exception as e:
                # print(f"Error in update_network_speed: {e}")
                time.sleep(1)

    def update_network_labels(self, download_speed, upload_speed):
        if self.network_speed_var.get():
            self.download_label.grid()
            self.upload_label.grid()

            # 根据下载速度选择单位
            if download_speed >= 1024:  # 大于1MB/s
                download_speed /= 1024  # 转为MB/s
                download_unit = "MB/s"
            else:
                download_unit = "KB/s"

            # 根据上传速度选择单位
            if upload_speed >= 1024:  # 大于1MB/s
                upload_speed /= 1024  # 转为MB/s
                upload_unit = "MB/s"
            else:
                upload_unit = "KB/s"

            # 更新标签文本，包含单位
            self.download_label.config(text=self.translate(f"Download Speed: {download_speed:.2f} {download_unit}"))
            self.upload_label.config(text=self.translate(f"Upload Speed: {upload_speed:.2f} {upload_unit}"))
        else:
            self.download_label.grid_remove()
            self.upload_label.grid_remove()
    def update_resource_usage(self):
        process = psutil.Process(os.getpid())
        while True:
            try:
                # 使用更大的interval减少刷新频率
                cpu_usage = process.cpu_percent(interval=2)
                memory_usage = process.memory_info().rss / (1024 ** 2)  # MB
                
                self.queue.put(lambda: self.update_resource_label(cpu_usage, memory_usage))
                time.sleep(1)
            except Exception as e:
                # print(f"Error in update_resource_usage: {e}")
                time.sleep(1)

    def update_resource_label(self, cpu_usage, memory_usage):
        if self.monitor_resource_usage_var.get():
            self.resource_label.config(text=self.translate(f"Resource Usage: CPU: {cpu_usage:.1f}%, Memory: {memory_usage:.2f} MB"))
            self.resource_label.grid()
        else:
            self.resource_label.grid_remove()

    def adjust_window_size(self):
        self.root.update_idletasks()
        self.root.geometry('')

    def create_system_tray(self):
        try:
            menu = Menu(
                MenuItem('Setting', self.open_settings),
                MenuItem('Toggle Mouse Penetration', self.toggle_mouse_penetration_menu),
                MenuItem('Show', self.show_window),
                MenuItem('Exit', self.quit_window)
            )
            
            # 使用异常处理确保图片加载
            try:
                image = Image.open('qcf.jpg')
            except Exception:
                # 如果无法加载图片，创建一个默认的
                image = Image.new('RGB', (64, 64), color=(200, 100, 90))
            
            self.icon = Icon("name", image, "SysPulse", menu)
            self.icon_thread = Thread(target=self.icon.run, daemon=True)
            self.icon_thread.start()
        except Exception as e:
            # print(f"Error creating system tray: {e}")
            pass

    def toggle_mouse_penetration_menu(self):
        self.mouse_penetrate_var.set(not self.mouse_penetrate_var.get())
        self.toggle_mouse_penetration()

    def show_window(self):
        self.root.deiconify()

    def quit_window(self):
        self.icon.stop()
        self.root.quit()
        # 退出整个程序
        sys.exit()

    def update_language(self):
        # 更新语言
        for attr_name, _ in self.labels:
            label = getattr(self, attr_name)
            current_text = label.cget("text")
            label.config(text=self.translate(current_text))

        # 更新按钮语言
        self.settings_button.config(text=self.translate("Settings"))

    def translate(self, text):
        # 使用加载的翻译
        language = self.language_var.get()
        if language not in self.translations:
            return text
            
        current_translations = self.translations[language]
        
        # 对于类似 "CPU Usage: 90.5%" 这样的文本进行处理
        for eng_prefix, trans_prefix in current_translations.items():
            if text.startswith(eng_prefix):
                value_part = text[len(eng_prefix):]
                return trans_prefix + value_part
                
        return text

    def toggle_mouse_penetration(self):
        if self.main_hwnd is None:
            self.main_hwnd = win32gui.FindWindow(None, self.root.title())
            if self.main_hwnd is None:
                return
        
        current_style = win32gui.GetWindowLong(self.main_hwnd, win32con.GWL_EXSTYLE)
        if self.mouse_penetrate_var.get():
            # 启用鼠标穿透
            new_style = current_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
        else:
            # 禁用鼠标穿透
            new_style = current_style & ~win32con.WS_EX_TRANSPARENT
        
        win32gui.SetWindowLong(self.main_hwnd, win32con.GWL_EXSTYLE, new_style)
    
    def reapply_mouse_penetration(self):
        # 重新应用鼠标穿透设置
        if self.needs_mouse_penetration_update and self.main_hwnd:
            current_style = win32gui.GetWindowLong(self.main_hwnd, win32con.GWL_EXSTYLE)
            if self.mouse_penetrate_var.get():
                new_style = current_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
            else:
                new_style = current_style & ~win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(self.main_hwnd, win32con.GWL_EXSTYLE, new_style)
            self.needs_mouse_penetration_update = False
    def toggle_borderless_mode(self):
        if self.borderless_mode_var.get():
            # 保存当前的鼠标穿透状态
            current_mouse_penetration = self.mouse_penetrate_var.get()
            
            # 启用无边框模式
            self.root.overrideredirect(True)
            
            # 重新获取窗口句柄
            self.root.update()
            self.main_hwnd = win32gui.FindWindow(None, self.root.title())
            
            # 如果之前启用了鼠标穿透，重新应用它
            if current_mouse_penetration:
                self.needs_mouse_penetration_update = True
                self.root.after(100, self.reapply_mouse_penetration)
        else:
            # 保存当前的鼠标穿透状态
            current_mouse_penetration = self.mouse_penetrate_var.get()
            
            # 禁用无边框模式
            self.root.overrideredirect(False)
            
            # 重新获取窗口句柄
            self.root.update()
            self.main_hwnd = win32gui.FindWindow(None, self.root.title())
            
            # 如果之前启用了鼠标穿透，重新应用它
            if current_mouse_penetration:
                self.needs_mouse_penetration_update = True
                self.root.after(100, self.reapply_mouse_penetration)

    def process_queue(self):
        # 从队列中处理更新，防止多线程问题
        while not self.queue.empty():
            task = self.queue.get()
            task()
        self.root.after(100, self.process_queue)

    def run(self):
        try:
            # 设置关闭窗口的处理
            self.root.protocol("WM_DELETE_WINDOW", self.quit_window)
            self.root.deiconify()  # 初始化完成后显示窗口
            # 确保在窗口完全显示后再创建系统托盘
            self.create_system_tray()
            # 启动主循环
            self.root.mainloop()
        except Exception as e:
            # print(f"Error in main loop: {e}")
            self.quit_window()

if __name__ == "__main__":
    multiprocessing.freeze_support()
    try:
        root = tk.Tk()
        root.withdraw()  # 隐藏主窗口，直到完全初始化
        app = SystemMonitor(root)
        root.deiconify()  # 初始化完成后显示窗口
        app.run()

    except Exception as e:
        # print(f"Fatal error: {e}")
        sys.exit(1)