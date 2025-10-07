#!/usr/bin/env python3
import sys
import re
import time
import logging
import os
from datetime import datetime

# Version expiration check
VERSION_EXPIRY_TIMESTAMP = 1762497441  # Test timestamp - expires before current time
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                              QWidget, QLabel, QSystemTrayIcon, QMenu, QToolTip, 
                              QCheckBox, QSpinBox, QGroupBox, QPushButton, QMessageBox,
                              QTextEdit, QScrollArea, QSplitter, QFrame, QTabWidget,
                              QListWidget, QListWidgetItem, QDialog)
from PySide6.QtCore import QTimer, Qt, Signal, QThread, QSettings, QPoint, QDateTime, QUrl
from PySide6.QtGui import QIcon, QPixmap, QFont, QAction, QCursor, QColor, QPalette, QDesktopServices
from pynput import keyboard

# In-memory log storage for UI
UI_LOGS = []
MAX_UI_LOGS = 50

class UILogHandler(logging.Handler):
    """Custom log handler for UI display"""
    def emit(self, record):
        global UI_LOGS
        if len(UI_LOGS) >= MAX_UI_LOGS:
            UI_LOGS.pop(0)  # Remove oldest log
        
        # Format the log message
        formatted = self.format(record)
        UI_LOGS.append({
            'timestamp': record.created,
            'level': record.levelname,
            'message': record.getMessage(),
            'formatted': formatted
        })

# Setup logging
def setup_logging():
    """Setup logging - reduced file logging, enhanced UI logging"""
    # Create logs directory if not exists
    log_dir = os.path.expanduser("~/Library/Logs/QTKit")
    os.makedirs(log_dir, exist_ok=True)
    
    # Log file path
    log_file = os.path.join(log_dir, "qtkit.log")
    
    # Create custom formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # File handler - only for INFO and ERROR
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # UI handler - for all logs
    ui_handler = UILogHandler()
    ui_handler.setLevel(logging.INFO)
    ui_handler.setFormatter(formatter)
    
    # Setup root logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()  # Clear any existing handlers
    logger.addHandler(file_handler)
    logger.addHandler(ui_handler)
    
    # Startup message
    logger.info("🚀 QTKit starting up...")
    logger.info(f"📁 Log file: {log_file}")
    
    return logger

# Initialize logger
logger = setup_logging()

class CmdCMonitor(QThread):
    """Monitor Cmd+C key combination"""
    cmd_c_pressed = Signal()
    permission_needed = Signal()
    
    def __init__(self):
        super().__init__()
        self.running = True
        self.cmd_pressed = False
        self.listener = None
        self.permission_checked = False
        
    def check_accessibility_permission(self):
        """Check if accessibility permission is granted on macOS"""
        try:
            import subprocess
            import sys
            
            if sys.platform == 'darwin':  # macOS
                # Method 1: Try creating keyboard listener to test permissions
                try:
                    test_listener = keyboard.Listener(on_press=lambda key: None)
                    test_listener.start()
                    test_listener.stop()
                    logger.info("✅ Accessibility permissions are granted")
                    return True
                except Exception as e:
                    error_msg = str(e).lower()
                    if any(word in error_msg for word in ["not trusted", "accessibility", "permission", "denied"]):
                        logger.warning("⚠️ Accessibility permissions not granted")
                        return False
                    else:
                        # Method 2: Check via system command as fallback
                        try:
                            result = subprocess.run([
                                "osascript", "-e", 
                                'tell application "System Events" to get application processes'
                            ], capture_output=True, text=True, timeout=5)
                            
                            if result.returncode == 0:
                                logger.info("✅ System Events accessible - permissions OK")
                                return True
                            else:
                                logger.warning("⚠️ System Events not accessible - permissions needed")
                                return False
                        except:
                            # If all methods fail, assume permissions needed
                            logger.warning("⚠️ Cannot verify permissions - assuming needed")
                            return False
            else:
                # Non-macOS systems typically don't need special permissions
                return True
                
        except Exception as e:
            logger.error(f"❌ Error checking accessibility permission: {e}")
            return False
    
    def run(self):
        """Start keyboard listener"""
        try:
            logger.info("🔧 Starting keyboard listener...")
            
            # Check permissions first
            if not self.check_accessibility_permission():
                logger.warning("⚠️ Missing accessibility permissions")
                self.permission_needed.emit()
                # Continue running but without actual monitoring
                while self.running:
                    self.msleep(1000)
                return
            
            self.listener = keyboard.Listener(
                on_press=self.on_key_press,
                on_release=self.on_key_release
            )
            self.listener.start()
            logger.info("🎧 Keyboard listener started")
            
            while self.running:
                self.msleep(100)
                
        except Exception as e:
            logger.error(f"❌ Keyboard listener error: {e}")
            logger.warning("💡 This usually means accessibility permissions are needed")
            if not self.permission_checked and ("not trusted" in str(e).lower() or "accessibility" in str(e).lower()):
                self.permission_needed.emit()
                self.permission_checked = True
            # Try to continue anyway
            while self.running:
                self.msleep(1000)
    
    def on_key_press(self, key):
        """Handle key press"""
        try:
            if key == keyboard.Key.cmd:
                self.cmd_pressed = True
            elif (self.cmd_pressed and 
                  hasattr(key, 'char') and 
                  key.char and key.char.lower() == 'c'):
                logger.info("🎯 Cmd+C detected!")
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

