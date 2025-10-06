#!/usr/bin/env python3
import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from timestamp_viewer import SimpleTimestampViewer

def main():
    # Tạo QApplication
    app = QApplication(sys.argv)
    
    # Cài đặt app properties
    app.setApplicationName("Timestamp Viewer")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("TimestampTools")
    
    # QUAN TRỌNG: Không thoát khi đóng window (chạy ngầm)
    app.setQuitOnLastWindowClosed(False)
    
    # Ẩn dock icon trên macOS (chạy ngầm hoàn toàn)
    if sys.platform == "darwin":
        import AppKit
        AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyProhibited)
    
    # Tạo main viewer object
    viewer = SimpleTimestampViewer()
    
    print("🚀 Timestamp Viewer đã khởi động - chạy ngầm...")
    print("📋 Copy timestamp → Hiển thị ngay tại vị trí chuột!")
    print("💡 Đơn giản và tiện lợi!")
    
    # Chạy app
    sys.exit(app.exec())

if __name__ == '__main__':
    main()