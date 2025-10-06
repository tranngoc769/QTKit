#!/usr/bin/env python3
import sys
import re
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                              QWidget, QLabel, QTextEdit, QPushButton, QSystemTrayIcon, 
                              QMenu, QMessageBox, QFrame, QScrollArea)
from PySide6.QtCore import QTimer, Qt, Signal, QThread, QPoint
from PySide6.QtGui import QIcon, QPixmap, QFont, QAction, QClipboard, QCursor
from PySide6.QtWidgets import QToolTip
import time
import subprocess



class ClipboardMonitor(QThread):
    """Monitor clipboard changes in a separate thread"""
    timestamp_detected = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.clipboard = QApplication.clipboard()
        self.last_text = ""
        self.running = True
        self.auto_copy_enabled = True
        self.last_processed_time = 0
        self.clipboard_changed = False  # Flag to track real clipboard changes
        
    def run(self):
        while self.running:
            current_text = self.clipboard.text().strip()
            
            # STRICT: Only process if text actually CHANGED from last time
            if (current_text and 
                current_text != self.last_text and 
                self.is_timestamp(current_text)):
                
                self.timestamp_detected.emit(current_text)
                self.last_text = current_text
                    
            self.msleep(500)  # Check every 500ms
    
    def stop(self):
        self.running = False
        self.quit()
        self.wait()
    
    def is_timestamp(self, text):
        """Check if text looks like a timestamp"""
        # Unix timestamp (10 or 13 digits)
        if re.match(r'^\d{10}$', text) or re.match(r'^\d{13}$', text):
            return True
        
        # ISO format timestamps
        iso_patterns = [
            r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}',  # ISO 8601
            r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',   # SQL format
            r'^\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}',   # US format
            r'^\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}',   # EU format
        ]
        
        for pattern in iso_patterns:
            if re.match(pattern, text):
                return True
        
        return False

class TimestampConverter:
    """Handle timestamp conversion logic"""
    
    @staticmethod
    def convert_timestamp(timestamp_str):
        """Convert various timestamp formats to human readable format"""
        results = []
        
        try:
            # Try Unix timestamp (seconds)
            if re.match(r'^\d{10}$', timestamp_str):
                unix_time = int(timestamp_str)
                dt = datetime.fromtimestamp(unix_time)
                results.append({
                    'format': 'Unix Timestamp (seconds)',
                    'input': timestamp_str,
                    'output': dt.strftime('%Y-%m-%d %H:%M:%S'),
                    'iso': dt.isoformat(),
                    'utc': datetime.utcfromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S UTC')
                })
            
            # Try Unix timestamp (milliseconds)
            elif re.match(r'^\d{13}$', timestamp_str):
                unix_time = int(timestamp_str) / 1000
                dt = datetime.fromtimestamp(unix_time)
                results.append({
                    'format': 'Unix Timestamp (milliseconds)',
                    'input': timestamp_str,
                    'output': dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                    'iso': dt.isoformat(),
                    'utc': datetime.utcfromtimestamp(unix_time).strftime('%Y-%m-%d %H:%M:%S.%f UTC')[:-3]
                })
            
            # Try ISO format
            elif 'T' in timestamp_str:
                # Remove timezone info for parsing if present
                clean_timestamp = re.sub(r'[+-]\d{2}:?\d{2}$|Z$', '', timestamp_str)
                try:
                    dt = datetime.fromisoformat(clean_timestamp)
                    results.append({
                        'format': 'ISO 8601 Format',
                        'input': timestamp_str,
                        'output': dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'iso': dt.isoformat(),
                        'unix': str(int(dt.timestamp())),
                        'unix_ms': str(int(dt.timestamp() * 1000))
                    })
                except ValueError:
                    pass
            
            # Try other common formats
            common_formats = [
                '%Y-%m-%d %H:%M:%S',
                '%m/%d/%Y %H:%M:%S',
                '%d-%m-%Y %H:%M:%S',
                '%Y-%m-%d',
                '%m/%d/%Y',
                '%d-%m-%Y'
            ]
            
            for fmt in common_formats:
                try:
                    dt = datetime.strptime(timestamp_str, fmt)
                    results.append({
                        'format': f'Custom Format ({fmt})',
                        'input': timestamp_str,
                        'output': dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'iso': dt.isoformat(),
                        'unix': str(int(dt.timestamp())),
                        'unix_ms': str(int(dt.timestamp() * 1000))
                    })
                    break
                except ValueError:
                    continue
                    
        except Exception as e:
            results.append({
                'format': 'Error',
                'input': timestamp_str,
                'output': f'Could not parse: {str(e)}',
                'error': True
            })
        
        return results

class TimestampViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.clipboard_monitor = None
        self.conversion_history = []
        self.tooltip_timer = None  # Timer để control tooltip
        self.is_tooltip_showing = False  # Track tooltip state
        self.setup_ui()
        self.setup_tray()
        self.setup_shortcuts()
        self.setup_tooltip_style()
        self.start_monitoring()
        
    def setup_ui(self):
        """Setup the main UI"""
        self.setWindowTitle("Timestamp Viewer")
        self.setGeometry(100, 100, 600, 500)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        
        # Title
        title = QLabel("🕐 Timestamp Viewer")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50; margin: 10px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Status label
        self.status_label = QLabel("📋 Đang theo dõi clipboard...")
        self.status_label.setStyleSheet("color: #27ae60; margin: 5px; font-size: 12px;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Instructions label
        instructions = QLabel("💡 Copy timestamp → Hiển thị tại chuột!\n⚡ Chỉ hiện khi copy text MỚI!")
        instructions.setStyleSheet("color: #34495e; margin: 5px; font-size: 11px; background-color: #f8f9fa; padding: 8px; border-radius: 4px;")
        instructions.setAlignment(Qt.AlignCenter)
        layout.addWidget(instructions)
        
        # Scroll area for results
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: 1px solid #bdc3c7; border-radius: 5px;")
        
        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setAlignment(Qt.AlignTop)
        
        scroll.setWidget(self.results_widget)
        layout.addWidget(scroll)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        clear_btn = QPushButton("🗑️ Clear History")
        clear_btn.clicked.connect(self.clear_history)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        
        hide_btn = QPushButton("👁️ Hide to Tray")
        hide_btn.clicked.connect(self.hide)
        hide_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        button_layout.addWidget(clear_btn)
        button_layout.addWidget(hide_btn)
        layout.addLayout(button_layout)
        
    def setup_tray(self):
        """Setup system tray icon"""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(self, "System Tray", "System tray is not available on this system.")
            return
        
        # Create tray icon
        self.tray_icon = QSystemTrayIcon(self)
        
        # Create a simple icon (you might want to use a proper icon file)
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.blue)
        icon = QIcon(pixmap)
        self.tray_icon.setIcon(icon)
        
        # Create tray menu
        tray_menu = QMenu()
        
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)
        
        tray_menu.addSeparator()
        
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        # Show tray icon
        self.tray_icon.show()
        
        # Set tooltip
        self.tray_icon.setToolTip("Timestamp Viewer - Monitoring clipboard")
    
    def setup_shortcuts(self):
        """Setup simple detection method"""
        # Đơn giản hóa - chỉ dùng copy detection và cho phép copy lại
        pass

        
    def setup_tooltip_style(self):
        """Setup compact and beautiful tooltip styling"""
        # Set custom tooltip font - COMPACT và DỄ NHÌN
        tooltip_font = QFont("SF Pro Display", 13)  # macOS system font
        tooltip_font.setBold(True)
        QToolTip.setFont(tooltip_font)
        
        # Compact and modern tooltip stylesheet
        tooltip_style = """
        QToolTip {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #2d3748, stop:1 #1a202c);
            color: #f7fafc;
            border: 2px solid #4a5568;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 13px;
            font-weight: bold;
            line-height: 1.2;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
        }
        """
        self.setStyleSheet(tooltip_style)
        
    def tray_icon_activated(self, reason):
        """Handle tray icon activation"""
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()
    
    def start_monitoring(self):
        """Start clipboard monitoring"""
        self.clipboard_monitor = ClipboardMonitor()
        
        # Debug connection
        self.clipboard_monitor.timestamp_detected.connect(self.handle_timestamp)
        self.clipboard_monitor.start()
        
    def handle_timestamp(self, timestamp_str):
        """Handle detected timestamp"""
        results = TimestampConverter.convert_timestamp(timestamp_str)
        
        for result in results:
            self.add_conversion_result(result)
            
        # Show tooltip at mouse cursor position
        self.show_tooltip_at_cursor(timestamp_str, results)
            
        # Show notification
        if self.tray_icon:
            self.tray_icon.showMessage(
                "Timestamp Detected!",
                f"Converted: {timestamp_str}",
                QSystemTrayIcon.Information,
                2000
            )
    
    def show_tooltip_at_cursor(self, timestamp_str, results):
        """Show single tooltip with proper control"""
        if not results:
            return
            
        # If tooltip is already showing, hide it first
        if self.is_tooltip_showing:
            QToolTip.hideText()
            if self.tooltip_timer:
                self.tooltip_timer.stop()
        
        # Get mouse position
        cursor_pos = QCursor.pos()
        
        # Create tooltip content
        result = results[0]  # Take first result
        if not result.get('error'):
            try:
                # Parse the timestamp to get both GMT and VN time
                if re.match(r'^\d{10}$', timestamp_str):
                    # Unix timestamp (seconds)
                    unix_time = int(timestamp_str)
                    
                    # GMT time
                    gmt_dt = datetime.utcfromtimestamp(unix_time)
                    gmt_str = gmt_dt.strftime('%Y-%m-%d %H:%M:%S')  # Full format with year
                    
                    # VN time (+7 hours)
                    vn_dt = datetime.fromtimestamp(unix_time)
                    vn_str = vn_dt.strftime('%Y-%m-%d %H:%M:%S')  # Full format with year
                    
                elif re.match(r'^\d{13}$', timestamp_str):
                    # Unix timestamp (milliseconds)
                    unix_time = int(timestamp_str) / 1000
                    
                    # GMT time
                    gmt_dt = datetime.utcfromtimestamp(unix_time)
                    gmt_str = gmt_dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                    # VN time (+7 hours)
                    vn_dt = datetime.fromtimestamp(unix_time)
                    vn_str = vn_dt.strftime('%Y-%m-%d %H:%M:%S')
                    
                else:
                    # Other formats - use the converted result
                    gmt_str = result.get('utc', result['output']).replace(' UTC', '')
                    vn_str = result['output']
                    # Try to shorten the format
                    if len(gmt_str) > 16:
                        gmt_str = gmt_str[-14:]  # Take last 14 chars
                    if len(vn_str) > 16:
                        vn_str = vn_str[-14:]
                
                # Create compact tooltip with icons
                tooltip_text = f"🌍 {gmt_str}\n🇻🇳 {vn_str}"
                
            except Exception as e:
                # Fallback to simple display
                tooltip_text = f"🌍 {result.get('utc', 'N/A')}\n🇻🇳 {result['output']}"
                
            # Show tooltip at cursor position
            QToolTip.showText(cursor_pos, tooltip_text)
            self.is_tooltip_showing = True
            
            # Create timer to hide tooltip and track state
            self.tooltip_timer = QTimer()
            self.tooltip_timer.setSingleShot(True)
            self.tooltip_timer.timeout.connect(self.hide_tooltip)
            self.tooltip_timer.start(4000)  # 4 seconds
            
        else:
            # Error case
            QToolTip.showText(cursor_pos, f"❌ {result['output']}")
            self.is_tooltip_showing = True
            
            self.tooltip_timer = QTimer()
            self.tooltip_timer.setSingleShot(True)
            self.tooltip_timer.timeout.connect(self.hide_tooltip)
            self.tooltip_timer.start(3000)  # 3 seconds
    
    def hide_tooltip(self):
        """Hide tooltip and reset state"""
        QToolTip.hideText()
        self.is_tooltip_showing = False
        if self.tooltip_timer:
            self.tooltip_timer.stop()
            self.tooltip_timer = None
    
    def add_conversion_result(self, result):
        """Add a conversion result to the display"""
        # Create result frame
        frame = QFrame()
        frame.setFrameStyle(QFrame.Box)
        frame.setStyleSheet("""
            QFrame {
                border: 1px solid #bdc3c7;
                border-radius: 8px;
                margin: 5px;
                padding: 10px;
                background-color: #ecf0f1;
            }
        """)
        
        layout = QVBoxLayout(frame)
        
        # Format header
        format_label = QLabel(f"📅 {result['format']}")
        format_label.setStyleSheet("font-weight: bold; color: #2c3e50; font-size: 14px;")
        layout.addWidget(format_label)
        
        # Input
        input_label = QLabel(f"Input: {result['input']}")
        input_label.setStyleSheet("color: #7f8c8d; font-family: monospace;")
        layout.addWidget(input_label)
        
        # Output
        if not result.get('error'):
            output_label = QLabel(f"📊 Human Readable: {result['output']}")
            output_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            layout.addWidget(output_label)
            
            # Additional formats
            if 'iso' in result:
                iso_label = QLabel(f"🔗 ISO Format: {result['iso']}")
                iso_label.setStyleSheet("color: #3498db; font-family: monospace; font-size: 11px;")
                layout.addWidget(iso_label)
            
            if 'unix' in result:
                unix_label = QLabel(f"⏱️ Unix: {result['unix']}")
                unix_label.setStyleSheet("color: #9b59b6; font-family: monospace; font-size: 11px;")
                layout.addWidget(unix_label)
            
            if 'unix_ms' in result:
                unix_ms_label = QLabel(f"⏱️ Unix (ms): {result['unix_ms']}")
                unix_ms_label.setStyleSheet("color: #9b59b6; font-family: monospace; font-size: 11px;")
                layout.addWidget(unix_ms_label)
                
            if 'utc' in result:
                utc_label = QLabel(f"🌍 UTC: {result['utc']}")
                utc_label.setStyleSheet("color: #e67e22; font-family: monospace; font-size: 11px;")
                layout.addWidget(utc_label)
        else:
            error_label = QLabel(f"❌ {result['output']}")
            error_label.setStyleSheet("color: #e74c3c;")
            layout.addWidget(error_label)
        
        # Add timestamp
        now = datetime.now().strftime("%H:%M:%S")
        time_label = QLabel(f"🕐 Detected at: {now}")
        time_label.setStyleSheet("color: #95a5a6; font-size: 10px;")
        layout.addWidget(time_label)
        
        # Insert at the top
        self.results_layout.insertWidget(0, frame)
        
        # Keep only last 10 results
        while self.results_layout.count() > 10:
            item = self.results_layout.takeAt(self.results_layout.count() - 1)
            if item.widget():
                item.widget().deleteLater()
    
    def clear_history(self):
        """Clear conversion history"""
        while self.results_layout.count() > 0:
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        self.status_label.setText("📋 History cleared - Monitoring clipboard...")
        
    def closeEvent(self, event):
        """Handle close event"""
        if self.tray_icon and self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            self.quit_application()
    
    def quit_application(self):
        """Quit the application completely"""
        if self.clipboard_monitor:
            self.clipboard_monitor.stop()
        if self.tray_icon:
            self.tray_icon.hide()
        QApplication.quit()