class LogViewerWindow(QDialog):
    """Log viewer window for debugging"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QTKit - Log Viewer")
        self.setGeometry(200, 200, 800, 600)
        
        # Set window flags to stay on top
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        
        self.setup_ui()
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_logs)
        self.update_timer.start(1000)  # Update every second
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("📋 QTKit Log Viewer")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # Log display
        # Connect close event for cleanup
        self.setAttribute(Qt.WA_DeleteOnClose, False)  # Don't delete, just hide
        
        self.log_display = QListWidget()
        self.log_display.setStyleSheet("""
            QListWidget {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: monospace;
                font-size: 12px;
                border: 1px solid #555;
            }
            QListWidgetItem {
                padding: 2px 5px;
                border-bottom: 1px solid #444;
            }
        """)
        layout.addWidget(self.log_display)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.auto_scroll_cb = QCheckBox("Auto-scroll")
        self.auto_scroll_cb.setChecked(True)
        controls_layout.addWidget(self.auto_scroll_cb)
        
        clear_btn = QPushButton("Clear Logs")
        clear_btn.clicked.connect(self.clear_logs)
        controls_layout.addWidget(clear_btn)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_logs)
        controls_layout.addWidget(refresh_btn)
        
        controls_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        controls_layout.addWidget(close_btn)
        
        layout.addLayout(controls_layout)
        
        # Initial load
        self.refresh_logs()
    
    def refresh_logs(self):
        """Refresh log display from UI_LOGS"""
        current_count = self.log_display.count()
        global UI_LOGS
        
        # Only add new logs to avoid flickering
        if len(UI_LOGS) > current_count:
            for log_entry in UI_LOGS[current_count:]:
                item = QListWidgetItem()
                
                # Color code by level
                level_colors = {
                    'INFO': '#4CAF50',     # Green
                    'WARNING': '#FF9800',  # Orange  
                    'ERROR': '#F44336',    # Red
                    'DEBUG': '#2196F3'     # Blue
                }
                
                color = level_colors.get(log_entry['level'], '#ffffff')
                
                # Format timestamp
                dt = QDateTime.fromSecsSinceEpoch(int(log_entry['timestamp']))
                time_str = dt.toString("hh:mm:ss")
                
                # Set item text and color
                item.setText(f"[{time_str}] {log_entry['level']}: {log_entry['message']}")
                item.setForeground(QColor(color))
                
                self.log_display.addItem(item)
        
        # Auto-scroll to bottom if enabled
        if self.auto_scroll_cb.isChecked():
            self.log_display.scrollToBottom()
    
    def clear_logs(self):
        """Clear both UI logs and display"""
        global UI_LOGS
        UI_LOGS.clear()
        self.log_display.clear()

class PermissionsWindow(QDialog):
    """Permissions checker and manager window"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QTKit - Permissions Manager")
        self.setGeometry(300, 300, 600, 500)
        
        # Set window flags to stay on top
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        
        self.setup_ui()
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.refresh_permissions)
        self.check_timer.start(3000)  # Check every 3 seconds
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("🔐 QTKit Permissions Manager")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)
        
        # Info text
        info = QLabel("QTKit cần các quyền sau để hoạt động đầy đủ:")
        info.setStyleSheet("padding: 5px; color: #666;")
        layout.addWidget(info)
        
        # Permissions list
        self.permissions_widget = QWidget()
        self.permissions_layout = QVBoxLayout(self.permissions_widget)
        layout.addWidget(self.permissions_widget)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_permissions)
        buttons_layout.addWidget(refresh_btn)
        
        open_settings_btn = QPushButton("⚙️ Open System Settings")
        open_settings_btn.clicked.connect(self.open_system_settings) 
        buttons_layout.addWidget(open_settings_btn)
        
        buttons_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
        
        # Initial check
        self.refresh_permissions()
    
    def refresh_permissions(self):
        """Check and display current permission status"""
        # Clear existing widgets
        for i in reversed(range(self.permissions_layout.count())):
            self.permissions_layout.itemAt(i).widget().setParent(None)
        
        permissions = [
            {
                'name': 'Accessibility',
                'description': 'Để theo dõi phím tắt Cmd+C',
                'check_func': self.check_accessibility_permission
            },
            {
                'name': 'Input Monitoring', 
                'description': 'Để phát hiện keyboard events',
                'check_func': self.check_input_monitoring_permission
            }
        ]
        
        for perm in permissions:
            self.add_permission_widget(perm)
    
    def add_permission_widget(self, permission):
        """Add a permission status widget"""
        container = QFrame()
        container.setFrameStyle(QFrame.Box)
        container.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 5px;
                margin: 5px;
                padding: 10px;
            }
        """)
        
        layout = QHBoxLayout(container)
        
        # Permission info
        info_layout = QVBoxLayout()
        
        name_label = QLabel(f"🔐 {permission['name']}")
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        info_layout.addWidget(name_label)
        
        desc_label = QLabel(permission['description'])
        desc_label.setStyleSheet("color: #666; font-size: 12px;")
        info_layout.addWidget(desc_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # Status
        status_granted = permission['check_func']()
        
        if status_granted:
            status_label = QLabel("✅ Đã cấp quyền")
            status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            status_label = QLabel("❌ Chưa cấp quyền")  
            status_label.setStyleSheet("color: #F44336; font-weight: bold;")
        
        layout.addWidget(status_label)
        
        # Open settings button for this permission
        if not status_granted:
            open_btn = QPushButton("Mở Settings")
            open_btn.clicked.connect(lambda: self.open_permission_settings(permission['name']))
            layout.addWidget(open_btn)
        
        self.permissions_layout.addWidget(container)
    
    def check_accessibility_permission(self):
        """Check Accessibility permission"""
        try:
            test_listener = keyboard.Listener(on_press=lambda key: None)
            test_listener.start()
            test_listener.stop()
            return True
        except Exception as e:
            error_msg = str(e).lower()
            return not any(word in error_msg for word in ["not trusted", "accessibility", "permission", "denied"])
    
    def check_input_monitoring_permission(self):
        """Check Input Monitoring permission"""
        try:
            import subprocess
            result = subprocess.run([
                "osascript", "-e", 
                'tell application "System Events" to get application processes'
            ], capture_output=True, text=True, check=True, timeout=3)
            return result.returncode == 0
        except:
            return False
    
    def open_permission_settings(self, permission_name):
        """Open system settings for specific permission"""
        try:
            import subprocess
            
            if permission_name == "Accessibility":
                commands = [
                    ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
                    ["open", "/System/Library/PreferencePanes/Security.prefPane"]
                ]
            elif permission_name == "Input Monitoring":
                commands = [
                    ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"], 
                    ["open", "/System/Library/PreferencePanes/Security.prefPane"]
                ]
            else:
                commands = [
                    ["open", "/System/Library/PreferencePanes/Security.prefPane"]
                ]
            
            for cmd in commands:
                try:
                    subprocess.call(cmd)
                    break
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Failed to open settings: {e}")
    
    def open_system_settings(self):
        """Open general system settings"""
        try:
            import subprocess
            commands = [
                ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy"],
                ["open", "/System/Library/PreferencePanes/Security.prefPane"],
                ["open", "-b", "com.apple.preference.security"]
            ]
            
            for cmd in commands:
                try:
                    subprocess.call(cmd)
                    break
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Failed to open system settings: {e}")

class SimpleTimestampViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.last_clipboard_text = ""
        self.settings = QSettings("QTKit", "Settings")
        self.dock_icon_visible = False  # Track dock icon state
        self.load_settings()
        self.setup_ui()
        self.setup_tray()
        
        # Hide dock icon for tray-only app
        self.hide_dock_icon_if_needed()
        
        # Check version expiry FIRST before any other operations
        if self.check_version_expiry():
            self.show_version_expired_dialog()
            return  # Stop initialization if expired
        
        # Force request permissions on EVERY startup
        self.force_request_permissions()
        
        self.setup_cmd_c_monitoring()
        
        # Setup periodic expiry check timer (check every minute)
        self.expiry_timer = QTimer()
        self.expiry_timer.timeout.connect(self.check_expiry_periodically)
        self.expiry_timer.start(60000)  # Check every 60 seconds
        
        # Show config window on first run
        logger.info(f"🔍 First run status: {self.first_run}")
        if self.first_run:
            logger.info("🎯 Showing first run welcome...")
            # Delay first run welcome for smoother startup
            QTimer.singleShot(200, self.show_first_run_welcome)
        else:
            logger.info("👻 Not first run - running in background")
    
    def delayed_startup(self):
        """Delayed startup operations for better performance"""
        try:
            # Force request permissions on EVERY startup
            self.force_request_permissions()
            
            self.setup_cmd_c_monitoring()
        except Exception as e:
            logger.error(f"Error in delayed startup: {e}")
    
    def load_settings(self):
        """Load settings from QSettings"""
        self.show_decimal = self.settings.value("show_decimal", True, type=bool)
        self.decimal_places = self.settings.value("decimal_places", 3, type=int)
        self.show_full_decimal = self.settings.value("show_full_decimal", False, type=bool)
        self.detect_mode = self.settings.value("detect_mode", False, type=bool)  # Default False
        self.tooltip_duration = self.settings.value("tooltip_duration", 3, type=int)  # Default 3 seconds
        self.first_run = self.settings.value("first_run", True, type=bool)
    
    def save_settings(self):
        """Save settings to QSettings"""
        self.settings.setValue("show_decimal", self.show_decimal)
        self.settings.setValue("decimal_places", self.decimal_places)
        self.settings.setValue("show_full_decimal", self.show_full_decimal)
        self.settings.setValue("detect_mode", self.detect_mode)
        self.settings.setValue("tooltip_duration", self.tooltip_duration)
        # Don't automatically set first_run to False here
    
    def mark_first_run_completed(self):
        """Mark first run as completed"""
        self.first_run = False
        self.settings.setValue("first_run", False)
    
    def reset_first_run(self):
        """Reset first run for testing - can be called from terminal"""
        self.settings.setValue("first_run", True)
        logger.info("🔄 First run reset! Restart app to see welcome screen.")
        
    def setup_ui(self):
        """Setup configuration UI"""
        self.setWindowTitle("QTKit - Cấu hình")
        self.setGeometry(100, 100, 480, 580)
        
        # Set window style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f8f9fa;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin: 8px 0px;
                padding-top: 15px;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #495057;
            }
            QCheckBox {
                padding: 6px;
                font-size: 16px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QPushButton {
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 16px;
            }
            QSpinBox {
                padding: 4px 8px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
            }
        """)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        if hasattr(self, 'first_run') and self.first_run:
            title = QLabel("🎉 Chào mừng đến với QTKit!")
            title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin-bottom: 15px;")
        else:
            title = QLabel("⚙️ Cấu hình QTKit")
            title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; margin-bottom: 15px;")
        
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
            
        # Detection mode group (moved to top)
        detect_group = QGroupBox("🔍 Chế độ detect timestamp")
        detect_layout = QVBoxLayout(detect_group)
        detect_layout.setSpacing(10)
        detect_layout.setContentsMargins(15, 15, 15, 15)
        
        self.detect_mode_cb = QCheckBox("Detect timestamp trong clipboard")
        self.detect_mode_cb.setChecked(False)  # Not checked by default
        self.detect_mode_cb.toggled.connect(self.on_detect_mode_changed)
        self.detect_mode_cb.setStyleSheet("color: #495057;")
        detect_layout.addWidget(self.detect_mode_cb)
        
        # Info container with better styling
        detect_info_container = QWidget()
        detect_info_container.setStyleSheet("background-color: #e9ecef; border-radius: 6px; padding: 8px;")
        info_layout = QVBoxLayout(detect_info_container)
        info_layout.setContentsMargins(10, 8, 10, 8)
        
        info_on = QLabel("• Bật: Tự động tìm timestamp trong text dài")
        info_on.setStyleSheet("color: #495057; font-size: 16px; margin: 2px 0;")
        info_layout.addWidget(info_on)
        info_off = QLabel("• Tắt: Chỉ detect khi toàn bộ clipboard là timestamp")
        info_off.setStyleSheet("color: #495057; font-size: 16px; margin: 2px 0;")
        info_layout.addWidget(info_off)
        
        detect_layout.addWidget(detect_info_container)
        layout.addWidget(detect_group)
        
        # Decimal settings group
        decimal_group = QGroupBox("⚙️ Cấu hình hiển thị thập phân")
        decimal_layout = QVBoxLayout(decimal_group)
        decimal_layout.setSpacing(10)
        decimal_layout.setContentsMargins(15, 15, 15, 15)
        
        # Main decimal options container
        decimal_main_container = QWidget()
        decimal_main_layout = QHBoxLayout(decimal_main_container)
        decimal_main_layout.setContentsMargins(0, 0, 0, 0)
        decimal_main_layout.setSpacing(20)
        
        # Left side - Show decimal checkbox
        self.show_decimal_cb = QCheckBox("Hiển thị phần thập phân")
        self.show_decimal_cb.setChecked(self.show_decimal)
        self.show_decimal_cb.toggled.connect(self.on_show_decimal_changed)
        self.show_decimal_cb.setStyleSheet("color: #495057;")
        decimal_main_layout.addWidget(self.show_decimal_cb)
        
        # Right side - Decimal places (aligned with checkbox)
        decimal_places_container = QWidget()
        decimal_places_layout = QHBoxLayout(decimal_places_container)
        decimal_places_layout.setContentsMargins(0, 0, 0, 0)
        decimal_places_layout.setSpacing(8)
        
        decimal_label = QLabel("Số chữ số:")
        decimal_label.setStyleSheet("color: #6c757d; font-size: 16px;")
        decimal_places_layout.addWidget(decimal_label)
        
        self.decimal_places_spin = QSpinBox()
        self.decimal_places_spin.setRange(0, 6)
        self.decimal_places_spin.setValue(self.decimal_places)
        self.decimal_places_spin.valueChanged.connect(self.on_decimal_places_changed)
        self.decimal_places_spin.setFixedWidth(60)
        decimal_places_layout.addWidget(self.decimal_places_spin)
        decimal_places_layout.addStretch()
        
        decimal_main_layout.addWidget(decimal_places_container)
        decimal_main_layout.addStretch()
        
        decimal_layout.addWidget(decimal_main_container)
        
        # Full decimal checkbox
        self.show_full_decimal_cb = QCheckBox("Hiển thị toàn bộ phần thập phân gốc")
        self.show_full_decimal_cb.setChecked(self.show_full_decimal)
        self.show_full_decimal_cb.toggled.connect(self.on_show_full_decimal_changed)
        self.show_full_decimal_cb.setStyleSheet("color: #495057;")
        decimal_layout.addWidget(self.show_full_decimal_cb)
        
        # Add helper note
        helper_note = QLabel("(Bỏ qua cài đặt số chữ số bên trên)")
        helper_note.setStyleSheet("color: #6c757d; font-size: 14px; margin-left: 25px; margin-top: -5px;")
        decimal_layout.addWidget(helper_note)
        
        layout.addWidget(decimal_group)
        
        # Tooltip duration settings group
        tooltip_group = QGroupBox("⏱️ Cấu hình thời gian hiển thị tooltip")
        tooltip_layout = QVBoxLayout(tooltip_group)
        tooltip_layout.setSpacing(10)
        tooltip_layout.setContentsMargins(15, 15, 15, 15)
        
        # Tooltip duration container
        tooltip_duration_container = QWidget()
        tooltip_duration_layout = QHBoxLayout(tooltip_duration_container)
        tooltip_duration_layout.setContentsMargins(0, 0, 0, 0)
        tooltip_duration_layout.setSpacing(12)
        
        tooltip_duration_label = QLabel("Thời gian hiển thị (giây):")
        tooltip_duration_label.setStyleSheet("color: #495057; font-size: 16px;")
        tooltip_duration_layout.addWidget(tooltip_duration_label)
        
        self.tooltip_duration_spin = QSpinBox()
        self.tooltip_duration_spin.setRange(1, 10)
        self.tooltip_duration_spin.setValue(self.tooltip_duration)
        self.tooltip_duration_spin.valueChanged.connect(self.on_tooltip_duration_changed)
        self.tooltip_duration_spin.setFixedWidth(80)
        self.tooltip_duration_spin.setSuffix(" giây")
        tooltip_duration_layout.addWidget(self.tooltip_duration_spin)
        
        tooltip_duration_layout.addStretch()
        
        tooltip_layout.addWidget(tooltip_duration_container)
        
        # Info note
        tooltip_info = QLabel("Tooltip sẽ tự động ẩn sau thời gian này")
        tooltip_info.setStyleSheet("color: #6c757d; font-size: 14px; margin-left: 10px;")
        tooltip_layout.addWidget(tooltip_info)
        
        layout.addWidget(tooltip_group)
        
        # Add some spacing before trigger info
        layout.addStretch()
        
        # Trigger and warning info - minimal style
        trigger_container = QWidget()
        trigger_container.setStyleSheet("""
            background-color: #fff8e1;
            border-radius: 4px;
        """)
        trigger_layout = QVBoxLayout(trigger_container)
        trigger_layout.setContentsMargins(8, 6, 8, 6)
        trigger_layout.setSpacing(2)
        
        info_trigger = QLabel("⌨️ Sử dụng: Command + C")
        info_trigger.setStyleSheet("color: #f57c00; font-size: 12px; font-weight: bold;")
        trigger_layout.addWidget(info_trigger)
        
        info_warning = QLabel("⚠️ Nguyên lý: Theo dõi Cmd+C và kiểm tra clipboard")
        info_warning.setStyleSheet("color: #f57c00; font-size: 11px;")
        trigger_layout.addWidget(info_warning)
        
        layout.addWidget(trigger_container)
        
        # QT Corporation info section with logo
        qt_corp_container = QWidget()
        qt_corp_container.setStyleSheet("""
            background-color: #e3f2fd;
            border-radius: 6px;
        """)
        qt_corp_main_layout = QHBoxLayout(qt_corp_container)
        qt_corp_main_layout.setContentsMargins(12, 8, 12, 8)
        qt_corp_main_layout.setSpacing(12)
        
        # Logo on the left - bigger size with proper path handling
        logo_label = QLabel()
        try:
            import os
            # Try multiple possible paths for logo
            possible_paths = [
                "logo.png",
                os.path.join(os.path.dirname(__file__), "logo.png"),
                os.path.join(os.path.dirname(sys.executable), "logo.png"),
                os.path.join(sys._MEIPASS, "logo.png") if hasattr(sys, '_MEIPASS') else None
            ]
            
            logo_loaded = False
            for logo_path in possible_paths:
                if logo_path and os.path.exists(logo_path):
                    logger.info(f"🎨 Loading UI logo from: {logo_path}")
                    logo_pixmap = QPixmap(logo_path)
                    if not logo_pixmap.isNull():
                        # Scale logo to bigger size (64x64)
                        scaled_logo = logo_pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        logo_label.setPixmap(scaled_logo)
                        logo_loaded = True
                        break
            
            if not logo_loaded:
                logger.warning("⚠️ Could not load logo.png for UI, using fallback")
                # Fallback text if logo not found
                logo_label.setText("📱")
                logo_label.setStyleSheet("font-size: 40px;")
        except Exception as e:
            logger.error(f"❌ Error loading UI logo: {e}")
            # Fallback text if error
            logo_label.setText("📱")
            logo_label.setStyleSheet("font-size: 40px;")
        
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFixedSize(64, 64)
        qt_corp_main_layout.addWidget(logo_label)
        
        # Text info on the right
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        corp_title = QLabel("QTKit - QuickTime Kit")
        corp_title.setStyleSheet("color: #1565c0; font-size: 16px; font-weight: bold;")
        text_layout.addWidget(corp_title)
        
        corp_author = QLabel("by Quang Trần - QT Corporation")
        corp_author.setStyleSheet("color: #1976d2; font-size: 14px; font-weight: bold;")
        text_layout.addWidget(corp_author)
        
        corp_copyright = QLabel("Copyright © 2025 QT Corporation")
        corp_copyright.setStyleSheet("color: #90a4ae; font-size: 11px;")
        text_layout.addWidget(corp_copyright)
        
        corp_contact = QLabel('📞 Contact: <a href="https://t.me/qpepsi769" style="color: #1976d2; text-decoration: underline;">@qpepsi769</a>')
        corp_contact.setStyleSheet("color: #1976d2; font-size: 12px; font-weight: bold;")
        corp_contact.setOpenExternalLinks(True)
        text_layout.addWidget(corp_contact)
        
        qt_corp_main_layout.addLayout(text_layout)
        qt_corp_main_layout.addStretch()  # Push content to left
        
        layout.addWidget(qt_corp_container)
        
        # Add some spacing before buttons
        layout.addStretch()
        
        # Buttons with better styling
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        if hasattr(self, 'first_run') and self.first_run:
            start_btn = QPushButton("🚀 Bắt đầu & chạy ngầm")
            start_btn.clicked.connect(self.start_using)
            start_btn.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #28a745, stop:1 #20a83a);
                color: white;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 14px;
            """)
            start_btn.setMinimumHeight(45)
            button_layout.addWidget(start_btn)
        else:
            hide_btn = QPushButton("Ẩn cửa sổ")
            hide_btn.clicked.connect(self.hide_config)
            hide_btn.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #6c757d, stop:1 #5a6268);
                color: white;
                border-radius: 8px;
                padding: 12px 24px;
            """)
            hide_btn.setMinimumHeight(45)
            button_layout.addWidget(hide_btn)
        
        quit_btn = QPushButton("Thoát ứng dụng")
        quit_btn.clicked.connect(self.quit_app)
        quit_btn.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                stop:0 #dc3545, stop:1 #c82333);
            color: white;
            border-radius: 8px;
            padding: 12px 24px;
        """)
        quit_btn.setMinimumHeight(45)
        button_layout.addWidget(quit_btn)
        
        layout.addLayout(button_layout)
        
        # Update UI state
        self.update_decimal_ui_state()
    
    def show_first_run_welcome(self):
        """Show welcome popup for first run"""
        logger.info("📱 Setting up first run welcome...")
        
        # Make sure dock icon is visible for first run on macOS
        if sys.platform == "darwin":
            try:
                import AppKit
                logger.info("🍎 Setting macOS app policy to Regular...")
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
            except ImportError:
                logger.warning("⚠️ AppKit not available")
        
        # Show the main config window with delay to ensure it appears
        logger.info("🪟 Showing window...")
        self.show()
        self.raise_()  # Bring to front
        self.activateWindow()  # Focus the window
        
        # Force window to be visible and on top
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        
        logger.info("🎉 First run detected - config window should be visible now!")
    
    def start_using(self):
        """Start using the app (for first run)"""
        # Mark first run as completed
        self.mark_first_run_completed()
        
        self.hide()
        
        # Hide dock icon on macOS after first setup
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
            except ImportError:
                pass
        
        logger.info("✅ Configuration saved! App is now running in background.")
    
    def show_config(self):
        """Show config window from tray menu"""
        # Temporarily show dock icon on macOS to display window
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
                self.dock_icon_visible = True
            except ImportError:
                pass
        
        self.show()
        self.raise_()
        self.activateWindow()
    
    def hide_config(self):
        """Hide config window and dock icon"""
        self.hide()
        
        # Only hide dock icon if no other dialogs are open
        if sys.platform == "darwin" and self.dock_icon_visible:
            # Check if any dialogs are still open
            has_open_dialogs = (
                (hasattr(self, 'log_viewer') and self.log_viewer and self.log_viewer.isVisible()) or
                (hasattr(self, 'permissions_window') and self.permissions_window and self.permissions_window.isVisible())
            )
            
            if not has_open_dialogs:
                try:
                    import AppKit
                    AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
                    self.dock_icon_visible = False
                except ImportError:
                    pass
    
    def show_help(self):
        """Show help dialog"""
        # Create custom dialog with larger size
        dialog = QDialog()
        dialog.setWindowTitle("QTKit - Hướng dẫn sử dụng")
        dialog.setGeometry(200, 200, 700, 600)
        dialog.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(5)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Header with logo and title
        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setSpacing(15)
        
        # Logo
        logo_label = QLabel()
        try:
            import os
            possible_paths = [
                "logo.png",
                os.path.join(os.path.dirname(__file__), "logo.png"),
                os.path.join(sys._MEIPASS, "logo.png") if hasattr(sys, '_MEIPASS') else None
            ]
            
            for logo_path in possible_paths:
                if logo_path and os.path.exists(logo_path):
                    logo_pixmap = QPixmap(logo_path)
                    if not logo_pixmap.isNull():
                        scaled_logo = logo_pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        logo_label.setPixmap(scaled_logo)
                        break
        except:
            logo_label.setText("📱")
            logo_label.setStyleSheet("font-size: 60px;")
        
        header_layout.addWidget(logo_label)
        
        # Title section
        title_layout = QVBoxLayout()
        title = QLabel("QTKit - QuickTime Kit")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        title_layout.addWidget(title)
        
        subtitle = QLabel("Công cụ chuyển đổi timestamp thông minh")
        subtitle.setStyleSheet("font-size: 16px; color: #7f8c8d; margin-top: 5px;")
        title_layout.addWidget(subtitle)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        layout.addWidget(header_container)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #bdc3c7;")
        layout.addWidget(separator)
        
        # Help content in scrollable area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f8f9fa;
            }
        """)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(5)
        content_layout.setContentsMargins(5, 5, 5, 5)
        
        # Help sections
        sections = [
            {
                "icon": "🎯",
                "title": "Cách sử dụng cơ bản",
                "content": """• Nhấn Cmd+C trên timestamp (ví dụ: 1640995200)
• QTKit sẽ tự động hiện tooltip với thời gian GMT và VN
• Tooltip hiển thị trong thời gian có thể tùy chỉnh (mặc định 3 giây)"""
            },
            {
                "icon": "⚙️",
                "title": "Cấu hình ứng dụng",
                "content": """• Right-click vào icon tray → "Mở cấu hình"
• Tùy chỉnh hiển thị phần thập phân (0-6 chữ số)
• Bật/tắt chế độ detect timestamp trong text dài
• Cài đặt thời gian hiển thị tooltip (1-10 giây)"""
            },
            {
                "icon": "🔐",
                "title": "Cài đặt quyền hệ thống",
                "content": """• Lần đầu chạy: ứng dụng yêu cầu quyền Accessibility
• macOS 13+: System Settings → Privacy & Security → Accessibility
• macOS 12-: System Preferences → Security & Privacy → Accessibility
• Tick chọn QTKit trong danh sách ứng dụng"""
            },
            {
                "icon": "🔍",
                "title": "Debug và troubleshoot",
                "content": """• Right-click icon tray → "Xem logs" để kiểm tra hoạt động
• Right-click icon tray → "Kiểm tra quyền" để xem trạng thái permissions
• Nếu không hoạt động: kiểm tra lại quyền Accessibility và Input Monitoring"""
            },
            {
                "icon": "📱",
                "title": "Tìm lại ứng dụng",
                "content": """• Tìm "QTKit" trong Spotlight (Cmd+Space)
• Mở từ Applications folder
• Icon xuất hiện trong system tray (góc trên bên phải màn hình)
• App chạy ngầm, không hiện trong Dock"""
            },
            {
                "icon": "💬",
                "title": "Liên hệ & Hỗ trợ",
                "content": """• Telegram: @qpepsi769 (click nút bên dưới)
• Báo lỗi, góp ý cải thiện
• Yêu cầu tính năng mới
• Hỗ trợ kỹ thuật"""
            },
            {
                "icon": "📞",
                "title": "Liên hệ hỗ trợ",
                "content": """• Telegram: https://t.me/qpepsi769
• Báo lỗi, góp ý cải tiến
• Yêu cầu tính năng mới
• Hỗ trợ kỹ thuật 24/7"""
            }
        ]
        
        for section in sections:
            section_container = QWidget()
            section_container.setStyleSheet("""
                QWidget {
                    background-color: white;
                    border-radius: 8px;
                    padding: 8px;
                }
            """)
            
            section_layout = QVBoxLayout(section_container)
            section_layout.setSpacing(3)
            
            # Section header
            header = QLabel(f"{section['icon']} {section['title']}")
            header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
            section_layout.addWidget(header)
            
            # Section content
            content = QLabel(section['content'])
            content.setStyleSheet("font-size: 15px; color: #34495e; line-height: 1.2;")
            content.setWordWrap(True)
            section_layout.addWidget(content)
            
            content_layout.addWidget(section_container)
        
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Contact button
        contact_btn = QPushButton("📱 Liên hệ Telegram")
        contact_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://t.me/qpepsi769")))
        contact_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #0088cc, stop:1 #006699);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 20px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #006699, stop:1 #004466);
            }
        """)
        button_layout.addWidget(contact_btn)
        
        close_btn = QPushButton("Đóng")
        def close_help_dialog():
            dialog.close()
            # Auto-hide dock icon if config window is also hidden
            if sys.platform == "darwin" and not self.isVisible():
                has_other_dialogs = (
                    (hasattr(self, 'log_viewer') and self.log_viewer and self.log_viewer.isVisible()) or
                    (hasattr(self, 'permissions_window') and self.permissions_window and self.permissions_window.isVisible())
                )
                if not has_other_dialogs:
                    try:
                        import AppKit
                        AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
                        self.dock_icon_visible = False
                    except ImportError:
                        pass
        
        close_btn.clicked.connect(close_help_dialog)
        close_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #3498db, stop:1 #2980b9);
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 30px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                    stop:0 #2980b9, stop:1 #21618c);
            }
        """)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        # Show with existing dock icon policy (don't change it)
        if sys.platform == "darwin" and not self.dock_icon_visible:
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
                self.dock_icon_visible = True
            except ImportError:
                pass
        
        dialog.exec_()
        
        # Only hide dock icon if config window is not visible
        if sys.platform == "darwin" and not self.isVisible():
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
                self.dock_icon_visible = False
            except ImportError:
                pass
        
    def setup_tray(self):
        """Setup system tray"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
            
        self.tray_icon = QSystemTrayIcon(self)
        
        # Use logo.png as icon with proper path handling
        try:
            import os
            # Try multiple possible paths
            possible_paths = [
                "logo.png",
                os.path.join(os.path.dirname(__file__), "logo.png"),
                os.path.join(os.path.dirname(sys.executable), "logo.png"),
                os.path.join(sys._MEIPASS, "logo.png") if hasattr(sys, '_MEIPASS') else None
            ]
            
            icon_loaded = False
            for icon_path in possible_paths:
                if icon_path and os.path.exists(icon_path):
                    logger.info(f"🎨 Loading tray icon from: {icon_path}")
                    pixmap = QPixmap(icon_path)
                    if not pixmap.isNull():
                        # Scale to appropriate tray icon size
                        scaled_pixmap = pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.tray_icon.setIcon(QIcon(scaled_pixmap))
                        icon_loaded = True
                        break
            
            if not icon_loaded:
                logger.warning("⚠️ Could not load logo.png, using fallback icon")
                # Fallback to simple icon
                pixmap = QPixmap(32, 32)
                pixmap.fill(Qt.blue)
                self.tray_icon.setIcon(QIcon(pixmap))
                
        except Exception as e:
            logger.error(f"❌ Error loading tray icon: {e}")
            # Fallback to simple icon
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.blue)
            self.tray_icon.setIcon(QIcon(pixmap))
        
        # Tray menu
        tray_menu = QMenu()
        
        # Main actions
        config_action = QAction("⚙️ Mở cấu hình", self)
        config_action.triggered.connect(self.show_config)
        tray_menu.addAction(config_action)
        
        # Add separator
        tray_menu.addSeparator()
        
        # Debug and tools
        logs_action = QAction("📋 Xem logs", self)
        logs_action.triggered.connect(self.show_logs)
        tray_menu.addAction(logs_action)
        
        permissions_action = QAction("🔐 Kiểm tra quyền", self)
        permissions_action.triggered.connect(self.show_permissions)
        tray_menu.addAction(permissions_action)
        
        # Add separator
        tray_menu.addSeparator()
        
        # Status and help
        status_action = QAction("📊 Trạng thái: Đang chạy", self)
        status_action.setEnabled(False)  # Just for display
        tray_menu.addAction(status_action)
        
        help_action = QAction("❓ Hướng dẫn sử dụng", self)
        help_action.triggered.connect(self.show_help)
        tray_menu.addAction(help_action)
        
        # Add separator
        tray_menu.addSeparator()
        
        # Quit
        quit_action = QAction("🚪 Thoát QTKit", self)
        quit_action.triggered.connect(self.quit_app)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        self.tray_icon.setToolTip("QTKit - QuickTime Kit\n🎯 Nhấn Cmd+C trên timestamp để xem thời gian\n⚙️ Right-click để cấu hình")
    
    def force_request_permissions(self):
        """Force request both Accessibility and Input Monitoring permissions on every startup"""
        logger.info("🔐 Force requesting permissions on startup...")
        
        if sys.platform != "darwin":
            return True
        
        permissions_needed = []
        
        # Test Accessibility permission
        try:
            test_listener = keyboard.Listener(on_press=lambda key: None)
            test_listener.start()
            test_listener.stop()
            logger.info("✅ Accessibility permission already granted")
        except Exception as e:
            error_msg = str(e).lower()
            if any(word in error_msg for word in ["not trusted", "accessibility", "permission", "denied"]):
                logger.warning("⚠️ Accessibility permission needed")
                permissions_needed.append("Accessibility")
        
        # Test Input Monitoring permission via AppleScript
        try:
            import subprocess
            subprocess.run([
                "osascript", "-e", 
                'tell application "System Events" to get application processes'
            ], capture_output=True, text=True, check=True, timeout=3)
            logger.info("✅ Input Monitoring permission already granted")
        except:
            logger.warning("⚠️ Input Monitoring permission needed")
            permissions_needed.append("Input Monitoring")
        
        # If any permissions needed, show comprehensive alert
        if permissions_needed:
            self.show_startup_permission_alert(permissions_needed)
            return False
        else:
            logger.info("✅ All permissions granted")
            return True
    
    def show_startup_permission_alert(self, permissions_needed):
        """Show comprehensive permission alert on startup"""
        logger.warning(f"🔐 Permissions needed: {', '.join(permissions_needed)}")
        
        # Show dock icon temporarily for the alert
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
            except ImportError:
                pass
        
        msg = QMessageBox()
        msg.setWindowTitle("QTKit - Cần cấp quyền bắt buộc")
        msg.setIcon(QMessageBox.Warning)
        
        if len(permissions_needed) > 1:
            msg.setText("🔐 QTKit cần CẢ HAI quyền để hoạt động:")
        else:
            msg.setText(f"🔐 QTKit cần quyền {permissions_needed[0]} để hoạt động:")
        
        permissions_text = ""
        if "Accessibility" in permissions_needed:
            permissions_text += "• ACCESSIBILITY: Để theo dõi phím Cmd+C\n"
        if "Input Monitoring" in permissions_needed:
            permissions_text += "• INPUT MONITORING: Để phát hiện keyboard events\n"
        
        detailed_text = f"""QTKit yêu cầu các quyền sau để hoạt động:

