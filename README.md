# QTKit - QuickTime Kit

Công cụ chuyển đổi timestamp thông minh cho macOS.

## 🚀 Build & Distribution

### Cách build:
```bash
python3 build.py
```

### Files trong project:
- `main.py` - Main application
- `logo.png` - App icon  
- `requirements.txt` - Dependencies
- `build.py` - Build script

### Output:
- `dist/QTKit.app` - Application bundle
- `QTKit-1.0.0.dmg` - Distribution DMG

## 📱 Features

- Tự động detect timestamp trong clipboard
- Hiển thị GMT và VN time qua tooltip
- System tray integration  
- Cấu hình decimal places
- Auto request permissions
- Professional DMG installer

## 🎯 Usage

1. Copy timestamp (vd: 1640995200)
2. Nhấn Cmd+C
3. Tooltip hiện thời gian GMT & VN
4. Right-click tray icon để cấu hình

## 📋 Requirements

- macOS 10.13+
- Python 3.7+
- PySide6, pynput

## 🚀 Installation

1. Download `QTKit-1.0.0.dmg`
2. Mở DMG → kéo QTKit.app vào Applications
3. Mở QTKit từ Applications hoặc Spotlight
4. Cấp quyền Accessibility khi được hỏi

Copyright © 2025 QT Corporation
