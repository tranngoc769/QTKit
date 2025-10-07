#!/usr/bin/env python3
"""
QTKit Build Script - All in One
Simple build script for QTKit macOS app
"""

import os
import sys
import subprocess
import shutil

def clean_build():
    """Clean previous builds"""
    print("🧹 Cleaning previous builds...")
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  Removed: {dir_name}/")

def install_requirements():
    """Install required packages"""
    print("📦 Installing requirements...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True)
        print("✅ Requirements installed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        return False
    return True

def build_app():
    """Build the app using PyInstaller"""
    print("🔨 Building QTKit app...")
    
    cmd = [
        "pyinstaller",
        "--name=QTKit",
        "--onedir",
        "--windowed", 
        "--icon=logo.png",
        "--osx-bundle-identifier=com.qt-corporation.qtkit",
        "--add-data", "logo.png:.",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets", 
        "--hidden-import=pynput.keyboard",
        "--clean",
        "--noconfirm",
        "main.py"
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print("✅ App built successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        return False

def update_permissions():
    """Add permission descriptions to Info.plist"""
    print("📝 Adding permission descriptions...")
    
    info_plist = "dist/QTKit.app/Contents/Info.plist"
    if not os.path.exists(info_plist):
        print("⚠️ Info.plist not found")
        return
    
    try:
        with open(info_plist, 'r') as f:
            content = f.read()
        
        permissions = [
            ('<key>NSAccessibilityUsageDescription</key>',
             '<string>QTKit cần quyền Accessibility để theo dõi phím tắt Cmd+C.</string>'),
            ('<key>NSInputMonitoringUsageDescription</key>', 
             '<string>QTKit cần quyền Input Monitoring để phát hiện Cmd+C.</string>')
        ]
        
        for key, value in permissions:
            if key not in content:
                content = content.replace('</dict>', f'\t{key}\n\t{value}\n</dict>')
        
        with open(info_plist, 'w') as f:
            f.write(content)
        
        print("✅ Permissions added")
    except Exception as e:
        print(f"⚠️ Could not update permissions: {e}")

def create_dmg():
    """Create distribution DMG"""
    print("📀 Creating DMG...")
    
    if not os.path.exists("dist/QTKit.app"):
        print("❌ App not found")
        return False
    
    # Clean old DMG
    if os.path.exists("QTKit-1.0.0.dmg"):
        os.remove("QTKit-1.0.0.dmg")
    
    # Create temp directory
    temp_dir = "temp_dmg"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    try:
        # Copy app and create Applications symlink
        shutil.copytree("dist/QTKit.app", f"{temp_dir}/QTKit.app")
        os.symlink("/Applications", f"{temp_dir}/Applications")
        
        # Create instructions
        instructions = """QTKit - QuickTime Kit

CÁCH CÀI ĐẶT:
1. Kéo QTKit.app vào thư mục Applications
2. Mở QTKit từ Applications hoặc Spotlight (Cmd+Space) 
3. Cấp quyền Accessibility khi được yêu cầu

CÁCH SỬ DỤNG:
- Copy timestamp và nhấn Cmd+C để xem thời gian
- Right-click tray icon để cấu hình
- App chạy ngầm trong system tray

Copyright © 2025 QT Corporation
"""
        
        with open(f"{temp_dir}/HƯỚNG DẪN.txt", "w", encoding="utf-8") as f:
            f.write(instructions)
        
        # Create DMG
        cmd = [
            "hdiutil", "create",
            "-volname", "QTKit Installer",
            "-srcfolder", temp_dir,
            "-ov", "-format", "UDZO",
            "QTKit-1.0.0.dmg"
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        shutil.rmtree(temp_dir)
        print("✅ DMG created: QTKit-1.0.0.dmg")
        return True
        
    except Exception as e:
        print(f"❌ DMG creation failed: {e}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return False

def main():
    print("🚀 QTKit Build Script")
    print("=" * 30)
    
    if sys.platform != "darwin":
        print("❌ macOS only!")
        return
    
    # Check requirements
    if not os.path.exists("main.py"):
        print("❌ main.py not found!")
        return
        
    if not os.path.exists("logo.png"):
        print("❌ logo.png not found!")
        return
    
    # Build process
    clean_build()
    
    if not install_requirements():
        return
        
    if not build_app():
        return
        
    update_permissions()
    
    # Ask for DMG
    choice = input("\n📀 Create DMG? (y/n): ").lower()
    if choice == 'y':
        create_dmg()
    
    print("\n🎉 Build completed!")
    print("📁 Files:")
    print("  - dist/QTKit.app")
    if os.path.exists("QTKit-1.0.0.dmg"):
        print("  - QTKit-1.0.0.dmg")
    print("\n🚀 Ready to distribute!")

if __name__ == "__main__":
    main()
