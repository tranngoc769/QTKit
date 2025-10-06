#!/usr/bin/env python3
import sys
import re
import time
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                              QWidget, QLabel, QSystemTrayIcon, QMenu, QToolTip)
from PySide6.QtCore import QTimer, Qt, Signal, QThread
from PySide6.QtGui import QIcon, QPixmap, QFont, QAction, QCursor
from pynput import keyboard

class CmdCMonitor(QThread):
    """Monitor Cmd+C key combination"""
    cmd_c_pressed = Signal()
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.cmd_pressed = False
        self.listener = None
        
    def run(self):
        """Start keyboard listener"""
        try:
            self.listener = keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release
            )
            self.listener.start()
            
            while self.running:
                self.msleep(100)
                
        except Exception as e:
            print(f"Keyboard listener error: {e}")
    
    def on_key_press(self, key):
        """Handle key press"""
        try:
            if key == keyboard.Key.cmd:
                self.cmd_pressed = True
            elif (self.cmd_pressed and 
                  hasattr(key, 'char') and 
                  key.char and key.char.lower() == 'c'):
                print("🎯 Cmd+C detected!")
                self.cmd_c_pressed.emit()
        except AttributeError:
            pass
    
    def on_key_release(self, key):
        """Handle key release"""
        try:
            if key == keyboard.Key.cmd:
                self.cmd_pressed = False
        except AttributeError:
            pass
    
    def stop(self):
        """Stop monitoring"""
        self.running = False
        if self.listener:
            self.listener.stop()

class SimpleTimestampViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.last_clipboard_text = ""
        self.setup_ui()
        self.setup_tray()
        self.setup_cmd_c_monitoring()
        
    def setup_ui(self):
        """Setup simple UI"""
        self.setWindowTitle("Timestamp Viewer")
        self.setGeometry(100, 100, 400, 200)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        title = QLabel("🕐 Timestamp Viewer")
        title.setStyleSheet("font-size: 18px; font-weight: bold; text-align: center; margin: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        instructions = QLabel("🎯 Cmd+C timestamp → Tooltip hiện ngay!\n⚡ Hoạt động với mọi timestamp, kể cả text trùng!")
        instructions.setStyleSheet("color: #34495e; text-align: center; margin: 10px; padding: 10px; background-color: #f8f9fa; border-radius: 5px;")
        instructions.setAlignment(Qt.AlignCenter)
        layout.addWidget(instructions)
        
    def setup_tray(self):
        """Setup system tray"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
            
        self.tray_icon = QSystemTrayIcon(self)
        
        # Simple icon
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.blue)
        self.tray_icon.setIcon(QIcon(pixmap))
        
        # Tray menu
        tray_menu = QMenu()
        
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.setToolTip("Timestamp Viewer")
        
    def setup_cmd_c_monitoring(self):
        """Setup Cmd+C key monitoring"""
        self.cmd_monitor = CmdCMonitor()
        self.cmd_monitor.cmd_c_pressed.connect(self.on_cmd_c_detected)
        self.cmd_monitor.start()
        
        # Setup tooltip font
        QToolTip.setFont(QFont("Monaco", 13, QFont.Bold))
        
        print("🎯 Monitoring Cmd+C keypresses...")
        
    def on_cmd_c_detected(self):
        """Handle Cmd+C detection"""
        # Wait a moment for clipboard to update
        QTimer.singleShot(200, self.check_clipboard_for_timestamp)
        
    def check_clipboard_for_timestamp(self):
        """Check clipboard specifically for timestamp after Cmd+C"""
        try:
            clipboard = QApplication.clipboard()
            current_text = clipboard.text().strip()
            
            if current_text and self.is_timestamp(current_text):
                self.show_tooltip(current_text)
                print(f"✅ Timestamp detected via Cmd+C: {current_text}")
            else:
                print(f"ℹ️ Non-timestamp copied: {current_text[:30]}..." if current_text else "Empty clipboard")
                
        except Exception as e:
            print(f"Error checking clipboard: {e}")
        

    def is_timestamp(self, text):
        """Check if text is a timestamp"""
        # Kiểm tra độ dài: 10-20 ký tự
        if len(text) < 10 or len(text) > 20:
            return False
        
        # Kiểm tra xem có phải là số float không
        try:
            float(text)
        except ValueError:
            return False
        
        # Nếu là số float hợp lệ và đúng độ dài, coi là timestamp
        return True
    
    def show_tooltip(self, timestamp_str):
        """Show tooltip at cursor position"""
        try:
            # Convert timestamp
            gmt_str, vn_str = self.convert_timestamp(timestamp_str)
            
            # Create tooltip text
            tooltip_text = f"🌍 GMT: {gmt_str}\n🇻🇳 VN:  {vn_str}"
            
            # Hide any existing tooltip first
            QToolTip.hideText()
            
            # Show at cursor position with consistent timing
            cursor_pos = QCursor.pos()
            QToolTip.showText(cursor_pos, tooltip_text)
            
            # Set consistent auto-hide timer (3 seconds)
            if hasattr(self, 'tooltip_timer'):
                self.tooltip_timer.stop()
            
            self.tooltip_timer = QTimer()
            self.tooltip_timer.setSingleShot(True)
            self.tooltip_timer.timeout.connect(QToolTip.hideText)
            self.tooltip_timer.start(3000)  # 3 seconds consistent
                
        except Exception as e:
            print(f"Error showing tooltip: {e}")
            
    def convert_timestamp(self, timestamp_str):
        """Convert timestamp to GMT and VN time"""
        try:
            # Parse as float
            unix_time = float(timestamp_str)
            
            # Kiểm tra xem có phần thập phân không
            has_decimal = '.' in timestamp_str
            
            # Nếu số lớn hơn 1e12, coi như milliseconds
            if unix_time > 1e12:
                unix_time = unix_time / 1000
            
            # Convert to datetime
            gmt_dt = datetime.utcfromtimestamp(unix_time)
            vn_dt = datetime.fromtimestamp(unix_time)
            
            # Format output - hiển thị millisecond nếu có phần thập phân
            if has_decimal:
                gmt_str = gmt_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # Cắt bớt microsecond thành millisecond
                vn_str = vn_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]    # Cắt bớt microsecond thành millisecond
            else:
                gmt_str = gmt_dt.strftime('%Y-%m-%d %H:%M:%S')
                vn_str = vn_dt.strftime('%Y-%m-%d %H:%M:%S')
            
            return gmt_str, vn_str
            
        except Exception as e:
            return f"Error: {str(e)}", f"Error: {str(e)}"
    
    def closeEvent(self, event):
        """Handle close event"""
        if self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self.quit_app()
    
    def quit_app(self):
        """Quit application"""
        if hasattr(self, 'clipboard_timer'):
            self.clipboard_timer.stop()
        if hasattr(self, 'tooltip_timer'):
            self.tooltip_timer.stop()
        if hasattr(self, 'cmd_monitor'):
            self.cmd_monitor.stop()
        if hasattr(self, 'tray_icon'):
            self.tray_icon.hide()
        QApplication.quit()

def main():
    app = QApplication(sys.argv)
    
    # App settings
    app.setApplicationName("Simple Timestamp Viewer")
    app.setQuitOnLastWindowClosed(False)
    
    # Hide dock icon on macOS
    if sys.platform == "darwin":
        try:
            import AppKit
            AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
        except ImportError:
            pass
    
    # Create viewer
    viewer = SimpleTimestampViewer()
    
    print("🚀 Simple Timestamp Viewer started!")
    print("📋 Copy any timestamp to see the magic!")
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