{permissions_text}
CÁCH CẤP QUYỀN (macOS 10.15+):

1️⃣ Mở System Preferences/System Settings
2️⃣ Vào Security & Privacy → Privacy 
   (hoặc Privacy & Security trên macOS 13+)
3️⃣ Tìm và click vào:
   - "Accessibility" (nếu cần)
   - "Input Monitoring" (nếu cần)
4️⃣ Click khóa 🔒 để unlock (nhập password)
5️⃣ Tick chọn ☑️ QTKit trong danh sách
6️⃣ Khởi động lại QTKit

LƯU Ý QUAN TRỌNG:
• Cần CẢ HAI quyền mới hoạt động đầy đủ
• Nếu không cấp quyền, app sẽ không detect Cmd+C
• Có thể cần khởi động lại app sau khi cấp quyền

TRÊN MACOS CŨ (10.14-):
System Preferences → Security & Privacy → Privacy → Accessibility"""
        
        msg.setInformativeText("System Preferences → Security & Privacy → Privacy\n\nCấp quyền Accessibility VÀ Input Monitoring cho QTKit")
        msg.setDetailedText(detailed_text)
        
        # Add buttons
        msg.setStandardButtons(QMessageBox.Ok)
        open_prefs_btn = msg.addButton("Mở System Preferences", QMessageBox.ActionRole)
        retry_btn = msg.addButton("Thử lại", QMessageBox.ActionRole)
        continue_btn = msg.addButton("Tiếp tục (không đầy đủ chức năng)", QMessageBox.ActionRole)
        
        result = msg.exec_()
        
        # Hide dock icon again after alert
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
            except ImportError:
                pass
        
        if msg.clickedButton() == open_prefs_btn:
            self.open_system_preferences()
        elif msg.clickedButton() == retry_btn:
            # Retry permission check
            if self.force_request_permissions():
                logger.info("✅ All permissions granted! Continuing...")
            else:
                logger.warning("⚠️ Still missing permissions")
        elif msg.clickedButton() == continue_btn:
            logger.warning("⚠️ User chose to continue without full permissions")
    
    def open_system_preferences(self):
        """Open macOS System Preferences to relevant permission sections"""
        try:
            import subprocess
            # Try multiple ways to open preferences for different macOS versions
            commands = [
                # macOS 13+ (Ventura+)
                ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy"],
                # macOS 12 and earlier
                ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
                # Fallback
                ["open", "/System/Library/PreferencePanes/Security.prefPane"],
                ["open", "-b", "com.apple.preference.security"]
            ]
            
            for cmd in commands:
                try:
                    subprocess.call(cmd)
                    logger.info(f"🔗 Opened System Preferences: {' '.join(cmd)}")
                    break
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Failed to open System Preferences: {e}")
            
    def hide_dock_icon_if_needed(self):
        """Hide dock icon on macOS when running as tray app"""
        try:
            if sys.platform == 'darwin':
                app = QApplication.instance()
                if app:
                    app.setAttribute(Qt.AA_DontShowIconsInMenus, True)
                    # Hide from dock using macOS specific method
                    try:
                        import objc
                        from Foundation import NSBundle
                        bundle = NSBundle.mainBundle()
                        if bundle:
                            info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                            if info:
                                info['LSUIElement'] = True
                    except ImportError:
                        pass  # objc not available, skip dock hiding
        except Exception as e:
            logger.error(f"Failed to hide dock icon: {e}")
        
    def setup_cmd_c_monitoring(self):
        """Setup Cmd+C key monitoring"""
        try:
            logger.info("🎯 Setting up Cmd+C monitoring...")
            self.cmd_monitor = CmdCMonitor()
            self.cmd_monitor.cmd_c_pressed.connect(self.on_cmd_c_detected)
            self.cmd_monitor.permission_needed.connect(self.show_permission_alert)
            self.cmd_monitor.start()
            
            # Setup tooltip font with system default font
            font = QApplication.font()
            font.setPointSize(13)
            font.setBold(True)
            QToolTip.setFont(font)
            
            logger.info("✅ Cmd+C monitoring started successfully!")
            logger.info("📝 Note: You may need to grant Accessibility permissions in System Preferences > Security & Privacy > Privacy > Accessibility")
            
        except Exception as e:
            logger.error(f"❌ Error setting up Cmd+C monitoring: {e}")
            logger.warning("⚠️ App will still work but won't detect Cmd+C automatically")
    
    def show_permission_alert(self):
        """Show alert when accessibility permissions are needed"""
        logger.warning("🔐 Accessibility permissions required")
        
        # Show dock icon temporarily for the alert
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
            except ImportError:
                pass
        
        msg = QMessageBox()
        msg.setWindowTitle("QTKit - Cần cấp quyền")
        msg.setIcon(QMessageBox.Warning)
        msg.setText("🔐 QTKit cần quyền Accessibility để phát hiện phím Cmd+C")
        
        detailed_text = """QTKit cần quyền Accessibility để:
