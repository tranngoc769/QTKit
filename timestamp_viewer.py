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
        # Unix timestamp (10 or 13 digits)
        if re.match(r'^\d{10}$', text) or re.match(r'^\d{13}$', text):
            return True
            
        # Common timestamp formats
        patterns = [
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # ISO 8601
            r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',   # SQL format  
            r'^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}',   # US format
        ]
        
        for pattern in patterns:
            if re.match(pattern, text):
                return True
                
        return False
    
    def show_tooltip(self, timestamp_str):
        """Show tooltip at cursor position"""
        try:
            # Convert timestamp
            gmt_str, vn_str = self.convert_timestamp(timestamp_str)
            
            # Create tooltip text
            tooltip_text = f"🌍 GMT: {gmt_str}\n🇻🇳 VN:  {vn_str}"
            
            # Show at cursor position
            cursor_pos = QCursor.pos()
            QToolTip.showText(cursor_pos, tooltip_text)
            
            # Auto hide after 4 seconds
            QTimer.singleShot(4000, QToolTip.hideText)
            
            # Show tray notification
            if self.tray_icon:
                self.tray_icon.showMessage(
                    "Timestamp Detected!",
                    f"Converted: {timestamp_str}",
                    QSystemTrayIcon.Information,
                    2000
                )
                
        except Exception as e:
            print(f"Error showing tooltip: {e}")
            
    def convert_timestamp(self, timestamp_str):
        """Convert timestamp to GMT and VN time"""
        try:
            if re.match(r'^\d{10}$', timestamp_str):
                # Unix timestamp (seconds)
                unix_time = int(timestamp_str)
                gmt_dt = datetime.utcfromtimestamp(unix_time)
                vn_dt = datetime.fromtimestamp(unix_time)
                
            elif re.match(r'^\d{13}$', timestamp_str):
                # Unix timestamp (milliseconds)
                unix_time = int(timestamp_str) / 1000
                gmt_dt = datetime.utcfromtimestamp(unix_time)
                vn_dt = datetime.fromtimestamp(unix_time)
                
            else:
                # Try to parse other formats
                try:
                    if 'T' in timestamp_str:
                        clean_timestamp = re.sub(r'[+-]\d{2}:?\d{2}$|Z$', '', timestamp_str)
                        dt = datetime.fromisoformat(clean_timestamp)
                    else:
                        # Try common formats
                        formats = ['%Y-%m-%d %H:%M:%S', '%m/%d/%Y %H:%M:%S', '%d-%m-%Y %H:%M:%S']
                        dt = None
                        for fmt in formats:
                            try:
                                dt = datetime.strptime(timestamp_str, fmt)
                                break
                            except ValueError:
                                continue
                        if not dt:
                            raise ValueError("Unable to parse timestamp")
                    
                    gmt_dt = dt
                    vn_dt = dt
                    
                except ValueError:
                    return "Invalid format", "Invalid format"
            
            # Format output
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
