#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Лаунчер для управления FacePanel проектом
Запуск/остановка Java Web приложения и Python скриптов kpp1/kpp2
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import os
import sys
import re
import threading
from pathlib import Path

# Пути к файлам проекта
PROJECT_ROOT = Path(__file__).parent.absolute()
OPENCV_DIR = PROJECT_ROOT / "OpenCVRework"
VENV_PYTHON = OPENCV_DIR / "venv" / "Scripts" / "python.exe"
KPP1_SCRIPT = OPENCV_DIR / "face_kpp1.py"
KPP2_SCRIPT = OPENCV_DIR / "face_kpp2.py"
POM_XML = PROJECT_ROOT / "pom.xml"
TARGET_DIR = PROJECT_ROOT / "target"

# Процессы
java_process = None
kpp1_process = None
kpp2_process = None


class LauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FacePanel Launcher - Lahmut Group")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        # Цветовая палитра Lahmut Group
        self.colors = {
            'bg_primary': '#0E0E0E',
            'bg_primary_alt': '#111111',
            'bg_secondary': '#262626',
            'bg_secondary_alt': '#2A2A2A',
            'accent_primary': '#C9B37E',
            'accent_primary_alt': '#D2BE8A',
            'accent_hover': '#B8A06A',
            'text_primary': '#EDEDED',
            'text_secondary': '#B0B0B0',
            'text_muted': '#888888',
            'border_subtle': '#3A3A3A',
            'status_stopped': '#C86464',
            'status_running': '#C9B37E'
        }
        
        # Настройка фона окна
        self.root.configure(bg=self.colors['bg_primary'])
        
        # Переменные для IP адресов
        self.kpp1_ip_var = tk.StringVar()
        self.kpp2_ip_var = tk.StringVar()
        
        self.setup_ui()
        self.load_camera_ips()
        
    def configure_styles(self, style):
        """Настройка стилей ttk в соответствии с палитрой Lahmut Group"""
        # LabelFrame
        style.configure('TLabelframe', 
                       background=self.colors['bg_primary'],
                       foreground=self.colors['text_primary'],
                       borderwidth=1,
                       relief=tk.SOLID)
        style.configure('TLabelframe.Label',
                       background=self.colors['bg_primary'],
                       foreground=self.colors['accent_primary'],
                       font=('Segoe UI', 10, 'bold'))
        
        # Frame
        style.configure('TFrame',
                       background=self.colors['bg_primary'])
        
        # Label
        style.configure('TLabel',
                       background=self.colors['bg_primary'],
                       foreground=self.colors['text_primary'],
                       font=('Segoe UI', 9))
        
        # Button - обычные кнопки
        style.configure('TButton',
                       background=self.colors['bg_secondary'],
                       foreground=self.colors['text_primary'],
                       borderwidth=1,
                       relief=tk.SOLID,
                       padding=(12, 6),
                       font=('Segoe UI', 9))
        style.map('TButton',
                 background=[('active', self.colors['bg_secondary_alt']),
                           ('pressed', self.colors['bg_secondary'])],
                 border=[('active', self.colors['accent_primary']),
                        ('pressed', self.colors['accent_primary'])],
                 foreground=[('active', self.colors['accent_primary'])])
        
        # Button - акцентные кнопки (запуск)
        style.configure('Accent.TButton',
                       background=self.colors['accent_primary'],
                       foreground=self.colors['bg_primary'],
                       borderwidth=1,
                       relief=tk.SOLID,
                       padding=(12, 6),
                       font=('Segoe UI', 9, 'bold'))
        style.map('Accent.TButton',
                 background=[('active', self.colors['accent_hover']),
                           ('pressed', self.colors['accent_primary'])],
                 border=[('active', self.colors['accent_hover']),
                        ('pressed', self.colors['accent_primary'])],
                 foreground=[('active', self.colors['bg_primary'])])
        
        # Entry
        style.configure('TEntry',
                       fieldbackground=self.colors['bg_secondary'],
                       foreground=self.colors['text_primary'],
                       borderwidth=1,
                       relief=tk.SOLID,
                       insertcolor=self.colors['accent_primary'])
        style.map('TEntry',
                 fieldbackground=[('focus', self.colors['bg_secondary_alt'])],
                 border=[('focus', self.colors['accent_primary'])])
    
    def setup_ui(self):
        # Настройка стилей ttk
        style = ttk.Style()
        style.theme_use('clam')
        
        # Настройка цветов для всех виджетов
        self.configure_styles(style)
        
        # Главный фрейм
        main_frame = tk.Frame(self.root, bg=self.colors['bg_primary'], padx=20, pady=20)
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # Заголовок с логотипом
        header_frame = tk.Frame(main_frame, bg=self.colors['bg_primary'])
        header_frame.grid(row=0, column=0, columnspan=3, pady=(0, 25), sticky=(tk.W, tk.E))
        main_frame.columnconfigure(0, weight=1)
        
        title_label = tk.Label(header_frame, 
                              text="FacePanel Launcher", 
                              font=("Segoe UI", 20, "bold"),
                              bg=self.colors['bg_primary'],
                              fg=self.colors['text_primary'])
        title_label.pack(side=tk.LEFT)
        
        subtitle_label = tk.Label(header_frame,
                                 text="Lahmut Group",
                                 font=("Segoe UI", 11),
                                 bg=self.colors['bg_primary'],
                                 fg=self.colors['accent_primary'])
        subtitle_label.pack(side=tk.LEFT, padx=(10, 0))
        
        header_frame.columnconfigure(0, weight=1)
        
        # === Java Web Application ===
        java_frame = ttk.LabelFrame(main_frame, text="Java Web Application (Панель)", padding="15")
        java_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=8)
        java_frame.columnconfigure(1, weight=1)
        
        self.java_status_label = tk.Label(java_frame, 
                                         text="Статус: Остановлен", 
                                         bg=self.colors['bg_primary'],
                                         fg=self.colors['status_stopped'],
                                         font=('Segoe UI', 9, 'bold'))
        self.java_status_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        java_btn_frame = ttk.Frame(java_frame)
        java_btn_frame.grid(row=1, column=0, columnspan=2, pady=5)
        
        self.java_start_btn = ttk.Button(java_btn_frame, text="▶ Запустить", 
                                        command=self.start_java, width=18, style='Accent.TButton')
        self.java_start_btn.pack(side=tk.LEFT, padx=6)
        
        self.java_stop_btn = ttk.Button(java_btn_frame, text="⏹ Остановить", 
                                       command=self.stop_java, width=18, state=tk.DISABLED)
        self.java_stop_btn.pack(side=tk.LEFT, padx=6)
        
        # === Python Script KPP1 ===
        kpp1_frame = ttk.LabelFrame(main_frame, text="Python Script KPP1", padding="15")
        kpp1_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=8)
        kpp1_frame.columnconfigure(1, weight=1)
        
        self.kpp1_status_label = tk.Label(kpp1_frame, 
                                          text="Статус: Остановлен", 
                                          bg=self.colors['bg_primary'],
                                          fg=self.colors['status_stopped'],
                                          font=('Segoe UI', 9, 'bold'))
        self.kpp1_status_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # IP адрес для KPP1
        ip_label1 = tk.Label(kpp1_frame, 
                            text="IP адрес камеры:",
                            bg=self.colors['bg_primary'],
                            fg=self.colors['text_primary'],
                            font=('Segoe UI', 9))
        ip_label1.grid(row=1, column=0, sticky=tk.W, pady=5)
        kpp1_ip_entry = ttk.Entry(kpp1_frame, textvariable=self.kpp1_ip_var, width=40)
        kpp1_ip_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        kpp1_btn_frame = ttk.Frame(kpp1_frame)
        kpp1_btn_frame.grid(row=2, column=0, columnspan=2, pady=5)
        
        self.kpp1_start_btn = ttk.Button(kpp1_btn_frame, text="▶ Запустить", 
                                         command=self.start_kpp1, width=18, style='Accent.TButton')
        self.kpp1_start_btn.pack(side=tk.LEFT, padx=6)
        
        self.kpp1_stop_btn = ttk.Button(kpp1_btn_frame, text="⏹ Остановить", 
                                        command=self.stop_kpp1, width=18, state=tk.DISABLED)
        self.kpp1_stop_btn.pack(side=tk.LEFT, padx=6)
        
        ttk.Button(kpp1_btn_frame, text="💾 Сохранить IP", 
                  command=self.save_kpp1_ip, width=18).pack(side=tk.LEFT, padx=6)
        
        # === Python Script KPP2 ===
        kpp2_frame = ttk.LabelFrame(main_frame, text="Python Script KPP2", padding="15")
        kpp2_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=8)
        kpp2_frame.columnconfigure(1, weight=1)
        
        self.kpp2_status_label = tk.Label(kpp2_frame, 
                                          text="Статус: Остановлен", 
                                          bg=self.colors['bg_primary'],
                                          fg=self.colors['status_stopped'],
                                          font=('Segoe UI', 9, 'bold'))
        self.kpp2_status_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # IP адрес для KPP2
        ip_label2 = tk.Label(kpp2_frame, 
                            text="IP адрес камеры:",
                            bg=self.colors['bg_primary'],
                            fg=self.colors['text_primary'],
                            font=('Segoe UI', 9))
        ip_label2.grid(row=1, column=0, sticky=tk.W, pady=5)
        kpp2_ip_entry = ttk.Entry(kpp2_frame, textvariable=self.kpp2_ip_var, width=40)
        kpp2_ip_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        
        kpp2_btn_frame = ttk.Frame(kpp2_frame)
        kpp2_btn_frame.grid(row=2, column=0, columnspan=2, pady=5)
        
        self.kpp2_start_btn = ttk.Button(kpp2_btn_frame, text="▶ Запустить", 
                                         command=self.start_kpp2, width=18, style='Accent.TButton')
        self.kpp2_start_btn.pack(side=tk.LEFT, padx=6)
        
        self.kpp2_stop_btn = ttk.Button(kpp2_btn_frame, text="⏹ Остановить", 
                                        command=self.stop_kpp2, width=18, state=tk.DISABLED)
        self.kpp2_stop_btn.pack(side=tk.LEFT, padx=6)
        
        ttk.Button(kpp2_btn_frame, text="💾 Сохранить IP", 
                  command=self.save_kpp2_ip, width=18).pack(side=tk.LEFT, padx=6)
        
        # === Логи ===
        log_frame = ttk.LabelFrame(main_frame, text="Логи", padding="15")
        log_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=8)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, 
            height=10, 
            width=80, 
            wrap=tk.WORD, 
            font=("Consolas", 9),
            bg=self.colors['bg_secondary'],
            fg=self.colors['text_primary'],
            insertbackground=self.colors['accent_primary'],
            selectbackground=self.colors['accent_primary'],
            selectforeground=self.colors['bg_primary'],
            borderwidth=1,
            relief=tk.SOLID,
            highlightthickness=0
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Включаем стандартные горячие клавиши для копирования
        self.log_text.bind("<Control-c>", self.copy_text)
        self.log_text.bind("<Control-a>", self.select_all_text)
        self.log_text.bind("<Button-3>", self.show_context_menu)  # Правый клик
        
        # Кнопки управления логами
        log_btn_frame = ttk.Frame(log_frame)
        log_btn_frame.grid(row=1, column=0, pady=(10, 0))
        
        ttk.Button(log_btn_frame, text="Очистить логи", 
                  command=lambda: self.log_text.delete(1.0, tk.END), width=16).pack(side=tk.LEFT, padx=6)
        ttk.Button(log_btn_frame, text="Копировать", 
                  command=self.copy_selected_text, width=16).pack(side=tk.LEFT, padx=6)
        ttk.Button(log_btn_frame, text="Выделить всё", 
                  command=self.select_all_text, width=16).pack(side=tk.LEFT, padx=6)
        
    def log(self, message):
        """Добавить сообщение в лог"""
        self.log_text.insert(tk.END, f"[{self.get_timestamp()}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
        
    def get_timestamp(self):
        """Получить текущее время"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
    
    def copy_text(self, event=None):
        """Копировать выделенный текст"""
        try:
            if self.log_text.tag_ranges(tk.SEL):
                # Есть выделение - копируем его
                self.root.clipboard_clear()
                self.root.clipboard_append(self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST))
            return "break"
        except:
            return "break"
    
    def copy_selected_text(self):
        """Копировать выделенный текст (кнопка)"""
        try:
            if self.log_text.tag_ranges(tk.SEL):
                self.root.clipboard_clear()
                self.root.clipboard_append(self.log_text.get(tk.SEL_FIRST, tk.SEL_LAST))
                self.log("Текст скопирован в буфер обмена")
            else:
                self.log("Выделите текст для копирования")
        except Exception as e:
            self.log(f"Ошибка копирования: {e}")
    
    def select_all_text(self, event=None):
        """Выделить весь текст"""
        self.log_text.tag_add(tk.SEL, "1.0", tk.END)
        self.log_text.mark_set(tk.INSERT, "1.0")
        self.log_text.see(tk.INSERT)
        return "break"
    
    def show_context_menu(self, event):
        """Показать контекстное меню"""
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="Копировать (Ctrl+C)", command=self.copy_selected_text)
        context_menu.add_command(label="Выделить всё (Ctrl+A)", command=self.select_all_text)
        context_menu.add_separator()
        context_menu.add_command(label="Очистить логи", 
                               command=lambda: self.log_text.delete(1.0, tk.END))
        
        try:
            context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            context_menu.grab_release()
        
    def load_camera_ips(self):
        """Загрузить IP адреса камер из файлов"""
        try:
            # Загрузить из face_kpp1.py
            if KPP1_SCRIPT.exists():
                content = KPP1_SCRIPT.read_text(encoding='utf-8')
                match = re.search(r'face\.CAMERA_URL\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    self.kpp1_ip_var.set(match.group(1))
                    self.log(f"Загружен IP для KPP1: {match.group(1)}")
            
            # Загрузить из face_kpp2.py
            if KPP2_SCRIPT.exists():
                content = KPP2_SCRIPT.read_text(encoding='utf-8')
                match = re.search(r'face\.CAMERA_URL\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    self.kpp2_ip_var.set(match.group(1))
                    self.log(f"Загружен IP для KPP2: {match.group(1)}")
        except Exception as e:
            self.log(f"Ошибка при загрузке IP адресов: {e}")
            
    def save_kpp1_ip(self):
        """Сохранить IP адрес для KPP1"""
        try:
            if not KPP1_SCRIPT.exists():
                messagebox.showerror("Ошибка", f"Файл {KPP1_SCRIPT} не найден!")
                return
                
            new_ip = self.kpp1_ip_var.get().strip()
            if not new_ip:
                messagebox.showerror("Ошибка", "IP адрес не может быть пустым!")
                return
                
            content = KPP1_SCRIPT.read_text(encoding='utf-8')
            # Заменить строку с CAMERA_URL
            pattern = r'(face\.CAMERA_URL\s*=\s*["\'])[^"\']+(["\'][\s]*\n)'
            replacement = r'\1' + new_ip + r'\2'
            new_content = re.sub(pattern, replacement, content)
            
            KPP1_SCRIPT.write_text(new_content, encoding='utf-8')
            self.log(f"IP адрес KPP1 сохранен: {new_ip}")
            messagebox.showinfo("Успех", f"IP адрес KPP1 сохранен: {new_ip}")
        except Exception as e:
            self.log(f"Ошибка при сохранении IP KPP1: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить IP: {e}")
            
    def save_kpp2_ip(self):
        """Сохранить IP адрес для KPP2"""
        try:
            if not KPP2_SCRIPT.exists():
                messagebox.showerror("Ошибка", f"Файл {KPP2_SCRIPT} не найден!")
                return
                
            new_ip = self.kpp2_ip_var.get().strip()
            if not new_ip:
                messagebox.showerror("Ошибка", "IP адрес не может быть пустым!")
                return
                
            content = KPP2_SCRIPT.read_text(encoding='utf-8')
            # Заменить строку с CAMERA_URL
            pattern = r'(face\.CAMERA_URL\s*=\s*["\'])[^"\']+(["\'][\s]*\n)'
            replacement = r'\1' + new_ip + r'\2'
            new_content = re.sub(pattern, replacement, content)
            
            KPP2_SCRIPT.write_text(new_content, encoding='utf-8')
            self.log(f"IP адрес KPP2 сохранен: {new_ip}")
            messagebox.showinfo("Успех", f"IP адрес KPP2 сохранен: {new_ip}")
        except Exception as e:
            self.log(f"Ошибка при сохранении IP KPP2: {e}")
            messagebox.showerror("Ошибка", f"Не удалось сохранить IP: {e}")
    
    def start_java(self):
        """Запустить Java Web приложение"""
        global java_process
        
        if java_process is not None:
            self.log("Java приложение уже запущено!")
            return
            
        try:
            self.log("Запуск Java Web приложения...")
            os.chdir(PROJECT_ROOT)
            
            # Сначала пытаемся найти JAR файл
            jar_file = None
            if TARGET_DIR.exists():
                jar_files = list(TARGET_DIR.glob("*.jar"))
                # Ищем JAR с именем проекта (не sources, не javadoc)
                for jar in jar_files:
                    if "sources" not in jar.name and "javadoc" not in jar.name:
                        jar_file = jar
                        break
            
            if jar_file and jar_file.exists():
                # Запускаем через JAR
                self.log(f"Найден JAR файл: {jar_file.name}")
                java_process = subprocess.Popen(
                    ["java", "-jar", str(jar_file)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                self.log("Запуск через JAR файл...")
            else:
                # Запускаем через Maven
                if not POM_XML.exists():
                    messagebox.showerror("Ошибка", 
                                       "Файл pom.xml не найден и JAR файл не найден!\n"
                                       "Соберите проект через Maven или Idea.")
                    return
                
                # Проверяем наличие Maven
                try:
                    subprocess.run(["mvn", "--version"], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE, 
                                 timeout=5)
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    messagebox.showerror("Ошибка", 
                                       "Maven не найден и JAR файл не найден!\n"
                                       "Убедитесь, что Maven установлен и добавлен в PATH,\n"
                                       "или соберите JAR файл через Idea (Maven -> package).")
                    self.log("Ошибка: Maven не найден и JAR не найден!")
                    return
                
                self.log("Запуск через Maven...")
                java_process = subprocess.Popen(
                    ["mvn", "spring-boot:run"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
            
            # Запускаем поток для чтения вывода
            threading.Thread(target=self.monitor_java_process, daemon=True).start()
            
            self.java_start_btn.config(state=tk.DISABLED)
            self.java_stop_btn.config(state=tk.NORMAL)
            self.java_status_label.config(text="Статус: Запущен", fg=self.colors['status_running'])
            self.log("Java приложение запущено!")
            
        except FileNotFoundError as e:
            messagebox.showerror("Ошибка", 
                               f"Не найдена необходимая программа: {e}\n"
                               "Убедитесь, что Java и Maven установлены и добавлены в PATH.")
            self.log(f"Ошибка: {e}")
        except Exception as e:
            self.log(f"Ошибка при запуске Java: {e}")
            messagebox.showerror("Ошибка", f"Не удалось запустить Java приложение: {e}")
    
    def monitor_java_process(self):
        """Мониторинг процесса Java"""
        global java_process
        if java_process is None:
            return
            
        try:
            for line in iter(java_process.stdout.readline, ''):
                if line:
                    self.root.after(0, self.log, f"[Java] {line.strip()}")
                if java_process.poll() is not None:
                    break
        except Exception as e:
            self.root.after(0, self.log, f"Ошибка мониторинга Java: {e}")
        finally:
            if java_process and java_process.poll() is not None:
                self.root.after(0, self.on_java_stopped)
    
    def on_java_stopped(self):
        """Обработка остановки Java процесса"""
        global java_process
        java_process = None
        self.java_start_btn.config(state=tk.NORMAL)
        self.java_stop_btn.config(state=tk.DISABLED)
        self.java_status_label.config(text="Статус: Остановлен", fg=self.colors['status_stopped'])
        self.log("Java приложение остановлено")
    
    def stop_java(self):
        """Остановить Java Web приложение"""
        global java_process
        
        if java_process is None:
            return
            
        try:
            self.log("Остановка Java приложения...")
            java_process.terminate()
            
            # Ждем завершения
            try:
                java_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.log("Принудительное завершение Java процесса...")
                java_process.kill()
                java_process.wait()
                
            self.on_java_stopped()
            
        except Exception as e:
            self.log(f"Ошибка при остановке Java: {e}")
            messagebox.showerror("Ошибка", f"Не удалось остановить Java приложение: {e}")
    
    def check_python_dependencies(self):
        """Проверка и установка необходимых Python модулей"""
        required_modules = ['requests', 'cv2', 'numpy']
        missing_modules = []
        
        self.log("Проверка зависимостей Python...")
        
        for module in required_modules:
            try:
                result = subprocess.run(
                    [str(VENV_PYTHON), "-c", f"import {module}"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5
                )
                if result.returncode != 0:
                    missing_modules.append(module)
                    self.log(f"⚠ Модуль {module} не найден")
                else:
                    self.log(f"✅ Модуль {module} найден")
            except Exception as e:
                missing_modules.append(module)
                self.log(f"⚠ Ошибка проверки {module}: {e}")
        
        if missing_modules:
            self.log(f"Установка недостающих модулей: {', '.join(missing_modules)}")
            try:
                # Устанавливаем недостающие модули
                for module in missing_modules:
                    if module == 'cv2':
                        module_name = 'opencv-python'
                    else:
                        module_name = module
                    
                    self.log(f"Установка {module_name}...")
                    result = subprocess.run(
                        [str(VENV_PYTHON), "-m", "pip", "install", module_name],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        timeout=120
                    )
                    if result.returncode == 0:
                        self.log(f"✅ {module_name} установлен")
                    else:
                        self.log(f"❌ Ошибка установки {module_name}: {result.stdout[:200]}")
                        return False
            except Exception as e:
                self.log(f"❌ Ошибка при установке модулей: {e}")
                return False
        
        return True
    
    def start_kpp1(self):
        """Запустить Python скрипт KPP1"""
        global kpp1_process
        
        if kpp1_process is not None:
            self.log("KPP1 уже запущен!")
            return
            
        try:
            # Проверяем наличие venv
            if not VENV_PYTHON.exists():
                messagebox.showerror("Ошибка", 
                                   f"Python из venv не найден: {VENV_PYTHON}\n"
                                   "Убедитесь, что venv настроен правильно.")
                return
            
            if not KPP1_SCRIPT.exists():
                messagebox.showerror("Ошибка", f"Скрипт {KPP1_SCRIPT} не найден!")
                return
            
            # Проверяем и устанавливаем зависимости
            if not self.check_python_dependencies():
                messagebox.showerror("Ошибка", 
                                   "Не удалось установить необходимые модули.\n"
                                   "Проверьте логи для деталей.")
                return
            
            self.log("Запуск Python скрипта KPP1...")
            self.log(f"Python: {VENV_PYTHON}")
            self.log(f"Скрипт: {KPP1_SCRIPT}")
            self.log(f"Рабочая директория: {OPENCV_DIR}")
            
            # Используем -u для unbuffered режима, чтобы логи сразу отображались
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'  # Устанавливаем UTF-8 для вывода
            kpp1_process = subprocess.Popen(
                [str(VENV_PYTHON), "-u", str(KPP1_SCRIPT)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',  # Явно указываем UTF-8
                errors='replace',  # Заменяем проблемные символы вместо ошибки
                bufsize=0,  # Unbuffered
                universal_newlines=True,
                env=env,
                cwd=str(OPENCV_DIR),
                shell=False
            )
            
            # Сразу запускаем поток для чтения вывода (до проверки статуса)
            threading.Thread(target=self.monitor_kpp1_process, daemon=True).start()
            
            # Небольшая задержка для проверки, что процесс запустился
            import time
            time.sleep(1.0)  # Увеличиваем задержку для чтения первых логов
            
            # Проверяем, что процесс все еще работает
            if kpp1_process.poll() is not None:
                # Процесс уже завершился - даем время потоку прочитать вывод
                time.sleep(0.5)
                error_msg = f"KPP1 завершился с кодом {kpp1_process.returncode}"
                self.log(error_msg)
                messagebox.showerror("Ошибка", 
                                   f"KPP1 не запустился!\n\n"
                                   f"Код возврата: {kpp1_process.returncode}\n\n"
                                   f"Проверьте логи ниже для деталей ошибки.")
                kpp1_process = None
                return
            
            self.kpp1_start_btn.config(state=tk.DISABLED)
            self.kpp1_stop_btn.config(state=tk.NORMAL)
            self.kpp1_status_label.config(text="Статус: Запущен", fg=self.colors['status_running'])
            self.log("KPP1 запущен! Ожидание логов...")
            
        except Exception as e:
            self.log(f"Ошибка при запуске KPP1: {e}")
            messagebox.showerror("Ошибка", f"Не удалось запустить KPP1: {e}")
    
    def monitor_kpp1_process(self):
        """Мониторинг процесса KPP1"""
        global kpp1_process
        if kpp1_process is None:
            return
            
        try:
            # Читаем вывод построчно
            while kpp1_process.poll() is None:
                line = kpp1_process.stdout.readline()
                if line:
                    line = line.rstrip()
                    if line:  # Пропускаем пустые строки
                        self.root.after(0, self.log, f"[KPP1] {line}")
                else:
                    # Если нет данных, небольшая задержка
                    import time
                    time.sleep(0.1)
                    
        except Exception as e:
            self.root.after(0, self.log, f"Ошибка мониторинга KPP1: {e}")
            import traceback
            self.root.after(0, self.log, f"Traceback: {traceback.format_exc()}")
        finally:
            if kpp1_process and kpp1_process.poll() is not None:
                # Читаем оставшиеся строки
                try:
                    remaining = kpp1_process.stdout.read()
                    if remaining:
                        for line in remaining.splitlines():
                            if line.strip():
                                self.root.after(0, self.log, f"[KPP1] {line.strip()}")
                except:
                    pass
                self.root.after(0, self.on_kpp1_stopped)
    
    def on_kpp1_stopped(self):
        """Обработка остановки KPP1 процесса"""
        global kpp1_process
        kpp1_process = None
        self.kpp1_start_btn.config(state=tk.NORMAL)
        self.kpp1_stop_btn.config(state=tk.DISABLED)
        self.kpp1_status_label.config(text="Статус: Остановлен", fg=self.colors['status_stopped'])
        self.log("KPP1 остановлен")
    
    def stop_kpp1(self):
        """Остановить Python скрипт KPP1"""
        global kpp1_process
        
        if kpp1_process is None:
            return
            
        try:
            self.log("Остановка KPP1...")
            kpp1_process.terminate()
            
            try:
                kpp1_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.log("Принудительное завершение KPP1...")
                kpp1_process.kill()
                kpp1_process.wait()
                
            self.on_kpp1_stopped()
            
        except Exception as e:
            self.log(f"Ошибка при остановке KPP1: {e}")
            messagebox.showerror("Ошибка", f"Не удалось остановить KPP1: {e}")
    
    def start_kpp2(self):
        """Запустить Python скрипт KPP2"""
        global kpp2_process
        
        if kpp2_process is not None:
            self.log("KPP2 уже запущен!")
            return
            
        try:
            # Проверяем наличие venv
            if not VENV_PYTHON.exists():
                messagebox.showerror("Ошибка", 
                                   f"Python из venv не найден: {VENV_PYTHON}\n"
                                   "Убедитесь, что venv настроен правильно.")
                return
            
            if not KPP2_SCRIPT.exists():
                messagebox.showerror("Ошибка", f"Скрипт {KPP2_SCRIPT} не найден!")
                return
            
            # Проверяем и устанавливаем зависимости
            if not self.check_python_dependencies():
                messagebox.showerror("Ошибка", 
                                   "Не удалось установить необходимые модули.\n"
                                   "Проверьте логи для деталей.")
                return
            
            self.log("Запуск Python скрипта KPP2...")
            self.log(f"Python: {VENV_PYTHON}")
            self.log(f"Скрипт: {KPP2_SCRIPT}")
            self.log(f"Рабочая директория: {OPENCV_DIR}")
            
            # Используем -u для unbuffered режима, чтобы логи сразу отображались
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'  # Устанавливаем UTF-8 для вывода
            kpp2_process = subprocess.Popen(
                [str(VENV_PYTHON), "-u", str(KPP2_SCRIPT)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',  # Явно указываем UTF-8
                errors='replace',  # Заменяем проблемные символы вместо ошибки
                bufsize=0,  # Unbuffered
                universal_newlines=True,
                env=env,
                cwd=str(OPENCV_DIR),
                shell=False
            )
            
            # Сразу запускаем поток для чтения вывода (до проверки статуса)
            threading.Thread(target=self.monitor_kpp2_process, daemon=True).start()
            
            # Небольшая задержка для проверки, что процесс запустился
            import time
            time.sleep(1.0)  # Увеличиваем задержку для чтения первых логов
            
            # Проверяем, что процесс все еще работает
            if kpp2_process.poll() is not None:
                # Процесс уже завершился - даем время потоку прочитать вывод
                time.sleep(0.5)
                error_msg = f"KPP2 завершился с кодом {kpp2_process.returncode}"
                self.log(error_msg)
                messagebox.showerror("Ошибка", 
                                   f"KPP2 не запустился!\n\n"
                                   f"Код возврата: {kpp2_process.returncode}\n\n"
                                   f"Проверьте логи ниже для деталей ошибки.")
                kpp2_process = None
                return
            
            self.kpp2_start_btn.config(state=tk.DISABLED)
            self.kpp2_stop_btn.config(state=tk.NORMAL)
            self.kpp2_status_label.config(text="Статус: Запущен", fg=self.colors['status_running'])
            self.log("KPP2 запущен! Ожидание логов...")
            
        except Exception as e:
            self.log(f"Ошибка при запуске KPP2: {e}")
            messagebox.showerror("Ошибка", f"Не удалось запустить KPP2: {e}")
    
    def monitor_kpp2_process(self):
        """Мониторинг процесса KPP2"""
        global kpp2_process
        if kpp2_process is None:
            return
            
        try:
            # Читаем вывод построчно
            while kpp2_process.poll() is None:
                line = kpp2_process.stdout.readline()
                if line:
                    line = line.rstrip()
                    if line:  # Пропускаем пустые строки
                        self.root.after(0, self.log, f"[KPP2] {line}")
                else:
                    # Если нет данных, небольшая задержка
                    import time
                    time.sleep(0.1)
                    
        except Exception as e:
            self.root.after(0, self.log, f"Ошибка мониторинга KPP2: {e}")
            import traceback
            self.root.after(0, self.log, f"Traceback: {traceback.format_exc()}")
        finally:
            if kpp2_process and kpp2_process.poll() is not None:
                # Читаем оставшиеся строки
                try:
                    remaining = kpp2_process.stdout.read()
                    if remaining:
                        for line in remaining.splitlines():
                            if line.strip():
                                self.root.after(0, self.log, f"[KPP2] {line.strip()}")
                except:
                    pass
                self.root.after(0, self.on_kpp2_stopped)
    
    def on_kpp2_stopped(self):
        """Обработка остановки KPP2 процесса"""
        global kpp2_process
        kpp2_process = None
        self.kpp2_start_btn.config(state=tk.NORMAL)
        self.kpp2_stop_btn.config(state=tk.DISABLED)
        self.kpp2_status_label.config(text="Статус: Остановлен", fg=self.colors['status_stopped'])
        self.log("KPP2 остановлен")
    
    def stop_kpp2(self):
        """Остановить Python скрипт KPP2"""
        global kpp2_process
        
        if kpp2_process is None:
            return
            
        try:
            self.log("Остановка KPP2...")
            kpp2_process.terminate()
            
            try:
                kpp2_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.log("Принудительное завершение KPP2...")
                kpp2_process.kill()
                kpp2_process.wait()
                
            self.on_kpp2_stopped()
            
        except Exception as e:
            self.log(f"Ошибка при остановке KPP2: {e}")
            messagebox.showerror("Ошибка", f"Не удалось остановить KPP2: {e}")


def main():
    root = tk.Tk()
    app = LauncherApp(root)
    
    # Обработка закрытия окна
    def on_closing():
        global java_process, kpp1_process, kpp2_process
        
        if messagebox.askokcancel("Выход", "Закрыть лаунчер и остановить все процессы?"):
            if java_process:
                java_process.terminate()
            if kpp1_process:
                kpp1_process.terminate()
            if kpp2_process:
                kpp2_process.terminate()
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
