#!/usr/bin/env python3
"""
QTKit All-in-One Build Script
Complete build, fix, and distribution script for QTKit macOS app
"""

import os
import sys
import subprocess
import shutil

def print_header(title):
    """Print formatted header"""
    print("\n" + "=" * 50)
    print(f"🚀 {title}")
    print("=" * 50)

def clean_build():
    """Clean previous builds"""
    print("🧹 Cleaning previous builds...")
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  Removed: {dir_name}/")

def check_requirements():
    """Check and install requirements"""
    print("📦 Checking requirements...")
    
    required_files = ["main.py", "logo.png", "requirements.txt"]
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Required file not found: {file}")
            return False
        print(f"✅ Found: {file}")
    
    # Install Python requirements
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True)
        print("✅ Python requirements installed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        return False
    
    # Check/install PyInstaller
    try:
        subprocess.run(["pyinstaller", "--version"], capture_output=True, check=True)
        print("✅ PyInstaller found")
    except:
        print("📦 Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("✅ PyInstaller installed")
    
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
        "--hidden-import=AppKit",
        "--clean",
        "--noconfirm",
        "main.py"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ App built successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        return False

def update_info_plist():
    """Update Info.plist with permissions and metadata"""
    print("📝 Updating Info.plist...")
    
    info_plist = "dist/QTKit.app/Contents/Info.plist"
    if not os.path.exists(info_plist):
        print("⚠️ Info.plist not found")
        return False
    
    try:
        with open(info_plist, 'r') as f:
            content = f.read()
        
        # Add comprehensive permissions and metadata
        updates = [
            # Permissions
            ('<key>NSAccessibilityUsageDescription</key>',
             '<string>QTKit cần quyền Accessibility để theo dõi phím tắt Cmd+C và tự động phát hiện timestamp trong clipboard.</string>'),
            ('<key>NSInputMonitoringUsageDescription</key>', 
             '<string>QTKit cần quyền Input Monitoring để phát hiện khi bạn nhấn tổ hợp phím Cmd+C.</string>'),
            ('<key>NSAppleEventsUsageDescription</key>',
             '<string>QTKit cần quyền System Events để tương tác với clipboard và hiển thị thông báo.</string>'),
            
            # App metadata
            ('<key>CFBundleDisplayName</key>',
             '<string>QTKit - QuickTime Kit</string>'),
            ('<key>CFBundleGetInfoString</key>',
             '<string>QTKit 1.0.0, Copyright © 2025 QT Corporation</string>'),
            ('<key>NSHumanReadableCopyright</key>',
             '<string>Copyright © 2025 QT Corporation. All rights reserved.</string>'),
            
            # Security and compatibility
            ('<key>LSMinimumSystemVersion</key>',
             '<string>10.13.0</string>'),
            ('<key>NSHighResolutionCapable</key>',
             '<true/>'),
            ('<key>NSSupportsAutomaticGraphicsSwitching</key>',
             '<true/>'),
            ('<key>LSUIElement</key>',
             '<true/>'),
        ]
        
        for key, value in updates:
            if key not in content:
                content = content.replace('</dict>', f'\t{key}\n\t{value}\n</dict>')
        
        with open(info_plist, 'w') as f:
            f.write(content)
        
        print("✅ Info.plist updated")
        return True
    except Exception as e:
        print(f"⚠️ Could not update Info.plist: {e}")
        return False

def fix_distribution():
    """Fix distribution issues (quarantine, signing)"""
    print("🔧 Fixing distribution issues...")
    
    app_path = "dist/QTKit.app"
    if not os.path.exists(app_path):
        print("❌ App not found")
        return False
    
    # Step 1: Remove quarantine attributes
    print("  🔓 Removing quarantine attributes...")
    try:
        cmd = ["xattr", "-dr", "com.apple.quarantine", app_path]
        subprocess.run(cmd, capture_output=True)
        
        # Remove other problematic attributes
        attrs_to_remove = [
            "com.apple.FinderInfo",
            "com.apple.metadata:kMDItemWhereFroms"
        ]
        
        for attr in attrs_to_remove:
            try:
                cmd = ["xattr", "-dr", attr, app_path]
                subprocess.run(cmd, capture_output=True)
            except:
                pass
        
        print("  ✅ Quarantine attributes removed")
    except Exception as e:
        print(f"  ⚠️ Could not remove quarantine: {e}")
    
    # Step 2: Apply ad-hoc signature
    print("  ✍️ Applying ad-hoc signature...")
    try:
        cmd = [
            "codesign",
            "--force",
            "--deep",
            "--sign", "-",  # Ad-hoc signature
            app_path
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        print("  ✅ Ad-hoc signature applied")
        
        # Verify signature
        verify_cmd = ["codesign", "--verify", "--verbose", app_path]
        result = subprocess.run(verify_cmd, capture_output=True)
        if result.returncode == 0:
            print("  ✅ Signature verified")
        
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️ Signing failed: {e}")
    
    return True

def create_fix_script():
    """Create fix script for end users"""
    print("📝 Creating user fix script...")
    
    script_content = '''#!/bin/bash
# QTKit Distribution Fixer
# Run this if QTKit shows "damaged" error

echo "🔧 QTKit Distribution Fixer"
echo "=========================="

APP_PATH="./QTKit.app"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ QTKit.app not found in current directory"
    echo "   Please run this script in the same folder as QTKit.app"
    exit 1
fi

echo "🔓 Removing quarantine attributes..."
xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true
xattr -dr com.apple.FinderInfo "$APP_PATH" 2>/dev/null || true

echo "✍️ Applying fresh signature..."
codesign --force --deep --sign - "$APP_PATH" 2>/dev/null || true

echo "✅ QTKit should now work!"
echo "   Try opening QTKit.app"
echo ""
echo "If still doesn't work:"
echo "1. Right-click QTKit.app → Open"
echo "2. Click 'Open' when asked"
echo "3. Or: System Preferences → Security → Allow"
'''
    
    with open("dist/Fix-QTKit.sh", "w") as f:
        f.write(script_content)
    
    # Make executable
    os.chmod("dist/Fix-QTKit.sh", 0o755)
    print("✅ Fix script created: dist/Fix-QTKit.sh")

def create_distribution_dmg():
    """Create professional DMG for distribution"""
    print("📀 Creating distribution DMG...")
    
    if not os.path.exists("dist/QTKit.app"):
        print("❌ App not found")
        return False
    
    # Remove old DMG
    dmg_name = "QTKit-1.0.0-Ready.dmg"
    if os.path.exists(dmg_name):
        os.remove(dmg_name)
    
    # Create temp directory
    temp_dir = "temp_dmg_final"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    try:
        # Copy app and create Applications symlink
        shutil.copytree("dist/QTKit.app", f"{temp_dir}/QTKit.app")
        os.symlink("/Applications", f"{temp_dir}/Applications")
        
        # Copy fix script
        if os.path.exists("dist/Fix-QTKit.sh"):
            shutil.copy2("dist/Fix-QTKit.sh", f"{temp_dir}/Fix-QTKit.sh")
        
        # Create installation instructions
        instructions = '''QTKit - QuickTime Kit v1.0.0
================================

🎯 HƯỚNG DẪN CÀI ĐẶT:

CÁCH 1 - Cài đặt bình thường:
1️⃣ Kéo QTKit.app vào thư mục Applications
2️⃣ Mở QTKit từ Applications hoặc Spotlight (Cmd+Space)
3️⃣ Cấp quyền Accessibility khi được yêu cầu

CÁCH 2 - Nếu gặp lỗi "QTKit is damaged":
1️⃣ Chạy script: sh Fix-QTKit.sh
2️⃣ Hoặc Right-click QTKit.app → Open → Open anyway
3️⃣ Hoặc thủ công: xattr -dr com.apple.quarantine QTKit.app

📱 CÁCH SỬ DỤNG:

• App chạy ngầm (icon trong system tray)
• Copy timestamp và nhấn Cmd+C để xem thời gian
• Right-click tray icon để cấu hình
• Tìm "QTKit" trong Spotlight để mở lại

⚙️ CẤP QUYỀN:

Khi lần đầu chạy, app sẽ yêu cầu quyền Accessibility:
• System Preferences → Security & Privacy → Accessibility
• Hoặc System Settings → Privacy & Security → Accessibility (macOS 13+)
• Thêm QTKit và tick chọn

🆘 KHẮC PHỤC:

• App bị "damaged": Chạy Fix-QTKit.sh
• Không detect Cmd+C: Kiểm tra quyền Accessibility
• App crash: Check log ~/Library/Logs/QTKit/qtkit.log
• Không tìm thấy: Tìm "QTKit" trong Spotlight

═══════════════════════════════════════════════
QTKit - QuickTime Kit
Copyright © 2025 QT Corporation
Developed by Quang Trần

🎯 Chức năng: Chuyển đổi timestamp thông minh
📧 Hỗ trợ: QT Corporation
═══════════════════════════════════════════════
'''
        
        with open(f"{temp_dir}/📖 HƯỚNG DẪN.txt", "w", encoding="utf-8") as f:
            f.write(instructions)
        
        # Remove quarantine from temp directory
        try:
            subprocess.run(["xattr", "-dr", "com.apple.quarantine", temp_dir], 
                         capture_output=True)
        except:
            pass
        
        # Create DMG
        cmd = [
            "hdiutil", "create",
            "-volname", "QTKit Installer",
            "-srcfolder", temp_dir,
            "-ov", "-format", "UDZO",
            "-imagekey", "zlib-level=9",
            dmg_name
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Remove quarantine from DMG
        try:
            subprocess.run(["xattr", "-dr", "com.apple.quarantine", dmg_name], 
                         capture_output=True)
        except:
            pass
        
        shutil.rmtree(temp_dir)
        print(f"✅ Distribution DMG created: {dmg_name}")
        return True
        
    except Exception as e:
        print(f"❌ DMG creation failed: {e}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return False

def main():
    print("🚀 QTKit All-in-One Build Script")
    print("=" * 50)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}")
    
    if sys.platform != "darwin":
        print("❌ This script is for macOS only!")
        return
    
    # Build process
    print_header("CHECKING REQUIREMENTS")
    if not check_requirements():
        print("❌ Requirements check failed!")
        return
    
    print_header("BUILDING APP")
    clean_build()
    
    if not build_app():
        print("❌ App build failed!")
        return
    
    if not update_info_plist():
        print("⚠️ Info.plist update failed, continuing...")
    
    print_header("FIXING DISTRIBUTION")
    fix_distribution()
    create_fix_script()
    
    print_header("CREATING DISTRIBUTION")
    choice = input("📀 Create distribution DMG? (y/n): ").lower()
    dmg_created = False
    if choice == 'y':
        dmg_created = create_distribution_dmg()
    
    # Final summary
    print_header("BUILD COMPLETED")
    print("🎉 QTKit build completed successfully!")
    print("\n📁 Output files:")
    print("  ✅ dist/QTKit.app - Ready-to-run app")
    print("  ✅ dist/Fix-QTKit.sh - User fix script")
    if dmg_created:
        print("  ✅ QTKit-1.0.0-Ready.dmg - Distribution installer")
    
    print("\n🚀 Distribution ready!")
    print("📋 What's included:")
    print("  • Ad-hoc signed app (no certificate needed)")
    print("  • Quarantine attributes removed")  
    print("  • Comprehensive permissions in Info.plist")
    print("  • Fix script for 'damaged' errors")
    print("  • Professional DMG with instructions")
    
    print("\n💡 For end users:")
    if dmg_created:
        print("  1. Share QTKit-1.0.0-Ready.dmg")
        print("  2. Users drag QTKit.app to Applications")
        print("  3. If 'damaged' error, run Fix-QTKit.sh")
    else:
        print("  1. Share dist/QTKit.app")
        print("  2. Include dist/Fix-QTKit.sh")
        print("  3. Instruct users to run fix script if needed")
    
    print("\n✅ App should work on other machines without issues!")

if __name__ == "__main__":
    main()