• Theo dõi tổ hợp phím Cmd+C
• Tự động phát hiện timestamp trong clipboard
• Hiển thị tooltip với thời gian chuyển đổi

Không có quyền này, QTKit sẽ không thể hoạt động tự động.

CÁCH CÁP QUYỀN:
1. Mở System Preferences (System Settings trên macOS 13+)
2. Vào Security & Privacy → Privacy → Accessibility
3. Click khóa để mở khóa (nhập password)
4. Tìm và tick chọn QTKit
5. Khởi động lại QTKit

LƯU Ý: Trên macOS mới, có thể cần vào:
System Settings → Privacy & Security → Accessibility"""
        
        msg.setInformativeText("System Preferences → Security & Privacy → Privacy → Accessibility\n\nThêm QTKit vào danh sách ứng dụng được phép.")
        msg.setDetailedText(detailed_text)
        
        # Add buttons
        msg.setStandardButtons(QMessageBox.Ok)
        open_prefs_btn = msg.addButton("Mở System Preferences", QMessageBox.ActionRole)
        retry_btn = msg.addButton("Thử lại", QMessageBox.ActionRole)
        
        result = msg.exec_()
        
        # Hide dock icon again after alert
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
            except ImportError:
                pass
        
        if msg.clickedButton() == open_prefs_btn:
            try:
                import subprocess
                # Try multiple ways to open preferences
                commands = [
                    ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"],
                    ["open", "/System/Library/PreferencePanes/Security.prefPane"],
                    ["open", "-b", "com.apple.preference.security"]
                ]
                
                for cmd in commands:
                    try:
                        subprocess.call(cmd)
                        logger.info(f"🔗 Opened System Preferences: {' '.join(cmd)}")
                        break
                    except:
                        continue
                        
            except Exception as e:
                logger.error(f"❌ Failed to open System Preferences: {e}")
                
        elif msg.clickedButton() == retry_btn:
            # Retry permission check
            if self.check_accessibility_permission():
                logger.info("✅ Permissions granted! Restarting keyboard monitoring...")
                if hasattr(self, 'cmd_monitor'):
                    self.cmd_monitor.stop()
                self.setup_cmd_c_monitoring()
            else:
                logger.warning("⚠️ Permissions still not granted")
    
    def on_show_decimal_changed(self, checked):
        """Handle show decimal checkbox change"""
        self.show_decimal = checked
        self.update_decimal_ui_state()
        self.save_settings()
        
    def show_logs(self):
        """Show logs window"""
        try:
            # Lazy loading for better performance
            if not hasattr(self, 'log_viewer') or self.log_viewer is None:
                self.log_viewer = LogViewerWindow()
                # Set window flags only once during creation
                self.log_viewer.setWindowFlags(
                    Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint
                )
            
            # Ensure dock icon is visible if needed
            if sys.platform == 'darwin' and not self.dock_icon_visible:
                try:
                    import AppKit
                    AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
                    self.dock_icon_visible = True
                except ImportError:
                    pass
            
            self.log_viewer.show()
            self.log_viewer.activateWindow()
            self.log_viewer.raise_()
                    
        except Exception as e:
            logger.error(f"Failed to show logs window: {e}")
            
    def show_permissions(self):
        """Show permissions window"""
        try:
            # Lazy loading for better performance
            if not hasattr(self, 'permissions_window') or self.permissions_window is None:
                self.permissions_window = PermissionsWindow()
                # Set window flags only once during creation
                self.permissions_window.setWindowFlags(
                    Qt.Window | Qt.WindowStaysOnTopHint | Qt.WindowCloseButtonHint
                )
            
            # Ensure dock icon is visible if needed
            if sys.platform == 'darwin' and not self.dock_icon_visible:
                try:
                    import AppKit
                    AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
                    self.dock_icon_visible = True
                except ImportError:
                    pass
            
            self.permissions_window.show()
            self.permissions_window.activateWindow()
            self.permissions_window.raise_()
                    
        except Exception as e:
            logger.error(f"Failed to show permissions window: {e}")
    
    def check_version_expiry(self):
        """Check if current version has expired"""
        current_timestamp = int(time.time())
        if current_timestamp < VERSION_EXPIRY_TIMESTAMP:
            return False  # Not expired
        return True  # Expired
    
    def show_version_expired_dialog(self):
        """Show version expired dialog"""
        logger.warning("🚫 Version expired!")
        
        # Show dock icon temporarily for the alert
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
            except ImportError:
                pass
        
        msg = QMessageBox()
        msg.setWindowTitle("QTKit - Phiên bản hết hạn")
        msg.setIcon(QMessageBox.Critical)
        msg.setText("🚫 Phiên bản QTKit đã hết hạn")
        
        detailed_text = f"""Phiên bản hiện tại của QTKit đã hết hạn sử dụng.

