#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Лаунчер для управления FacePanel проектом
Современный дизайн на PyQt6
"""

import sys
from pathlib import Path
import subprocess
import os
import re
import threading
import time
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QTextEdit, 
                             QLineEdit, QFrame, QMessageBox, QGroupBox, QSplitter,
                             QScrollArea)
from PyQt6.QtCore import (Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, 
                         QParallelAnimationGroup, QEasingCurve, pyqtProperty)
from PyQt6.QtGui import QPixmap, QFont, QColor, QLinearGradient, QPainter, QPalette, QBrush

# Пути к файлам проекта
PROJECT_ROOT = Path(__file__).parent.absolute()
OPENCV_DIR = PROJECT_ROOT / "OpenCVRework"
VENV_PYTHON = OPENCV_DIR / "venv" / "Scripts" / "python.exe"
KPP1_SCRIPT = OPENCV_DIR / "face_kpp1.py"
KPP2_SCRIPT = OPENCV_DIR / "face_kpp2.py"
POM_XML = PROJECT_ROOT / "pom.xml"
TARGET_DIR = PROJECT_ROOT / "target"
LOGO_PATH = PROJECT_ROOT / "logo.png"

# Процессы
java_process = None
kpp1_process = None
kpp2_process = None


class GradientButton(QPushButton):
    """Кнопка с градиентом"""
    def __init__(self, text, parent=None, is_accent=False):
        super().__init__(text, parent)
        self.is_accent = is_accent
        self.setMinimumHeight(40)
        self.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        
    def paintEvent(self, event):
        if self.is_accent:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            gradient = QLinearGradient(0, 0, self.width(), self.height())
            gradient.setColorAt(0, QColor("#D2BE8A"))
            gradient.setColorAt(1, QColor("#C9B37E"))
            
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect(), 8, 8)
            
            painter.setPen(QColor("#0E0E0E"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        else:
            super().paintEvent(event)


class ServiceCard(QFrame):
    """Карточка для сервиса с анимациями"""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName(f"serviceCard_{id(self)}")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setStyleSheet("""
            QFrame {
                background-color: #262626;
                border: 1px solid rgba(201, 179, 126, 0.2);
                border-radius: 12px;
                padding: 15px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Заголовок
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #EDEDED;")
        header.addWidget(title_label)
        header.addStretch()
        
        self.status_label = QLabel("Остановлен")
        self.status_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.status_label.setStyleSheet("color: #C86464;")
        header.addWidget(self.status_label)
        
        layout.addLayout(header)
        
        # Контент (будет добавлен позже)
        self.content_layout = QVBoxLayout()
        layout.addLayout(self.content_layout)


class ModernLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FacePanel Launcher - Lahmut Group")
        self.setGeometry(100, 100, 1000, 800)
        
        # Цветовая палитра
        self.colors = {
            'bg_primary': '#0E0E0E',
            'bg_secondary': '#262626',
            'accent': '#C9B37E',
            'accent_light': '#D2BE8A',
            'text': '#EDEDED',
            'status_running': '#C9B37E',
            'status_stopped': '#C86464'
        }
        
        self.setup_ui()
        self.load_camera_ips()
        
    def setup_ui(self):
        # Центральный виджет с анимированным фоном
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Инициализация анимации фона
        self.gradient_angle = 0
        
        # Установка темного фона с анимацией
        self.bg_timer = QTimer()
        self.bg_timer.timeout.connect(self.animate_background)
        self.bg_timer.start(50)  # Обновление каждые 50мс
        self.animate_background()
        
        # Главный layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Левая панель - панели управления
        left_panel = QWidget()
        left_panel_layout = QVBoxLayout(left_panel)
        left_panel_layout.setSpacing(15)
        left_panel_layout.setContentsMargins(0, 0, 0, 0)
        
        # Заголовок с логотипом
        header = self.create_header()
        left_panel_layout.addWidget(header)
        
        # Панели управления
        services_layout = QVBoxLayout()
        services_layout.setSpacing(12)
        services_layout.setContentsMargins(0, 0, 0, 0)
        
        # Java Web Application
        self.java_card = ServiceCard("Java Web Application (Панель)")
        self.setup_java_card()
        services_layout.addWidget(self.java_card)
        
        # ВХОД
        self.kpp1_card = ServiceCard("Python Script ВХОД")
        self.setup_kpp1_card()
        services_layout.addWidget(self.kpp1_card)

        # ВЫХОД
        self.kpp2_card = ServiceCard("Python Script ВЫХОД")
        self.setup_kpp2_card()
        services_layout.addWidget(self.kpp2_card)
        
        services_layout.addStretch()
        
        # Контейнер для панелей управления
        services_container = QWidget()
        services_container.setLayout(services_layout)
        left_panel_layout.addWidget(services_container, stretch=1)
        
        # Правая панель - логи
        right_panel = self.create_logs_panel()
        
        # Разделитель
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([600, 400])  # Соотношение 60/40
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: rgba(201, 179, 126, 0.2);
                width: 2px;
            }
            QSplitter::handle:hover {
                background: rgba(201, 179, 126, 0.4);
            }
        """)
        
        main_layout.addWidget(splitter)
        
    def create_header(self):
        """Создает заголовок с логотипом"""
        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        header_layout.setSpacing(20)
        
        # Логотип
        if LOGO_PATH.exists():
            logo_label = QLabel()
            pixmap = QPixmap(str(LOGO_PATH))
            scaled_pixmap = pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio, 
                                         Qt.TransformationMode.SmoothTransformation)
            logo_label.setPixmap(scaled_pixmap)
            header_layout.addWidget(logo_label)
        
        # Текст заголовка
        text_layout = QVBoxLayout()
        title = QLabel("FacePanel Launcher")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #EDEDED;")
        text_layout.addWidget(title)
        
        subtitle = QLabel("Lahmut Group")
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setStyleSheet("color: #C9B37E;")
        text_layout.addWidget(subtitle)
        
        header_layout.addLayout(text_layout)
        header_layout.addStretch()
        
        return header_frame
    
    def setup_java_card(self):
        """Настройка карточки Java"""
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.java_start_btn = GradientButton("▶ Запустить", is_accent=True)
        self.java_start_btn.clicked.connect(self.start_java)
        self.java_start_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #D2BE8A, stop:1 #C9B37E);
                color: #0E0E0E;
                border-radius: 8px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #E0CFA0, stop:1 #D2BE8A);
            }
            QPushButton:disabled {
                background: #3A3A3A;
                color: #888888;
            }
        """)
        btn_layout.addWidget(self.java_start_btn)
        
        self.java_stop_btn = QPushButton("⏹ Остановить")
        self.java_stop_btn.setEnabled(False)
        self.java_stop_btn.clicked.connect(self.stop_java)
        self.java_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #262626;
                color: #EDEDED;
                border: 1px solid #C86464;
                border-radius: 8px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #2A2A2A;
            }
            QPushButton:disabled {
                background-color: #1A1A1A;
                color: #666666;
                border-color: #444444;
            }
        """)
        btn_layout.addWidget(self.java_stop_btn)
        
        self.java_card.content_layout.addLayout(btn_layout)
    
    def setup_kpp1_card(self):
        """Настройка карточки KPP1"""
        # IP поле
        ip_layout = QHBoxLayout()
        ip_label = QLabel("IP адрес камеры:")
        ip_label.setStyleSheet("color: #EDEDED;")
        ip_layout.addWidget(ip_label)
        
        self.kpp1_ip_input = QLineEdit()
        self.kpp1_ip_input.setStyleSheet("""
            QLineEdit {
                background-color: #1A1A1A;
                color: #EDEDED;
                border: 1px solid rgba(201, 179, 126, 0.3);
                border-radius: 6px;
                padding: 8px;
            }
            QLineEdit:focus {
                border: 1px solid #C9B37E;
            }
        """)
        ip_layout.addWidget(self.kpp1_ip_input, stretch=1)
        
        save_btn = QPushButton("💾 Сохранить IP")
        save_btn.clicked.connect(self.save_kpp1_ip)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A1A1A;
                color: #C9B37E;
                border: 1px solid rgba(201, 179, 126, 0.3);
                border-radius: 6px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #262626;
                border-color: #C9B37E;
            }
        """)
        ip_layout.addWidget(save_btn)
        
        self.kpp1_card.content_layout.addLayout(ip_layout)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.kpp1_start_btn = GradientButton("▶ Запустить", is_accent=True)
        self.kpp1_start_btn.clicked.connect(self.start_kpp1)
        self.kpp1_start_btn.setStyleSheet(self.java_start_btn.styleSheet())
        btn_layout.addWidget(self.kpp1_start_btn)
        
        self.kpp1_stop_btn = QPushButton("⏹ Остановить")
        self.kpp1_stop_btn.setEnabled(False)
        self.kpp1_stop_btn.clicked.connect(self.stop_kpp1)
        self.kpp1_stop_btn.setStyleSheet(self.java_stop_btn.styleSheet())
        btn_layout.addWidget(self.kpp1_stop_btn)
        
        self.kpp1_card.content_layout.addLayout(btn_layout)
    
    def setup_kpp2_card(self):
        """Настройка карточки KPP2"""
        # IP поле
        ip_layout = QHBoxLayout()
        ip_label = QLabel("IP адрес камеры:")
        ip_label.setStyleSheet("color: #EDEDED;")
        ip_layout.addWidget(ip_label)
        
        self.kpp2_ip_input = QLineEdit()
        self.kpp2_ip_input.setStyleSheet(self.kpp1_ip_input.styleSheet())
        ip_layout.addWidget(self.kpp2_ip_input, stretch=1)
        
        save_btn = QPushButton("💾 Сохранить IP")
        save_btn.clicked.connect(self.save_kpp2_ip)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #1A1A1A;
                color: #C9B37E;
                border: 1px solid rgba(201, 179, 126, 0.3);
                border-radius: 6px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #262626;
                border-color: #C9B37E;
            }
        """)
        ip_layout.addWidget(save_btn)
        
        self.kpp2_card.content_layout.addLayout(ip_layout)
        
        # Кнопки
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.kpp2_start_btn = GradientButton("▶ Запустить", is_accent=True)
        self.kpp2_start_btn.clicked.connect(self.start_kpp2)
        self.kpp2_start_btn.setStyleSheet(self.java_start_btn.styleSheet())
        btn_layout.addWidget(self.kpp2_start_btn)
        
        self.kpp2_stop_btn = QPushButton("⏹ Остановить")
        self.kpp2_stop_btn.setEnabled(False)
        self.kpp2_stop_btn.clicked.connect(self.stop_kpp2)
        self.kpp2_stop_btn.setStyleSheet(self.java_stop_btn.styleSheet())
        btn_layout.addWidget(self.kpp2_stop_btn)
        
        self.kpp2_card.content_layout.addLayout(btn_layout)
    
    def animate_background(self):
        """Анимация фона - плавное движение градиента"""
        self.gradient_angle = (self.gradient_angle + 0.5) % 360
        angle_rad = self.gradient_angle * 3.14159 / 180
        
        # Вычисляем позиции для плавного движения градиента
        x1 = 0.5 + 0.3 * abs(angle_rad / 3.14159)
        y1 = 0.5 - 0.3 * abs(angle_rad / 3.14159)
        x2 = 0.5 - 0.3 * abs(angle_rad / 3.14159)
        y2 = 0.5 + 0.3 * abs(angle_rad / 3.14159)
        
        # Плавный градиент от темного к чуть светлее
        style = f"""
            QMainWindow {{
                background: qlineargradient(x1:{x1}, y1:{y1}, x2:{x2}, y2:{y2},
                    stop:0 #0E0E0E, stop:0.5 #111111, stop:1 #0E0E0E);
            }}
        """
        self.setStyleSheet(style)
    
    def create_logs_panel(self):
        """Создает панель логов справа"""
        logs_panel = QFrame()
        logs_panel.setObjectName("logsPanel")
        logs_panel.setStyleSheet("""
            QFrame#logsPanel {
                background-color: #1A1A1A;
                border: 1px solid rgba(201, 179, 126, 0.3);
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(logs_panel)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Заголовок и кнопки
        header = QHBoxLayout()
        title = QLabel("Логи системы")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #EDEDED;")
        header.addWidget(title)
        header.addStretch()
        
        btn_style = """
            QPushButton {
                background-color: #262626;
                color: #C9B37E;
                border: 1px solid rgba(201, 179, 126, 0.3);
                border-radius: 6px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2A2A2A;
                border-color: #C9B37E;
            }
        """
        
        clear_btn = QPushButton("Очистить")
        clear_btn.clicked.connect(lambda: self.log_text.clear())
        clear_btn.setStyleSheet(btn_style)
        header.addWidget(clear_btn)
        
        copy_btn = QPushButton("Копировать")
        copy_btn.clicked.connect(self.copy_logs)
        copy_btn.setStyleSheet(btn_style)
        header.addWidget(copy_btn)
        
        layout.addLayout(header)
        
        # Текстовое поле с прокруткой
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #0E0E0E;
                color: #EDEDED;
                border: 1px solid rgba(201, 179, 126, 0.2);
                border-radius: 8px;
                padding: 12px;
                selection-background-color: #C9B37E;
                selection-color: #0E0E0E;
            }
            QScrollBar:vertical {
                background: #1A1A1A;
                width: 12px;
                border-radius: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #C9B37E;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #D2BE8A;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        layout.addWidget(self.log_text)
        
        return logs_panel
    
    def log(self, message):
        """Добавить сообщение в лог"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # Автопрокрутка
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def copy_logs(self):
        """Копировать выделенный текст"""
        text = self.log_text.textCursor().selectedText()
        if text:
            QApplication.clipboard().setText(text)
            self.log("Текст скопирован в буфер обмена")
        else:
            # Копируем все, если ничего не выделено
            QApplication.clipboard().setText(self.log_text.toPlainText())
            self.log("Все логи скопированы в буфер обмена")
    
    def load_camera_ips(self):
        """Загрузить IP адреса камер"""
        try:
            if KPP1_SCRIPT.exists():
                content = KPP1_SCRIPT.read_text(encoding='utf-8')
                match = re.search(r'face\.CAMERA_URL\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    self.kpp1_ip_input.setText(match.group(1))
            
            if KPP2_SCRIPT.exists():
                content = KPP2_SCRIPT.read_text(encoding='utf-8')
                match = re.search(r'face\.CAMERA_URL\s*=\s*["\']([^"\']+)["\']', content)
                if match:
                    self.kpp2_ip_input.setText(match.group(1))
        except Exception as e:
            self.log(f"Ошибка при загрузке IP: {e}")
    
    def save_kpp1_ip(self):
        """Сохранить IP для KPP1"""
        self._save_ip(KPP1_SCRIPT, self.kpp1_ip_input.text(), "KPP1")
    
    def save_kpp2_ip(self):
        """Сохранить IP для KPP2"""
        self._save_ip(KPP2_SCRIPT, self.kpp2_ip_input.text(), "KPP2")
    
    def _save_ip(self, script_path, new_ip, name):
        """Сохранение IP адреса"""
        try:
            if not script_path.exists():
                QMessageBox.critical(self, "Ошибка", f"Файл {script_path} не найден!")
                return
            
            new_ip = new_ip.strip()
            if not new_ip:
                QMessageBox.critical(self, "Ошибка", "IP адрес не может быть пустым!")
                return
            
            content = script_path.read_text(encoding='utf-8')
            pattern = r'(face\.CAMERA_URL\s*=\s*["\'])[^"\']+(["\'][\s]*\n)'
            replacement = r'\1' + new_ip + r'\2'
            new_content = re.sub(pattern, replacement, content)
            
            script_path.write_text(new_content, encoding='utf-8')
            self.log(f"IP адрес {name} сохранен: {new_ip}")
            QMessageBox.information(self, "Успех", f"IP адрес {name} сохранен: {new_ip}")
        except Exception as e:
            self.log(f"Ошибка при сохранении IP {name}: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить IP: {e}")
    
    # Все методы запуска/остановки процессов (скопированы из старой версии с адаптацией под PyQt6)
    def start_java(self):
        """Запустить Java Web приложение"""
        global java_process
        
        if java_process is not None:
            self.log("Java приложение уже запущено!")
            return
        
        try:
            self.log("Запуск Java Web приложения...")
            os.chdir(PROJECT_ROOT)
            
            jar_file = None
            if TARGET_DIR.exists():
                jar_files = list(TARGET_DIR.glob("*.jar"))
                for jar in jar_files:
                    if "sources" not in jar.name and "javadoc" not in jar.name:
                        jar_file = jar
                        break
            
            if jar_file and jar_file.exists():
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
                if not POM_XML.exists():
                    QMessageBox.critical(self, "Ошибка", 
                                       "Файл pom.xml не найден и JAR файл не найден!")
                    return
                
                try:
                    subprocess.run(["mvn", "--version"], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE, 
                                 timeout=5)
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    QMessageBox.critical(self, "Ошибка", 
                                       "Maven не найден и JAR файл не найден!")
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
            
            threading.Thread(target=self.monitor_java_process, daemon=True).start()
            
            self.java_start_btn.setEnabled(False)
            self.java_stop_btn.setEnabled(True)
            self.java_card.status_label.setText("Запущен")
            self.java_card.status_label.setStyleSheet("color: #C9B37E;")
            self.log("Java приложение запущено!")
        
        except Exception as e:
            self.log(f"Ошибка при запуске Java: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить Java: {e}")
    
    def monitor_java_process(self):
        """Мониторинг Java процесса"""
        global java_process
        if java_process is None:
            return
        
        try:
            for line in iter(java_process.stdout.readline, ''):
                if line:
                    self.log(f"[Java] {line.strip()}")
                if java_process.poll() is not None:
                    break
        except Exception as e:
            self.log(f"Ошибка мониторинга Java: {e}")
        finally:
            if java_process and java_process.poll() is not None:
                QTimer.singleShot(0, self.on_java_stopped)
    
    def on_java_stopped(self):
        """Обработка остановки Java"""
        global java_process
        java_process = None
        self.java_start_btn.setEnabled(True)
        self.java_stop_btn.setEnabled(False)
        self.java_card.status_label.setText("Остановлен")
        self.java_card.status_label.setStyleSheet("color: #C86464;")
        self.log("Java приложение остановлено")
    
    def stop_java(self):
        """Остановить Java"""
        global java_process
        if java_process is None:
            return
        
        try:
            self.log("Остановка Java приложения...")
            java_process.terminate()
            try:
                java_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.log("Принудительное завершение Java...")
                java_process.kill()
                java_process.wait()
            self.on_java_stopped()
        except Exception as e:
            self.log(f"Ошибка при остановке Java: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось остановить Java: {e}")
    
    def check_python_dependencies(self):
        """Проверка зависимостей Python"""
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
                for module in missing_modules:
                    module_name = 'opencv-python' if module == 'cv2' else module
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
                        self.log(f"❌ Ошибка установки {module_name}")
                        return False
            except Exception as e:
                self.log(f"❌ Ошибка при установке модулей: {e}")
                return False
        
        return True
    
    def start_kpp1(self):
        """Запустить KPP1"""
        global kpp1_process
        
        if kpp1_process is not None:
            self.log("KPP1 уже запущен!")
            return
        
        try:
            if not VENV_PYTHON.exists():
                QMessageBox.critical(self, "Ошибка", 
                                   f"Python из venv не найден: {VENV_PYTHON}")
                return
            
            if not KPP1_SCRIPT.exists():
                QMessageBox.critical(self, "Ошибка", f"Скрипт {KPP1_SCRIPT} не найден!")
                return
            
            if not self.check_python_dependencies():
                QMessageBox.critical(self, "Ошибка", 
                                   "Не удалось установить необходимые модули.")
                return
            
            self.log("Запуск Python скрипта KPP1...")
            
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            kpp1_process = subprocess.Popen(
                [str(VENV_PYTHON), "-u", str(KPP1_SCRIPT)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=0,
                universal_newlines=True,
                env=env,
                cwd=str(OPENCV_DIR),
                shell=False
            )
            
            threading.Thread(target=self.monitor_kpp1_process, daemon=True).start()
            
            time.sleep(1.0)
            
            if kpp1_process.poll() is not None:
                time.sleep(0.5)
                error_msg = f"KPP1 завершился с кодом {kpp1_process.returncode}"
                self.log(error_msg)
                QMessageBox.critical(self, "Ошибка", f"KPP1 не запустился!")
                kpp1_process = None
                return
            
            self.kpp1_start_btn.setEnabled(False)
            self.kpp1_stop_btn.setEnabled(True)
            self.kpp1_card.status_label.setText("Запущен")
            self.kpp1_card.status_label.setStyleSheet("color: #C9B37E;")
            self.log("KPP1 запущен! Ожидание логов...")
        
        except Exception as e:
            self.log(f"Ошибка при запуске KPP1: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить KPP1: {e}")
    
    def monitor_kpp1_process(self):
        """Мониторинг KPP1"""
        global kpp1_process
        if kpp1_process is None:
            return
        
        try:
            while kpp1_process.poll() is None:
                line = kpp1_process.stdout.readline()
                if line:
                    line = line.rstrip()
                    if line:
                        self.log(f"[KPP1] {line}")
                else:
                    time.sleep(0.1)
        except Exception as e:
            self.log(f"Ошибка мониторинга KPP1: {e}")
        finally:
            if kpp1_process and kpp1_process.poll() is not None:
                try:
                    remaining = kpp1_process.stdout.read()
                    if remaining:
                        for line in remaining.splitlines():
                            if line.strip():
                                self.log(f"[KPP1] {line.strip()}")
                except:
                    pass
                QTimer.singleShot(0, self.on_kpp1_stopped)
    
    def on_kpp1_stopped(self):
        """Обработка остановки KPP1"""
        global kpp1_process
        kpp1_process = None
        self.kpp1_start_btn.setEnabled(True)
        self.kpp1_stop_btn.setEnabled(False)
        self.kpp1_card.status_label.setText("Остановлен")
        self.kpp1_card.status_label.setStyleSheet("color: #C86464;")
        self.log("KPP1 остановлен")
    
    def stop_kpp1(self):
        """Остановить KPP1"""
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
            QMessageBox.critical(self, "Ошибка", f"Не удалось остановить KPP1: {e}")
    
    def start_kpp2(self):
        """Запустить KPP2"""
        global kpp2_process
        
        if kpp2_process is not None:
            self.log("KPP2 уже запущен!")
            return
        
        try:
            if not VENV_PYTHON.exists():
                QMessageBox.critical(self, "Ошибка", 
                                   f"Python из venv не найден: {VENV_PYTHON}")
                return
            
            if not KPP2_SCRIPT.exists():
                QMessageBox.critical(self, "Ошибка", f"Скрипт {KPP2_SCRIPT} не найден!")
                return
            
            if not self.check_python_dependencies():
                QMessageBox.critical(self, "Ошибка", 
                                   "Не удалось установить необходимые модули.")
                return
            
            self.log("Запуск Python скрипта KPP2...")
            
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'
            env['PYTHONIOENCODING'] = 'utf-8'
            kpp2_process = subprocess.Popen(
                [str(VENV_PYTHON), "-u", str(KPP2_SCRIPT)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=0,
                universal_newlines=True,
                env=env,
                cwd=str(OPENCV_DIR),
                shell=False
            )
            
            threading.Thread(target=self.monitor_kpp2_process, daemon=True).start()
            
            time.sleep(1.0)
            
            if kpp2_process.poll() is not None:
                time.sleep(0.5)
                error_msg = f"KPP2 завершился с кодом {kpp2_process.returncode}"
                self.log(error_msg)
                QMessageBox.critical(self, "Ошибка", f"KPP2 не запустился!")
                kpp2_process = None
                return
            
            self.kpp2_start_btn.setEnabled(False)
            self.kpp2_stop_btn.setEnabled(True)
            self.kpp2_card.status_label.setText("Запущен")
            self.kpp2_card.status_label.setStyleSheet("color: #C9B37E;")
            self.log("KPP2 запущен! Ожидание логов...")
        
        except Exception as e:
            self.log(f"Ошибка при запуске KPP2: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось запустить KPP2: {e}")
    
    def monitor_kpp2_process(self):
        """Мониторинг KPP2"""
        global kpp2_process
        if kpp2_process is None:
            return
        
        try:
            while kpp2_process.poll() is None:
                line = kpp2_process.stdout.readline()
                if line:
                    line = line.rstrip()
                    if line:
                        self.log(f"[KPP2] {line}")
                else:
                    time.sleep(0.1)
        except Exception as e:
            self.log(f"Ошибка мониторинга KPP2: {e}")
        finally:
            if kpp2_process and kpp2_process.poll() is not None:
                try:
                    remaining = kpp2_process.stdout.read()
                    if remaining:
                        for line in remaining.splitlines():
                            if line.strip():
                                self.log(f"[KPP2] {line.strip()}")
                except:
                    pass
                QTimer.singleShot(0, self.on_kpp2_stopped)
    
    def on_kpp2_stopped(self):
        """Обработка остановки KPP2"""
        global kpp2_process
        kpp2_process = None
        self.kpp2_start_btn.setEnabled(True)
        self.kpp2_stop_btn.setEnabled(False)
        self.kpp2_card.status_label.setText("Остановлен")
        self.kpp2_card.status_label.setStyleSheet("color: #C86464;")
        self.log("KPP2 остановлен")
    
    def stop_kpp2(self):
        """Остановить KPP2"""
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
            QMessageBox.critical(self, "Ошибка", f"Не удалось остановить KPP2: {e}")
    
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        global java_process, kpp1_process, kpp2_process
        
        reply = QMessageBox.question(self, "Выход", 
                                    "Закрыть лаунчер и остановить все процессы?",
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            if java_process:
                java_process.terminate()
            if kpp1_process:
                kpp1_process.terminate()
            if kpp2_process:
                kpp2_process.terminate()
            event.accept()
        else:
            event.ignore()


def main():
    app = QApplication(sys.argv)
    
    # Установка стиля приложения
    app.setStyle("Fusion")
    
    window = ModernLauncher()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
