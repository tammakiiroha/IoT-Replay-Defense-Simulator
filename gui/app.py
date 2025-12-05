"""
主应用程序类
Main simulation GUI application
"""

import os
import platform
import queue
import signal
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog

from .theme import COLORS, FONTS
from .translations import TRANSLATIONS
from .panels import create_scenario_panel, create_config_panel, create_output_panel


class SimulationGUI:
    """重放攻击仿真 GUI 主类"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Replay Attack Defense Evaluation System")
        self.root.geometry("1400x900")
        self.root.configure(bg=COLORS["bg_main"])
        
        self.current_lang = tk.StringVar(value="en")
        self.output_queue = queue.Queue()
        self.running = False
        self.current_process = None
        
        # 这些变量将由 config_panel 初始化
        self.defense_var = None
        self.attack_mode_var = None
        self.runs_var = None
        self.num_legit_var = None
        self.num_replay_var = None
        self.ploss_var = None
        self.preorder_var = None
        self.window_size_var = None
        self.seed_var = None
        self.attacker_loss_var = None
        
        # UI 组件
        self.output_text = None
        self.status_label = None
        self.stop_button = None
        
        self.setup_style()
        self.create_widgets()
        self.check_output()
    
    def t(self, key):
        """获取翻译"""
        return TRANSLATIONS[self.current_lang.get()].get(key, key)
    
    def setup_style(self):
        """配置样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # 单选按钮样式
        style.configure("Academic.TRadiobutton",
                       background=COLORS["bg_card"],
                       foreground=COLORS["text_primary"],
                       font=FONTS["body"],
                       borderwidth=0)
        style.map("Academic.TRadiobutton",
                 background=[('active', COLORS["bg_card"])],
                 foreground=[('active', COLORS["primary"])])
        
        # 滑动条样式
        style.configure("Academic.Horizontal.TScale",
                       background=COLORS["bg_card"],
                       troughcolor=COLORS["bg_section"],
                       borderwidth=0,
                       lightcolor=COLORS["accent"],
                       darkcolor=COLORS["accent"])
    
    def create_widgets(self):
        """创建主界面"""
        
        # === 顶部标题区 ===
        header = tk.Frame(self.root, bg=COLORS["primary"], height=160)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        header_content = tk.Frame(header, bg=COLORS["primary"])
        header_content.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(
            header_content,
            text=self.t("title"),
            font=FONTS["title"],
            fg=COLORS["text_light"],
            bg=COLORS["primary"]
        ).pack()
        
        tk.Label(
            header_content,
            text=self.t("subtitle"),
            font=FONTS["subtitle"],
            fg=COLORS["accent"],
            bg=COLORS["primary"]
        ).pack(pady=(8, 4))
        
        tk.Label(
            header_content,
            text=self.t("tagline"),
            font=FONTS["small"],
            fg=COLORS["text_light"],
            bg=COLORS["primary"]
        ).pack()
        
        # 语言切换器（右上角）
        lang_frame = tk.Frame(header, bg=COLORS["primary"])
        lang_frame.place(relx=0.95, rely=0.5, anchor="e")
        
        tk.Label(
            lang_frame,
            text=self.t("language"),
            font=FONTS["small"],
            fg=COLORS["text_light"],
            bg=COLORS["primary"]
        ).pack(side=tk.LEFT, padx=(0, 8))
        
        for code, name in [("en", "EN"), ("zh", "中"), ("ja", "日")]:
            is_active = self.current_lang.get() == code
            btn = tk.Label(
                lang_frame,
                text=name,
                font=FONTS["small"],
                fg=COLORS["accent"] if is_active else COLORS["text_light"],
                bg=COLORS["primary"],
                cursor="hand2",
                padx=8,
                pady=4
            )
            btn.pack(side=tk.LEFT, padx=2)
            if not is_active:
                btn.bind("<Button-1>", lambda e, lc=code: self.switch_language(lc))
        
        # === 主内容区 ===
        main = tk.Frame(self.root, bg=COLORS["bg_main"])
        main.pack(fill=tk.BOTH, expand=True, padx=30, pady=25)
        
        # 左侧：实验场景 + 配置
        left = tk.Frame(main, bg=COLORS["bg_main"], width=480)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left.pack_propagate(False)
        
        # 右侧：输出
        right = tk.Frame(main, bg=COLORS["bg_main"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 使用模块化的面板创建函数
        create_scenario_panel(left, self)
        create_config_panel(left, self)
        create_output_panel(right, self)
    
    def switch_language(self, lang_code):
        """切换语言"""
        self.current_lang.set(lang_code)
        for widget in self.root.winfo_children():
            widget.destroy()
        self.create_widgets()
    
    # === 业务逻辑 ===
    
    def run_scenario(self, scenario):
        """运行预设场景"""
        scenarios = {
            "quick": ("Quick Test", "--modes window --runs 30 --num-legit 10 --num-replay 50 --p-loss 0.05"),
            "baseline": ("Baseline", "--modes no_def rolling window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.0 --p-reorder 0.0"),
            "packet_loss": ("Packet Loss", "--modes rolling window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.1 --p-reorder 0.0"),
            "reorder": ("Reordering", "--modes rolling window --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.0 --p-reorder 0.3"),
            "harsh": ("Harsh Network", "--modes window challenge --runs 100 --num-legit 20 --num-replay 100 --p-loss 0.15 --p-reorder 0.3"),
        }
        name, cmd = scenarios[scenario]
        self.run_command(cmd, name)
    
    def run_custom(self):
        """运行自定义配置"""
        defense_map = {
            "all": "no_def rolling window challenge",
            "no_def": "no_def",
            "rolling": "rolling",
            "window": "window",
            "challenge": "challenge"
        }
        modes = defense_map[self.defense_var.get()]
        
        cmd_parts = [
            f"--modes {modes}",
            f"--runs {self.runs_var.get()}",
            f"--num-legit {self.num_legit_var.get()}",
            f"--num-replay {self.num_replay_var.get()}",
            f"--p-loss {self.ploss_var.get()}",
            f"--p-reorder {self.preorder_var.get()}",
            f"--window-size {self.window_size_var.get()}",
            f"--attack-mode {self.attack_mode_var.get()}",
            f"--attacker-loss {self.attacker_loss_var.get()}",
        ]
        
        if self.seed_var.get() != 0:
            cmd_parts.append(f"--seed {self.seed_var.get()}")
        
        cmd = " ".join(cmd_parts)
        self.run_command(cmd, self.t("custom_exp"))
    
    def run_command(self, args, description):
        """执行仿真命令"""
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        
        self.running = True
        self.set_status(True, f"{self.t('status_running')}: {description}")
        self.stop_button.pack(side=tk.RIGHT, padx=(0, 5))
        
        self.output_text.insert(tk.END, f"\n{'='*70}\n▶ EXPERIMENT: {description}\n{'='*70}\n\n")
        self.output_text.see(tk.END)
        
        def run_thread():
            try:
                cmd = f"source .venv/bin/activate && python main.py {args}"
                self.current_process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    executable='/bin/bash',
                    preexec_fn=None if platform.system() == "Windows" else lambda: None
                )
                for line in self.current_process.stdout:
                    if not self.running:
                        break
                    self.output_queue.put(line)
                
                returncode = self.current_process.wait()
                if returncode == 0:
                    self.output_queue.put(f"\n✓ {self.t('done')}\n")
                elif returncode == -15 or returncode == -9:
                    self.output_queue.put(f"\n⚠ Experiment stopped by user\n")
                else:
                    self.output_queue.put(f"\n✗ Process exited with code {returncode}\n")
            except Exception as e:
                self.output_queue.put(f"\n✗ {self.t('error')}: {e}\n")
            finally:
                self.current_process = None
                self.running = False
                self.set_status(False)
                self.stop_button.pack_forget()
        
        threading.Thread(target=run_thread, daemon=True).start()
    
    def generate_plots(self):
        """生成图表"""
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        
        if not os.path.exists("results") or not os.listdir("results"):
            messagebox.showwarning("Warning", self.t("no_results"))
            return
        
        self.running = True
        self.set_status(True, self.t("generate_plots"))
        
        def run():
            try:
                result = subprocess.run(
                    "source .venv/bin/activate && python scripts/plot_results.py",
                    shell=True,
                    executable='/bin/bash',
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.output_queue.put(f"✓ {self.t('generate_plots')} {self.t('done')}\n")
                else:
                    self.output_queue.put(f"✗ Error: {result.stderr}\n")
            except Exception as e:
                self.output_queue.put(f"✗ {self.t('error')}: {e}\n")
            finally:
                self.running = False
                self.set_status(False)
        
        threading.Thread(target=run, daemon=True).start()
    
    def export_tables(self):
        """导出表格"""
        if self.running:
            messagebox.showwarning("Busy", self.t("busy_msg"))
            return
        
        if not os.path.exists("results") or not os.listdir("results"):
            messagebox.showwarning("Warning", self.t("no_results"))
            return
        
        self.running = True
        self.set_status(True, self.t("export_tables"))
        
        def run():
            try:
                result = subprocess.run(
                    "source .venv/bin/activate && python scripts/export_tables.py",
                    shell=True,
                    executable='/bin/bash',
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.output_queue.put(f"✓ {self.t('export_tables')} {self.t('done')}\n")
                else:
                    self.output_queue.put(f"✗ Error: {result.stderr}\n")
            except Exception as e:
                self.output_queue.put(f"✗ {self.t('error')}: {e}\n")
            finally:
                self.running = False
                self.set_status(False)
        
        threading.Thread(target=run, daemon=True).start()
    
    def stop_experiment(self):
        """停止当前运行的实验"""
        if not self.running or not self.current_process:
            return
        
        if messagebox.askyesno("Confirm", self.t("confirm_stop")):
            try:
                if platform.system() != "Windows":
                    os.killpg(os.getpgid(self.current_process.pid), signal.SIGTERM)
                else:
                    self.current_process.terminate()
                
                self.running = False
                self.output_queue.put("\n⚠ Stopping experiment...\n")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to stop: {e}")
    
    def save_output(self):
        """保存输出到文件"""
        content = self.output_text.get(1.0, tk.END).strip()
        if not content:
            messagebox.showinfo("Info", "No output to save")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"simulation_output_{timestamp}.txt"
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_name
        )
        
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("Success", f"{self.t('saved')}\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save: {e}")
    
    def clear_output(self):
        """清空输出"""
        self.output_text.delete(1.0, tk.END)
    
    def set_status(self, is_running, text=None):
        """设置状态"""
        if text:
            self.status_label.config(text=f"● {text}")
        else:
            self.status_label.config(text=f"● {self.t('status_ready')}")
        
        if is_running:
            self.status_label.config(fg=COLORS["warning"])
        else:
            self.status_label.config(fg=COLORS["success"])
    
    def check_output(self):
        """检查输出队列"""
        try:
            while True:
                line = self.output_queue.get_nowait()
                self.output_text.insert(tk.END, line)
                self.output_text.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(100, self.check_output)


def main():
    """入口函数"""
    root = tk.Tk()
    app = SimulationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
