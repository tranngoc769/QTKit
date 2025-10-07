#!/usr/bin/env python3
"""
QTKit Build Script
Build macOS app bundle using PyInstaller
"""

import os
import sys
import subprocess
from pathlib import Path

def build_app():
    """Build macOS app using PyInstaller"""
    
    # Check if logo.png exists, fallback to logo.png
    logo_file = "logo.png" if os.path.exists("logo.png") else "logo.png"
    
    if not os.path.exists(logo_file):
        print(f"❌ Error: Neither logo.png nor logo.png found!")
        return False
    
    print(f"🎨 Using {logo_file} as app icon")
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--name=QTKit",
        "--onedir",  # Create one directory
        "--windowed",  # No console window
        f"--icon={logo_file}",  # App icon
        "--osx-bundle-identifier=com.qt-corporation.qtkit",
        "--add-data", f"{logo_file}:.",  # Include logo in bundle
        "--add-data", "logo.png:.",  # Include logo.png for tray icon
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui", 
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=pynput.keyboard",
        "--clean",  # Clean cache
        "main.py"
    ]
    
    print("🔨 Building macOS app...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Build successful!")
        print(f"📦 App created at: dist/QTKit.app")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        print(f"Error output: {e.stderr}")
        return False

def create_dmg():
    """Create DMG file for distribution"""
    print("📀 Creating DMG file...")
    
    dmg_name = "QTKit-1.0.0.dmg"
    
    # Remove old DMG if exists
    if os.path.exists(dmg_name):
        os.remove(dmg_name)
    
    cmd = [
        "hdiutil", "create",
        "-volname", "QTKit",
        "-srcfolder", "dist/QTKit.app",
        "-ov", "-format", "UDZO",
        dmg_name
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ DMG created: {dmg_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ DMG creation failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 QTKit macOS Build Script")
    print("=" * 40)
    
    # Check if we're on macOS
    if sys.platform != "darwin":
        print("❌ This script is for macOS only!")
        sys.exit(1)
    
    # Check if PyInstaller is installed
    try:
        subprocess.run(["pyinstaller", "--version"], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Build the app
    if build_app():
        print("\n🎉 Build completed successfully!")
        
        # Ask if user wants to create DMG
        create_dmg_choice = input("\n📀 Create DMG file for distribution? (y/n): ").lower()
        if create_dmg_choice == 'y':
            create_dmg()
        
        print("\n📁 Files created:")
        print("  - dist/QTKit.app (Application bundle)")
        if os.path.exists("QTKit-1.0.0.dmg"):
            print("  - QTKit-1.0.0.dmg (Distribution file)")
            
    else:
        print("❌ Build failed!")
        sys.exit(1)
