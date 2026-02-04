"""
鲸介12306 抢票助手 - 桌面端 GUI 应用

开发者：鲸介 (Whale_DIY)
项目：12306 智能抢票系统
开源协议：MIT License
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import json
import os
import threading
import sys
from datetime import datetime
from pathlib import Path

# 导入核心抢票脚本
from booking_core import setup_browser_and_login, run_booking_with_driver

CONFIG_PATH = 'config.json'


class TicketBookingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("桃叔12306 抢票助手 v1.0")
        self.root.geometry("700x850")
        self.root.resizable(False, False)
        
        # 设置图标（如果存在）
        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass
        
        self.booking_thread = None
        self.is_booking = False
        self.driver = None  # 保存浏览器实例
        self.is_logged_in = False  # 登录状态标记
        
        self.setup_ui()
        self.load_config()
    
    def setup_ui(self):
        """构建用户界面"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 标题
        title_label = ttk.Label(main_frame, text="🚄 桃叔12306 抢票助手", 
                                font=("微软雅黑", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # 基础信息区域
        self.create_basic_info_section(main_frame, start_row=1)
        
        # 高级选项区域
        self.create_advanced_options_section(main_frame, start_row=7)
        
        # 钉钉机器人配置区域
        self.create_dingtalk_section(main_frame, start_row=12)
        
        # 操作按钮区域
        self.create_action_buttons(main_frame, start_row=13)
        
        # 日志输出区域
        self.create_log_section(main_frame, start_row=14)
        
        # 状态栏
        self.create_status_bar(main_frame, start_row=15)
    
    def create_basic_info_section(self, parent, start_row):
        """创建基础信息输入区域"""
        section_frame = ttk.LabelFrame(parent, text="基础信息", padding="10")
        section_frame.grid(row=start_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 出发站
        ttk.Label(section_frame, text="出发站:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.from_station_var = tk.StringVar(value="广州南")
        ttk.Entry(section_frame, textvariable=self.from_station_var, width=25).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # 到达站
        ttk.Label(section_frame, text="到达站:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.to_station_var = tk.StringVar(value="深圳北")
        ttk.Entry(section_frame, textvariable=self.to_station_var, width=25).grid(row=1, column=1, sticky=tk.W, padx=5)
        
        # 出发日期
        ttk.Label(section_frame, text="出发日期:").grid(row=2, column=0, sticky=tk.W, pady=5)
        date_frame = ttk.Frame(section_frame)
        date_frame.grid(row=2, column=1, sticky=tk.W, padx=5)
        self.travel_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        ttk.Entry(date_frame, textvariable=self.travel_date_var, width=15).pack(side=tk.LEFT)
        ttk.Label(date_frame, text="(格式: YYYY-MM-DD)", foreground="gray").pack(side=tk.LEFT, padx=5)
        
        # 票型
        ttk.Label(section_frame, text="票型:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.ticket_type_var = tk.StringVar(value="adult")
        ticket_frame = ttk.Frame(section_frame)
        ticket_frame.grid(row=3, column=1, sticky=tk.W, padx=5)
        ttk.Radiobutton(ticket_frame, text="成人票", variable=self.ticket_type_var, 
                       value="adult").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(ticket_frame, text="学生票", variable=self.ticket_type_var, 
                       value="student").pack(side=tk.LEFT)
        
        # 席别
        ttk.Label(section_frame, text="席别:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.seat_category_var = tk.StringVar(value="二等座")
        seat_combo = ttk.Combobox(section_frame, textvariable=self.seat_category_var, 
                                  values=["二等座", "一等座", "商务座", "硬座", "硬卧", "软卧", "一等卧", "二等卧"], 
                                  width=22, state="readonly")
        seat_combo.grid(row=4, column=1, sticky=tk.W, padx=5)
        
        # 乘车人姓名
        ttk.Label(section_frame, text="乘车人:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.passenger_name_var = tk.StringVar(value="张航铭")
        ttk.Entry(section_frame, textvariable=self.passenger_name_var, width=25).grid(row=5, column=1, sticky=tk.W, padx=5)
    
    def create_advanced_options_section(self, parent, start_row):
        """创建高级选项区域"""
        section_frame = ttk.LabelFrame(parent, text="高级选项", padding="10")
        section_frame.grid(row=start_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 抢票策略选择
        ttk.Label(section_frame, text="抢票策略:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.strategy_var = tk.StringVar(value="time_range")
        strategy_frame = ttk.Frame(section_frame)
        strategy_frame.grid(row=0, column=1, sticky=tk.W, padx=5)
        ttk.Radiobutton(strategy_frame, text="时间范围", variable=self.strategy_var, 
                       value="time_range", command=self.on_strategy_change).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(strategy_frame, text="指定车次", variable=self.strategy_var, 
                       value="train_number", command=self.on_strategy_change).pack(side=tk.LEFT)
        
        # 时间范围输入
        self.time_range_frame = ttk.Frame(section_frame)
        self.time_range_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Label(self.time_range_frame, text="出发时间范围:").pack(side=tk.LEFT)
        self.start_time_var = tk.StringVar(value="07:00")
        ttk.Entry(self.time_range_frame, textvariable=self.start_time_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(self.time_range_frame, text="至").pack(side=tk.LEFT)
        self.end_time_var = tk.StringVar(value="09:00")
        ttk.Entry(self.time_range_frame, textvariable=self.end_time_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(self.time_range_frame, text="(格式: HH:MM)", foreground="gray").pack(side=tk.LEFT)
        
        # 指定车次输入
        self.train_number_frame = ttk.Frame(section_frame)
        self.train_number_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=5)
        ttk.Label(self.train_number_frame, text="目标车次:").pack(side=tk.LEFT)
        self.target_train_var = tk.StringVar(value="")
        ttk.Entry(self.train_number_frame, textvariable=self.target_train_var, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(self.train_number_frame, text="(如: G1234)", foreground="gray").pack(side=tk.LEFT)
        self.train_number_frame.grid_remove()  # 默认隐藏
        
        # 选座偏好
        ttk.Label(section_frame, text="选座偏好:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.seat_position_var = tk.StringVar(value="first")
        position_combo = ttk.Combobox(section_frame, textvariable=self.seat_position_var, 
                                     values=["first", "window", "aisle"], 
                                     width=22, state="readonly")
        position_combo.grid(row=3, column=1, sticky=tk.W, padx=5)
        
        # 开售时间
        ttk.Label(section_frame, text="开售时间:").grid(row=4, column=0, sticky=tk.W, pady=5)
        booking_time_frame = ttk.Frame(section_frame)
        booking_time_frame.grid(row=4, column=1, sticky=tk.W, padx=5)
        self.booking_start_time_var = tk.StringVar(value="")
        ttk.Entry(booking_time_frame, textvariable=self.booking_start_time_var, width=20).pack(side=tk.LEFT)
        ttk.Label(booking_time_frame, text="(可留空)", foreground="gray").pack(side=tk.LEFT, padx=5)
        ttk.Label(section_frame, text="", foreground="gray").grid(row=5, column=1, sticky=tk.W, padx=5)
        ttk.Label(section_frame, text="格式: YYYY-MM-DD HH:MM:SS", foreground="gray").grid(row=5, column=1, sticky=tk.W, padx=5)
    
    def create_action_buttons(self, parent, start_row):
        """创建操作按钮区域"""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=start_row, column=0, columnspan=2, pady=10)
        
        # 第一行按钮：预登录
        login_frame = ttk.Frame(button_frame)
        login_frame.pack(pady=5)
        
        self.login_button = ttk.Button(login_frame, text="🔐 预登录12306", 
                                       command=self.pre_login, width=20)
        self.login_button.pack(side=tk.LEFT, padx=5)
        
        self.login_status_label = ttk.Label(login_frame, text="未登录", foreground="red")
        self.login_status_label.pack(side=tk.LEFT, padx=10)
        
        # 第二行按钮：抢票控制
        booking_frame = ttk.Frame(button_frame)
        booking_frame.pack(pady=5)
        
        self.start_button = ttk.Button(booking_frame, text="🚀 开始抢票", 
                                       command=self.start_booking, width=15)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(booking_frame, text="⏹ 停止", 
                                      command=self.stop_booking, width=15, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # 第三行按钮：配置管理
        config_frame = ttk.Frame(button_frame)
        config_frame.pack(pady=5)
        
        ttk.Button(config_frame, text="💾 保存配置", 
                  command=self.save_config, width=15).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(config_frame, text="📂 加载配置", 
                  command=self.load_config, width=15).pack(side=tk.LEFT, padx=5)
    
    def create_log_section(self, parent, start_row):
        """创建日志输出区域"""
        log_frame = ttk.LabelFrame(parent, text="运行日志", padding="5")
        log_frame.grid(row=start_row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=80, 
                                                   wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 重定向标准输出到日志窗口
        sys.stdout = TextRedirector(self.log_text, "stdout")
    
    def create_status_bar(self, parent, start_row):
        """创建状态栏"""
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(parent, textvariable=self.status_var, 
                              relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=start_row, column=0, columnspan=2, sticky=(tk.W, tk.E))
    
    def create_dingtalk_section(self, parent, start_row):
        """创建钉钉机器人配置区域"""
        section_frame = ttk.LabelFrame(parent, text="钉钉机器人配置", padding="10")
        section_frame.grid(row=start_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 钉钉机器人Token
        ttk.Label(section_frame, text="钉钉机器人Token:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.dingtalk_token_var = tk.StringVar(value="59a5435eb19966e52544ea4c8b3dda69bb0923e1c6d03f8bfda6b12b02a9f10f")
        ttk.Entry(section_frame, textvariable=self.dingtalk_token_var, width=50).grid(row=0, column=1, sticky=tk.W, padx=5)
        
        # 钉钉机器人Secret（用于加签）
        ttk.Label(section_frame, text="钉钉机器人Secret:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.dingtalk_secret_var = tk.StringVar(value="SEC0114e8018102ac44af2377745892f43ec74f54147ea4982c75564a23294c1c47")
        ttk.Entry(section_frame, textvariable=self.dingtalk_secret_var, width=50).grid(row=1, column=1, sticky=tk.W, padx=5)
    
    def on_strategy_change(self):
        """策略切换时的回调"""
        if self.strategy_var.get() == "time_range":
            self.time_range_frame.grid()
            self.train_number_frame.grid_remove()
        else:
            self.time_range_frame.grid_remove()
            self.train_number_frame.grid()
    
    def pre_login(self):
        """预登录功能：提前打开浏览器让用户登录"""
        if self.is_logged_in:
            if not messagebox.askyesno("重新登录", "已经登录过了，是否重新登录？"):
                return
            # 关闭旧的浏览器
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
                self.is_logged_in = False
        
        self.login_button.config(state=tk.DISABLED)
        self.login_status_label.config(text="正在打开浏览器...", foreground="orange")
        self.log_text.delete(1.0, tk.END)
        
        # 在新线程中执行登录
        threading.Thread(target=self.run_pre_login, daemon=True).start()
    
    def run_pre_login(self):
        """在后台线程中执行预登录"""
        try:
            from booking_core import setup_browser_and_login
            
            print("=" * 60)
            print("🔐 预登录12306")
            print("=" * 60)
            
            self.driver = setup_browser_and_login()
            
            if self.driver:
                self.is_logged_in = True
                self.root.after(0, lambda: self.login_status_label.config(text="✓ 已登录", foreground="green"))
                self.root.after(0, lambda: self.login_button.config(state=tk.NORMAL))
                print("\n✓ 登录成功！现在可以开始抢票了")
                print("=" * 60)
            else:
                self.root.after(0, lambda: self.login_status_label.config(text="✗ 登录失败", foreground="red"))
                self.root.after(0, lambda: self.login_button.config(state=tk.NORMAL))
                print("\n✗ 登录失败，请重试")
        except Exception as e:
            print(f"预登录出错: {e}")
            self.root.after(0, lambda: self.login_status_label.config(text="✗ 登录失败", foreground="red"))
            self.root.after(0, lambda: self.login_button.config(state=tk.NORMAL))
    
    def get_params(self):
        """获取当前界面参数"""
        params = {
            'from_station': self.from_station_var.get().strip(),
            'to_station': self.to_station_var.get().strip(),
            'travel_date': self.travel_date_var.get().strip(),
            'ticket_type': self.ticket_type_var.get(),
            'seat_category': self.seat_category_var.get(),
            'seat_position_preference': self.seat_position_var.get(),
            'booking_start_time': self.booking_start_time_var.get().strip(),
            'passenger_name': self.passenger_name_var.get().strip(),
            'dingtalk_token': self.dingtalk_token_var.get().strip(),
            'dingtalk_secret': self.dingtalk_secret_var.get().strip(),
        }
        
        if self.strategy_var.get() == "time_range":
            params['depart_time_range'] = {
                'start': self.start_time_var.get().strip(),
                'end': self.end_time_var.get().strip()
            }
            params['target_train_number'] = ''
        else:
            params['target_train_number'] = self.target_train_var.get().strip().upper()
            params['depart_time_range'] = {'start': '00:00', 'end': '23:59'}
        
        return params
    
    def validate_params(self, params):
        """验证参数有效性"""
        if not params['from_station']:
            messagebox.showerror("参数错误", "请输入出发站")
            return False
        if not params['to_station']:
            messagebox.showerror("参数错误", "请输入到达站")
            return False
        if not params['travel_date']:
            messagebox.showerror("参数错误", "请输入出发日期")
            return False
        
        # 验证日期格式
        try:
            datetime.strptime(params['travel_date'], '%Y-%m-%d')
        except:
            messagebox.showerror("参数错误", "出发日期格式错误，应为 YYYY-MM-DD")
            return False
        
        # 验证开售时间格式（如果填写了）
        if params['booking_start_time']:
            try:
                datetime.strptime(params['booking_start_time'], '%Y-%m-%d %H:%M:%S')
            except:
                messagebox.showerror("参数错误", "开售时间格式错误，应为 YYYY-MM-DD HH:MM:SS")
                return False
        
        return True
    
    def start_booking(self):
        """开始抢票"""
        # 检查是否已登录
        if not self.is_logged_in or not self.driver:
            messagebox.showwarning("未登录", "请先点击【预登录12306】按钮完成登录！")
            return
        
        params = self.get_params()
        
        if not self.validate_params(params):
            return
        
        # 确认对话框
        msg = f"确认开始抢票？\n\n"
        msg += f"出发站: {params['from_station']}\n"
        msg += f"到达站: {params['to_station']}\n"
        msg += f"日期: {params['travel_date']}\n"
        if params['target_train_number']:
            msg += f"车次: {params['target_train_number']}\n"
        else:
            msg += f"时间: {params['depart_time_range']['start']} - {params['depart_time_range']['end']}\n"
        
        if not messagebox.askyesno("确认抢票", msg):
            return
        
        self.is_booking = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.login_button.config(state=tk.DISABLED)
        self.status_var.set("抢票中...")
        
        # 在新线程中运行抢票
        self.booking_thread = threading.Thread(target=self.run_booking, args=(params,), daemon=True)
        self.booking_thread.start()
    
    def run_booking(self, params):
        """在后台线程中运行抢票逻辑"""
        try:
            from booking_core import run_booking_with_driver
            run_booking_with_driver(self.driver, params)
        except Exception as e:
            print(f"抢票过程出错: {e}")
            messagebox.showerror("错误", f"抢票过程出错: {e}")
        finally:
            self.is_booking = False
            self.root.after(0, self.on_booking_finished)
    
    def stop_booking(self):
        """停止抢票"""
        if messagebox.askyesno("确认", "确定要停止抢票吗？"):
            self.is_booking = False
            self.status_var.set("已停止")
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            print("\n用户手动停止抢票")
    
    def on_booking_finished(self):
        """抢票完成后的回调"""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.login_button.config(state=tk.NORMAL)
        self.status_var.set("就绪")
    
    def save_config(self):
        """保存配置到文件"""
        params = self.get_params()
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(params, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", f"配置已保存到 {os.path.abspath(CONFIG_PATH)}")
            print(f"配置已保存到: {os.path.abspath(CONFIG_PATH)}")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {e}")
    
    def load_config(self):
        """从文件加载配置"""
        if not os.path.exists(CONFIG_PATH):
            return
        
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                params = json.load(f)
            
            self.from_station_var.set(params.get('from_station', ''))
            self.to_station_var.set(params.get('to_station', ''))
            self.travel_date_var.set(params.get('travel_date', ''))
            self.ticket_type_var.set(params.get('ticket_type', 'adult'))
            self.seat_category_var.set(params.get('seat_category', '二等座'))
            self.seat_position_var.set(params.get('seat_position_preference', 'first'))
            self.booking_start_time_var.set(params.get('booking_start_time', ''))
            self.passenger_name_var.set(params.get('passenger_name', '张航铭'))
            self.dingtalk_token_var.set(params.get('dingtalk_token', '59a5435eb19966e52544ea4c8b3dda69bb0923e1c6d03f8bfda6b12b02a9f10f'))
            self.dingtalk_secret_var.set(params.get('dingtalk_secret', 'SEC0114e8018102ac44af2377745892f43ec74f54147ea4982c75564a23294c1c47'))
            
            # 加载策略相关参数
            if params.get('target_train_number'):
                self.strategy_var.set('train_number')
                self.target_train_var.set(params['target_train_number'])
                self.on_strategy_change()
            else:
                self.strategy_var.set('time_range')
                tr = params.get('depart_time_range', {})
                if isinstance(tr, dict):
                    self.start_time_var.set(tr.get('start', '07:00'))
                    self.end_time_var.set(tr.get('end', '09:00'))
                self.on_strategy_change()
            
            print(f"已加载配置: {os.path.abspath(CONFIG_PATH)}")
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败: {e}")


class TextRedirector:
    """将标准输出重定向到 Text 组件"""
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag
    
    def write(self, text):
        self.widget.insert(tk.END, text)
        self.widget.see(tk.END)
    
    def flush(self):
        pass


def main():
    root = tk.Tk()
    app = TicketBookingApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
