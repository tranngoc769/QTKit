#!/usr/bin/env python3
import sys
import re
import time
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                              QWidget, QLabel, QSystemTrayIcon, QMenu, QToolTip, 
                              QCheckBox, QSpinBox, QGroupBox, QPushButton)
from PySide6.QtCore import QTimer, Qt, Signal, QThread, QSettings, QPoint
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
        self.settings = QSettings("TimestampViewer", "Settings")
        self.load_settings()
        self.setup_ui()
        self.setup_tray()
        self.setup_cmd_c_monitoring()
    
    def load_settings(self):
        """Load settings from QSettings"""
        self.show_decimal = self.settings.value("show_decimal", True, type=bool)
        self.decimal_places = self.settings.value("decimal_places", 3, type=int)
        self.show_full_decimal = self.settings.value("show_full_decimal", False, type=bool)
        self.detect_mode = self.settings.value("detect_mode", False, type=bool)
    
    def save_settings(self):
        """Save settings to QSettings"""
        self.settings.setValue("show_decimal", self.show_decimal)
        self.settings.setValue("decimal_places", self.decimal_places)
        self.settings.setValue("show_full_decimal", self.show_full_decimal)
        self.settings.setValue("detect_mode", self.detect_mode)
        
    def setup_ui(self):
        """Setup configuration UI"""
        self.setWindowTitle("Timestamp Viewer - Cấu hình")
        self.setGeometry(100, 100, 450, 400)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Title
        title = QLabel("🕐 Timestamp Viewer - Cấu hình")
        title.setStyleSheet("font-size: 18px; font-weight: bold; text-align: center; margin: 20px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Decimal settings group
        decimal_group = QGroupBox("⚙️ Cấu hình hiển thị thập phân")
        decimal_layout = QVBoxLayout(decimal_group)
        
        # Show decimal checkbox
        self.show_decimal_cb = QCheckBox("Hiển thị phần thập phân")
        self.show_decimal_cb.setChecked(self.show_decimal)
        self.show_decimal_cb.toggled.connect(self.on_show_decimal_changed)
        decimal_layout.addWidget(self.show_decimal_cb)
        
        # Decimal places
        decimal_places_layout = QHBoxLayout()
        decimal_places_layout.addWidget(QLabel("Số chữ số thập phân:"))
        self.decimal_places_spin = QSpinBox()
        self.decimal_places_spin.setRange(0, 6)
        self.decimal_places_spin.setValue(self.decimal_places)
        self.decimal_places_spin.valueChanged.connect(self.on_decimal_places_changed)
        decimal_places_layout.addWidget(self.decimal_places_spin)
        decimal_places_layout.addStretch()
        decimal_layout.addLayout(decimal_places_layout)
        
        # Full decimal checkbox
        self.show_full_decimal_cb = QCheckBox("Hiển thị toàn bộ phần thập phân gốc (không padding - bỏ qua cài đặt trên)")
        self.show_full_decimal_cb.setChecked(self.show_full_decimal)
        self.show_full_decimal_cb.toggled.connect(self.on_show_full_decimal_changed)
        decimal_layout.addWidget(self.show_full_decimal_cb)
        
        layout.addWidget(decimal_group)
        
        # Detection mode group
        detect_group = QGroupBox("🔍 Chế độ detect timestamp")
        detect_layout = QVBoxLayout(detect_group)
        
        self.detect_mode_cb = QCheckBox("Detect timestamp trong clipboard (tự động tìm số giống timestamp)")
        self.detect_mode_cb.setChecked(self.detect_mode)
        self.detect_mode_cb.toggled.connect(self.on_detect_mode_changed)
        detect_layout.addWidget(self.detect_mode_cb)
        
        detect_info = QLabel("• Bật: Tự động tìm timestamp trong text dài\n• Tắt: Chỉ detect khi toàn bộ clipboard là timestamp")
        detect_info.setStyleSheet("color: #666; font-size: 12px; margin-left: 20px;")
        detect_layout.addWidget(detect_info)
        
        layout.addWidget(detect_group)
        
        # Status
        status_label = QLabel("🎯 Cmd+C timestamp → Tooltip hiện ngay!\n⚡ App đang chạy ngầm...")
        status_label.setStyleSheet("color: #27ae60; text-align: center; margin: 15px; padding: 10px; background-color: #f8f9fa; border-radius: 5px;")
        status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        hide_btn = QPushButton("Ẩn cửa sổ")
        hide_btn.clicked.connect(self.hide)
        button_layout.addWidget(hide_btn)
        
        quit_btn = QPushButton("Thoát ứng dụng")
        quit_btn.clicked.connect(self.quit_app)
        quit_btn.setStyleSheet("background-color: #e74c3c; color: white;")
        button_layout.addWidget(quit_btn)
        
        layout.addLayout(button_layout)
        
        # Update UI state
        self.update_decimal_ui_state()
        
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
        
        config_action = QAction("⚙️ Cấu hình", self)
        config_action.triggered.connect(self.show)
        tray_menu.addAction(config_action)
        
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
    
    def on_show_decimal_changed(self, checked):
        """Handle show decimal checkbox change"""
        self.show_decimal = checked
        self.update_decimal_ui_state()
        self.save_settings()
    
    def on_decimal_places_changed(self, value):
        """Handle decimal places change"""
        self.decimal_places = value
        self.save_settings()
    
    def on_show_full_decimal_changed(self, checked):
        """Handle show full decimal checkbox change"""
        self.show_full_decimal = checked
        self.update_decimal_ui_state()
        self.save_settings()
    
    def on_detect_mode_changed(self, checked):
        """Handle detect mode checkbox change"""
        self.detect_mode = checked
        self.save_settings()
    
    def update_decimal_ui_state(self):
        """Update decimal UI elements state"""
        if hasattr(self, 'decimal_places_spin'):
            # Disable decimal places when show_decimal is off or show_full_decimal is on
            self.decimal_places_spin.setEnabled(self.show_decimal and not self.show_full_decimal)
        
    def on_cmd_c_detected(self):
        """Handle Cmd+C detection"""
        # Wait a moment for clipboard to update
        QTimer.singleShot(200, self.check_clipboard_for_timestamp)
        
    def check_clipboard_for_timestamp(self):
        """Check clipboard specifically for timestamp after Cmd+C"""
        try:
            clipboard = QApplication.clipboard()
            current_text = clipboard.text().strip()
            
            if current_text:
                timestamp_str, is_valid = self.get_timestamp(current_text)
                if is_valid:
                    self.show_tooltip(timestamp_str)
                    print(f"✅ Timestamp detected via Cmd+C: {timestamp_str}")
                else:
                    print(f"ℹ️ Non-timestamp copied: {current_text[:30]}...")
            else:
                print("Empty clipboard")
                
        except Exception as e:
            print(f"Error checking clipboard: {e}")
        

    def get_timestamp(self, text):
        """Extract timestamp from text and check if valid
        Returns: (timestamp_string, is_valid_timestamp)
        """
        text = text.strip()
        
        # Chế độ detect: tìm timestamp trong text
        if hasattr(self, 'detect_mode') and self.detect_mode:
            # Tìm các số có độ dài 10-20 ký tự trong text
            import re
            patterns = [
                r'\b\d{10,13}\.\d+\b',  # timestamp với thập phân
                r'\b\d{10,13}\b',       # timestamp nguyên
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text)
                if matches:
                    candidate = matches[0]
                    if self._is_valid_timestamp(candidate):
                        return candidate, True
            
            return text, False
        else:
            # Chế độ thông thường: kiểm tra toàn bộ text
            return text, self._is_valid_timestamp(text)
    
    def _is_valid_timestamp(self, text):
        """Check if text is a valid timestamp"""
        # Kiểm tra độ dài: 10-20 ký tự
        if len(text) < 10 or len(text) > 20:
            return False
        
        # Kiểm tra xem có phải là số float không
        try:
            timestamp_val = float(text)
            # Kiểm tra range hợp lý cho timestamp (1970-2050)
            if timestamp_val > 1e12:  # milliseconds
                timestamp_val = timestamp_val / 1000
            return 946684800 <= timestamp_val <= 2524608000  # 2000-2050
        except ValueError:
            return False
    
    def show_tooltip(self, timestamp_str):
        """Show tooltip at cursor position"""
        try:
            # Convert timestamp
            gmt_str, vn_str = self.convert_timestamp(timestamp_str)
            
            # Create tooltip text
            tooltip_text = f"🌍 GMT: {gmt_str}\n🇻🇳 VN:  {vn_str}"
            
            # Hide any existing tooltip first
            QToolTip.hideText()
            
            # Show at cursor position with offset (above and to the right)
            cursor_pos = QCursor.pos()
            # Điều chỉnh vị trí: sang phải 40px, lên trên 70px (không che timestamp)
            tooltip_pos = QPoint(cursor_pos.x() + 40, cursor_pos.y() - 70)
            QToolTip.showText(tooltip_pos, tooltip_text)
            
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
            
            # Kiểm tra xem có phần thập phân không và extract phần thập phân gốc
            has_decimal = '.' in timestamp_str
            original_decimal = ""
            if has_decimal:
                original_decimal = timestamp_str.split('.')[1].rstrip('0')  # Loại bỏ trailing zeros
            
            # Nếu số lớn hơn 1e12, coi như milliseconds
            if unix_time > 1e12:
                unix_time = unix_time / 1000
            
            # Convert to datetime
            gmt_dt = datetime.utcfromtimestamp(unix_time)
            vn_dt = datetime.fromtimestamp(unix_time)
            
            # Format output dựa trên settings
            if self.show_decimal and has_decimal and original_decimal:
                if self.show_full_decimal:
                    # Hiển thị chính xác phần thập phân gốc
                    gmt_str = gmt_dt.strftime('%Y-%m-%d %H:%M:%S') + f".{original_decimal}"
                    vn_str = vn_dt.strftime('%Y-%m-%d %H:%M:%S') + f".{original_decimal}"
                else:
                    # Hiển thị theo số chữ số cấu hình từ phần thập phân gốc
                    decimal_part = original_decimal[:self.decimal_places]
                    if decimal_part:
                        gmt_str = gmt_dt.strftime('%Y-%m-%d %H:%M:%S') + f".{decimal_part}"
                        vn_str = vn_dt.strftime('%Y-%m-%d %H:%M:%S') + f".{decimal_part}"
                    else:
                        gmt_str = gmt_dt.strftime('%Y-%m-%d %H:%M:%S')
                        vn_str = vn_dt.strftime('%Y-%m-%d %H:%M:%S')
            else:
                # Không hiển thị phần thập phân
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
