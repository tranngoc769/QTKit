#!/usr/bin/env python3
import sys
import re
import time
import logging
import os
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                              QWidget, QLabel, QSystemTrayIcon, QMenu, QToolTip, 
                              QCheckBox, QSpinBox, QGroupBox, QPushButton, QMessageBox)
from PySide6.QtCore import QTimer, Qt, Signal, QThread, QSettings, QPoint
from PySide6.QtGui import QIcon, QPixmap, QFont, QAction, QCursor
from pynput import keyboard

# Setup logging
def setup_logging():
    """Setup logging to file and console"""
    # Create logs directory if not exists
    log_dir = os.path.expanduser("~/Library/Logs/QTKit")
    os.makedirs(log_dir, exist_ok=True)
    
    # Log file path
    log_file = os.path.join(log_dir, "qtkit.log")
    
    # Setup logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("=" * 50)
    logger.info("🚀 QTKit starting up...")
    logger.info(f"📁 Log file: {log_file}")
    logger.info("=" * 50)
    
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
                # Try to create a keyboard listener to test permissions
                try:
                    test_listener = keyboard.Listener(on_press=lambda key: None)
                    test_listener.start()
                    test_listener.stop()
                    logger.info("✅ Accessibility permissions are granted")
                    return True
                except Exception as e:
                    if "not trusted" in str(e).lower() or "accessibility" in str(e).lower():
                        logger.warning("⚠️ Accessibility permissions not granted")
                        return False
                    else:
                        # Other error, assume permissions are OK
                        return True
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

class SimpleTimestampViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.last_clipboard_text = ""
        self.settings = QSettings("QTKit", "Settings")
        self.load_settings()
        self.setup_ui()
        self.setup_tray()
        self.setup_cmd_c_monitoring()
        
        # Show config window on first run
        logger.info(f"🔍 First run status: {self.first_run}")
        if self.first_run:
            logger.info("🎯 Showing first run welcome...")
            self.show_first_run_welcome()
        else:
            logger.info("👻 Not first run - running in background")
    
    def load_settings(self):
        """Load settings from QSettings"""
        self.show_decimal = self.settings.value("show_decimal", True, type=bool)
        self.decimal_places = self.settings.value("decimal_places", 3, type=int)
        self.show_full_decimal = self.settings.value("show_full_decimal", False, type=bool)
        self.detect_mode = self.settings.value("detect_mode", False, type=bool)  # Default False
        self.first_run = self.settings.value("first_run", True, type=bool)
    
    def save_settings(self):
        """Save settings to QSettings"""
        self.settings.setValue("show_decimal", self.show_decimal)
        self.settings.setValue("decimal_places", self.decimal_places)
        self.settings.setValue("show_full_decimal", self.show_full_decimal)
        self.settings.setValue("detect_mode", self.detect_mode)
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
            hide_btn.clicked.connect(self.hide)
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
        
        # Hide dock icon on macOS after first setup
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
            except ImportError:
                pass
        
        self.hide()
        logger.info("✅ Configuration saved! App is now running in background.")
    
    def show_config(self):
        """Show config window from tray menu"""
        # Temporarily show dock icon on macOS to display window
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
            except ImportError:
                pass
        
        self.show()
        self.raise_()
        self.activateWindow()
    
    def show_help(self):
        """Show help dialog"""
        msg = QMessageBox()
        msg.setWindowTitle("QTKit - Hướng dẫn sử dụng")
        msg.setIcon(QMessageBox.Information)
        
        help_text = """🎯 Cách sử dụng QTKit:

1️⃣ Sao chép timestamp:
   • Nhấn Cmd+C trên timestamp (vd: 1640995200)
   • QTKit sẽ tự động hiện tooltip với thời gian

2️⃣ Cấu hình:
   • Right-click vào icon tray → "Mở cấu hình"
   • Tùy chỉnh hiển thị thập phân
   • Bật/tắt chế độ detect trong text dài

3️⃣ Cài đặt lần đầu:
   • Ứng dụng sẽ yêu cầu quyền Accessibility
   • System Preferences → Security & Privacy → Accessibility
   • Thêm QTKit vào danh sách

4️⃣ Tìm lại ứng dụng:
   • Tìm "QTKit" trong Spotlight (Cmd+Space)
   • Hoặc mở từ Applications folder
   • Icon sẽ xuất hiện trong system tray"""
        
        msg.setText("QTKit - QuickTime Kit")
        msg.setInformativeText("Công cụ chuyển đổi timestamp thông minh")
        msg.setDetailedText(help_text)
        
        # Show temporarily with dock icon
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyRegular)
            except ImportError:
                pass
        
        msg.exec_()
        
        # Hide dock icon again
        if sys.platform == "darwin":
            try:
                import AppKit
                AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
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
        
    def setup_cmd_c_monitoring(self):
        """Setup Cmd+C key monitoring"""
        try:
            logger.info("🎯 Setting up Cmd+C monitoring...")
            self.cmd_monitor = CmdCMonitor()
            self.cmd_monitor.cmd_c_pressed.connect(self.on_cmd_c_detected)
            self.cmd_monitor.permission_needed.connect(self.show_permission_alert)
            self.cmd_monitor.start()
            
            # Setup tooltip font
            QToolTip.setFont(QFont("Monaco", 13, QFont.Bold))
            
            logger.info("✅ Cmd+C monitoring started successfully!")
            logger.info("📝 Note: You may need to grant Accessibility permissions in System Preferences > Security & Privacy > Privacy > Accessibility")
            
        except Exception as e:
            logger.error(f"❌ Error setting up Cmd+C monitoring: {e}")
            logger.warning("⚠️ App will still work but won't detect Cmd+C automatically")
    
    def show_permission_alert(self):
        """Show alert when accessibility permissions are needed"""
        logger.warning("🔐 Accessibility permissions required")
        
        msg = QMessageBox()
        msg.setWindowTitle("QTKit - Permissions Required")
        msg.setIcon(QMessageBox.Warning)
        msg.setText("QTKit needs Accessibility permissions to detect Cmd+C key combinations.")
        msg.setInformativeText("Please go to:\nSystem Preferences > Security & Privacy > Privacy > Accessibility\n\nThen add QTKit to the list of allowed apps.")
        msg.setDetailedText("Without these permissions, QTKit cannot automatically detect when you copy timestamps to the clipboard. You can still use the app by pasting timestamps manually.")
        
        # Add buttons
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        open_prefs_btn = msg.addButton("Open System Preferences", QMessageBox.ActionRole)
        
        result = msg.exec_()
        
        if msg.clickedButton() == open_prefs_btn:
            try:
                import subprocess
                subprocess.call(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
                logger.info("🔗 Opened System Preferences for user")
            except Exception as e:
                logger.error(f"❌ Failed to open System Preferences: {e}")
    
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
        logger.info("📋 Cmd+C detected, checking clipboard...")
        # Wait a moment for clipboard to update
        QTimer.singleShot(200, self.check_clipboard_for_timestamp)
        
    def check_clipboard_for_timestamp(self):
        """Check clipboard specifically for timestamp after Cmd+C"""
        try:
            clipboard = QApplication.clipboard()
            current_text = clipboard.text().strip()
            
            if current_text:
                logger.info(f"📝 Clipboard content: {current_text[:50]}...")
                timestamp_str, is_valid = self.get_timestamp(current_text)
                if is_valid:
                    logger.info(f"✅ Valid timestamp detected: {timestamp_str}")
                    self.show_tooltip(timestamp_str)
                    logger.info(f"🎯 Tooltip should be displayed now")
                else:
                    logger.info(f"ℹ️ Non-timestamp content: {current_text[:30]}...")
            else:
                logger.warning("📋 Clipboard is empty")
                
        except Exception as e:
            logger.error(f"❌ Error checking clipboard: {e}", exc_info=True)
        

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
            logger.info(f"🔄 Converting timestamp: {timestamp_str}")
            # Convert timestamp
            gmt_str, vn_str = self.convert_timestamp(timestamp_str)
            logger.info(f"🕐 GMT: {gmt_str}")
            logger.info(f"🕐 VN:  {vn_str}")
            
            # Create tooltip text
            tooltip_text = f"🌍 GMT: {gmt_str}\n🇻🇳 VN:  {vn_str}"
            
            # Hide any existing tooltip first
            QToolTip.hideText()
            
            # Show at cursor position with offset (above and to the right)
            cursor_pos = QCursor.pos()
            tooltip_pos = QPoint(cursor_pos.x() + 40, cursor_pos.y() - 90)
            logger.info(f"💬 Showing tooltip at position: {tooltip_pos.x()}, {tooltip_pos.y()}")
            logger.info(f"💬 Tooltip text: {tooltip_text}")
            
            QToolTip.showText(tooltip_pos, tooltip_text)
            
            # Set consistent auto-hide timer (3 seconds)
            if hasattr(self, 'tooltip_timer'):
                self.tooltip_timer.stop()
            
            self.tooltip_timer = QTimer()
            self.tooltip_timer.setSingleShot(True)
            self.tooltip_timer.timeout.connect(QToolTip.hideText)
            self.tooltip_timer.start(3000)  # 3 seconds consistent
            
            logger.info("✅ Tooltip displayed successfully")
                
        except Exception as e:
            logger.error(f"❌ Error showing tooltip: {e}", exc_info=True)
            
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
            # Hide dock icon again on macOS when closing config window
            if sys.platform == "darwin" and not self.first_run:
                try:
                    import AppKit
                    AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
                except ImportError:
                    pass
            
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
