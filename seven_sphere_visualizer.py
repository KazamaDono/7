"""
seven_sphere_visualizer.py - Native PyQt5 Visualizer with Siri-like Sphere Motion
"""

import sys
import os
import math
import random
import threading
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTextEdit, QStackedWidget
)
from PyQt5.QtCore import Qt, QTimer, QPoint
from PyQt5.QtGui import QPainter, QColor, QRadialGradient, QPen, QBrush

# Create necessary directories
current_dir = os.getcwd()
TempDirPath = os.path.join(current_dir, "Frontend", "Files")
os.makedirs(TempDirPath, exist_ok=True)

class AnimatedSphere(QWidget):
    """Custom animated sphere widget with Siri-like motion"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.setMaximumSize(500, 500)
        
        # Animation state
        self.pulse_scale = 1.0
        self.rotation_angle = 0
        self.audio_level = 0
        self.state = "idle"
        self.ripples = []
        
        # Colors
        self.colors = {
            'idle': (0, 150, 255),
            'listening': (68, 255, 68),
            'speaking': (255, 170, 68),
            'processing': (255, 68, 255)
        }
        
        # Animation timers
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self.update_pulse)
        self.pulse_timer.start(50)
        
        self.ripple_timer = QTimer()
        self.ripple_timer.timeout.connect(self.update_ripples)
        self.ripple_timer.start(100)
    
    def update_pulse(self):
        """Update pulsing animation"""
        if self.state == "listening":
            target = 1.0 + (self.audio_level * 0.3)
            self.pulse_scale = self.pulse_scale * 0.8 + target * 0.2
        elif self.state == "speaking":
            target = 1.0 + math.sin(datetime.now().timestamp() * 20) * 0.15
            self.pulse_scale = self.pulse_scale * 0.9 + target * 0.1
        elif self.state == "processing":
            target = 1.0 + math.sin(datetime.now().timestamp() * 5) * 0.1
            self.pulse_scale = self.pulse_scale * 0.95 + target * 0.05
        else:
            target = 1.0 + math.sin(datetime.now().timestamp() * 2) * 0.05
            self.pulse_scale = self.pulse_scale * 0.95 + target * 0.05
        
        self.update()
    
    def update_ripples(self):
        """Update ripple effects"""
        if self.state in ["listening", "speaking"]:
            if random.random() < 0.2:
                self.ripples.append({'scale': 1.0, 'alpha': 0.6})
        
        for ripple in self.ripples[:]:
            ripple['scale'] += 0.04
            ripple['alpha'] -= 0.02
            if ripple['scale'] > 2.5 or ripple['alpha'] <= 0:
                self.ripples.remove(ripple)
        
        self.update()
    
    def set_state(self, state, audio_level=0):
        """Update sphere state"""
        self.state = state
        self.audio_level = min(1.0, audio_level)
    
    def paintEvent(self, event):
        """Draw the animated sphere"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Center point
        width = self.width()
        height = self.height()
        center = QPoint(width // 2, height // 2)
        base_radius = min(width, height) // 2 - 20
        
        # Draw ripples
        for ripple in self.ripples:
            radius = base_radius * ripple['scale']
            color = self.colors.get(self.state, self.colors['idle'])
            alpha = int(ripple['alpha'] * 100)
            pen = QPen(QColor(color[0], color[1], color[2], alpha))
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, int(radius), int(radius))
        
        # Draw outer glow
        glow_radius = base_radius * (1.0 + self.pulse_scale * 0.2)
        color = self.colors.get(self.state, self.colors['idle'])
        glow_gradient = QRadialGradient(center, glow_radius)
        glow_gradient.setColorAt(0, QColor(color[0], color[1], color[2], 80))
        glow_gradient.setColorAt(1, QColor(color[0], color[1], color[2], 0))
        painter.setBrush(QBrush(glow_gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, int(glow_radius), int(glow_radius))
        
        # Draw main sphere
        sphere_radius = base_radius * self.pulse_scale
        sphere_gradient = QRadialGradient(center, sphere_radius)
        sphere_gradient.setColorAt(0, QColor(color[0], color[1], color[2]))
        sphere_gradient.setColorAt(0.7, QColor(
            int(color[0] * 0.6),
            int(color[1] * 0.6),
            int(color[2] * 0.6)
        ))
        sphere_gradient.setColorAt(1, QColor(
            int(color[0] * 0.2),
            int(color[1] * 0.2),
            int(color[2] * 0.2)
        ))
        
        painter.setBrush(QBrush(sphere_gradient))
        painter.drawEllipse(center, int(sphere_radius), int(sphere_radius))
        
        # Draw highlight
        highlight_offset = int(sphere_radius * 0.3)
        highlight_radius = int(sphere_radius * 0.6)
        highlight_gradient = QRadialGradient(
            center.x() - highlight_offset,
            center.y() - highlight_offset,
            highlight_radius
        )
        highlight_gradient.setColorAt(0, QColor(255, 255, 255, 100))
        highlight_gradient.setColorAt(1, QColor(255, 255, 255, 0))
        painter.setBrush(QBrush(highlight_gradient))
        painter.drawEllipse(
            center.x() - highlight_offset,
            center.y() - highlight_offset,
            highlight_radius,
            highlight_radius
        )
        
        # Draw inner core
        core_radius = int(sphere_radius * 0.3)
        core_gradient = QRadialGradient(center, core_radius)
        core_gradient.setColorAt(0, QColor(255, 255, 255, 200))
        core_gradient.setColorAt(1, QColor(color[0], color[1], color[2], 200))
        painter.setBrush(QBrush(core_gradient))
        painter.drawEllipse(center, core_radius, core_radius)

class SevenSphereWindow(QMainWindow):
    """Main window with sphere visualization"""
    
    def __init__(self, seven_core=None):
        super().__init__()
        self.seven_core = seven_core
        self.setWindowTitle("SEVEN AI Assistant")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: #000000;")
        
        # Connect to SEVEN core if provided
        if self.seven_core:
            self.seven_core.visualizer = self
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Top bar
        top_bar = self.create_top_bar()
        main_layout.addWidget(top_bar)
        
        # Stacked widget
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        # Create screens
        self.home_screen = self.create_home_screen()
        self.chat_screen = self.create_chat_screen()
        
        self.stacked_widget.addWidget(self.home_screen)
        self.stacked_widget.addWidget(self.chat_screen)
        
        # Status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(100)
        
        # Audio simulation
        self.current_audio_level = 0
        self.audio_timer = QTimer()
        self.audio_timer.timeout.connect(self.simulate_audio)
        self.audio_timer.start(50)
        
        # Show home screen
        self.stacked_widget.setCurrentIndex(0)
    
    def create_top_bar(self):
        """Create top bar with controls"""
        top_widget = QWidget()
        top_widget.setFixedHeight(50)
        top_widget.setStyleSheet("background-color: #111111;")
        
        layout = QHBoxLayout()
        top_widget.setLayout(layout)
        
        title = QLabel("⚡ SEVEN AI Assistant")
        title.setStyleSheet("color: #00aaff; font-size: 18px; font-weight: bold; padding-left: 10px;")
        layout.addWidget(title)
        
        layout.addStretch()
        
        home_btn = QPushButton("🏠 Home")
        home_btn.setStyleSheet("""
            QPushButton {
                background-color: #00aaff;
                color: black;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0088cc; }
        """)
        home_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        
        chat_btn = QPushButton("💬 Chats")
        chat_btn.setStyleSheet("""
            QPushButton {
                background-color: #00aaff;
                color: black;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #0088cc; }
        """)
        chat_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        
        layout.addWidget(home_btn)
        layout.addWidget(chat_btn)
        
        layout.addStretch()
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff3333;
                color: white;
                border: none;
                border-radius: 5px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: #ff0000; }
        """)
        close_btn.clicked.connect(self.close_app)
        
        layout.addWidget(close_btn)
        
        return top_widget
    
    def create_home_screen(self):
        """Create home screen with animated sphere"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        
        self.sphere = AnimatedSphere()
        layout.addWidget(self.sphere, alignment=Qt.AlignCenter)
        
        self.status_label = QLabel("SEVEN Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #00aaff; font-size: 18px; margin-top: 20px;")
        layout.addWidget(self.status_label)
        
        hint_label = QLabel("Say 'Seven' to activate")
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setStyleSheet("color: #666666; font-size: 12px; margin-top: 10px;")
        layout.addWidget(hint_label)
        
        widget.setLayout(layout)
        return widget
    
    def create_chat_screen(self):
        """Create chat screen"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #000000;
                color: #00aaff;
                border: 1px solid #00aaff;
                border-radius: 10px;
                padding: 10px;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.chat_display)
        
        input_layout = QHBoxLayout()
        self.input_field = QTextEdit()
        self.input_field.setMaximumHeight(60)
        self.input_field.setPlaceholderText("Type your message here...")
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: #111111;
                color: #00aaff;
                border: 1px solid #00aaff;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        
        send_btn = QPushButton("Send")
        send_btn.setStyleSheet("""
            QPushButton {
                background-color: #00aaff;
                color: black;
                border: none;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
            }
        """)
        send_btn.clicked.connect(self.send_message)
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(send_btn)
        layout.addLayout(input_layout)
        
        widget.setLayout(layout)
        return widget
    
    def send_message(self):
        """Send text message to SEVEN"""
        message = self.input_field.toPlainText().strip()
        if message and self.seven_core:
            self.add_chat_message("You", message)
            self.input_field.clear()
            
            # Process command
            self.sphere.set_state("processing")
            response = self.seven_core._process_command(message)
            self.add_chat_message("SEVEN", response)
            self.sphere.set_state("idle")
    
    def add_chat_message(self, sender, message):
        """Add message to chat display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color = "#00aaff" if sender == "SEVEN" else "#ffffff"
        self.chat_display.append(f"<font color='{color}'><b>[{timestamp}] {sender}:</b> {message}</font>")
        # Auto-scroll
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )
    
    def update_status(self):
        """Update status from SEVEN core"""
        if self.seven_core:
            if hasattr(self.seven_core, 'is_listening') and self.seven_core.is_listening:
                self.sphere.set_state("listening", self.current_audio_level)
                self.status_label.setText("🎤 Listening...")
            elif hasattr(self.seven_core, 'is_speaking') and self.seven_core.is_speaking:
                self.sphere.set_state("speaking", 0.7)
                self.status_label.setText("🔊 Speaking...")
            else:
                self.sphere.set_state("idle", 0)
                self.status_label.setText("SEVEN Ready")
    
    def simulate_audio(self):
        """Simulate audio level"""
        if self.sphere.state == "listening":
            self.current_audio_level = 0.3 + random.random() * 0.5
            self.sphere.audio_level = self.current_audio_level
        elif self.sphere.state == "speaking":
            self.current_audio_level = 0.5 + math.sin(datetime.now().timestamp() * 20) * 0.3
            self.sphere.audio_level = self.current_audio_level
        else:
            self.current_audio_level = 0
            self.sphere.audio_level = 0
    
    def close_app(self):
        """Close application"""
        if self.seven_core:
            self.seven_core.running = False
        self.close()

def run_sphere_visualizer(seven_core=None):
    """Run SEVEN with sphere visualizer"""
    app = QApplication(sys.argv)
    window = SevenSphereWindow(seven_core=seven_core)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run_sphere_visualizer()