THÔNG TIN:
• Timestamp hiện tại: {int(time.time())}
• Hạn sử dụng: {VERSION_EXPIRY_TIMESTAMP}
• Ngày hết hạn: {datetime.fromtimestamp(VERSION_EXPIRY_TIMESTAMP).strftime('%d/%m/%Y %H:%M:%S')}

Để tiếp tục sử dụng QTKit, vui lòng:
� Liên hệ Telegram: https://t.me/qpepsi769
🔄 Để update bản nâng cấp mới nhất

Ứng dụng sẽ thoát sau khi đóng thông báo này."""

        msg.setDetailedText(detailed_text)
        msg.setStandardButtons(QMessageBox.Ok)
        
        result = msg.exec_()
        
        # Hide dock icon again after alert
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
            except ImportError:
                pass
        
        # Exit application after showing dialog
        QApplication.quit()
    
    def check_expiry_periodically(self):
        """Periodic check for version expiry while app is running"""
        try:
            if self.check_version_expiry():
                logger.warning("🚫 Version expired during runtime!")
                # Stop the timer to prevent multiple dialogs
                if hasattr(self, 'expiry_timer'):
                    self.expiry_timer.stop()
                # Show expiry dialog and exit
                self.show_version_expired_dialog()
        except Exception as e:
            logger.error(f"Error in periodic expiry check: {e}")
    
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
    
    def on_tooltip_duration_changed(self, value):
        """Handle tooltip duration change"""
        self.tooltip_duration = value
        self.save_settings()
        logger.info(f"🕐 Tooltip duration changed to {value} seconds")
    
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
                    logger.info(f"✅ Timestamp detected: {timestamp_str}")
                    self.show_tooltip(timestamp_str)
                # Don't log non-timestamp content to reduce spam
            else:
                logger.warning("📋 Clipboard is empty")
                
        except Exception as e:
            logger.error(f"❌ Error checking clipboard: {e}")
        

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
            tooltip_pos = QPoint(cursor_pos.x() + 40, cursor_pos.y() - 90)
            
            QToolTip.showText(tooltip_pos, tooltip_text)
            
            # Set consistent auto-hide timer (3 seconds)
            if hasattr(self, 'tooltip_timer'):
                self.tooltip_timer.stop()
            
            self.tooltip_timer = QTimer()
            self.tooltip_timer.setSingleShot(True)
            self.tooltip_timer.timeout.connect(QToolTip.hideText)
            self.tooltip_timer.start(self.tooltip_duration * 1000)  # Convert seconds to milliseconds
            
            logger.info(f"✅ Tooltip shown for {self.tooltip_duration}s: {gmt_str} / {vn_str}")
                
        except Exception as e:
            logger.error(f"❌ Error showing tooltip: {e}")
            
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
            
            # Hide dock icon again on macOS when closing config window
            if sys.platform == "darwin" and not self.first_run:
                try:
                    import AppKit
                    AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
                except ImportError:
                    pass
            
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
    app.setApplicationName("QTKit")
    app.setQuitOnLastWindowClosed(False)
    
    # Check for reset flag
    settings = QSettings("TimestampViewer", "Settings")
    settings.setValue("first_run", True)
    logger.info("🔄 Reset first_run flag!")
    
    # Create viewer first
    viewer = SimpleTimestampViewer()
    
    # Hide dock icon on macOS only after first run
    if sys.platform == "darwin" and not viewer.first_run:
        try:
            import AppKit
            AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
        except ImportError:
            pass
    
    logger.info("🚀 QTKit (QuickTime Kit) started!")
    logger.info("📋 Copy any timestamp to see the magic!")
    logger.info(f"📁 Check logs at: ~/Library/Logs/QTKit/qtkit.log")
    
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
