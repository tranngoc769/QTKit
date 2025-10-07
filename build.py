#!/usr/bin/env python3
"""
QTKit Enhanced Build Script
Professional build with code signing and distribution
"""

import os
import sys
import subprocess
import shutil
import tempfile

def clean_build():
    """Clean previous builds"""
    print("🧹 Cleaning previous builds...")
    dirs_to_clean = ["build", "dist", "__pycache__"]
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  Removed: {dir_name}/")

def check_tools():
    """Check required build tools"""
    print("🔍 Checking build tools...")
    
    # Check PyInstaller
    try:
        subprocess.run(["pyinstaller", "--version"], capture_output=True, check=True)
        print("  ✅ pyinstaller found")
    except:
        print("  📦 Installing pyinstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
        print("  ✅ pyinstaller installed")
    
    # Check macOS tools (these should always be available on macOS)
    macos_tools = [
        ("codesign", ["codesign", "--version"]),
        ("hdiutil", ["hdiutil", "info"]),
        ("security", ["security", "--help"])
    ]
    
    for tool_name, cmd in macos_tools:
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"  ✅ {tool_name} found")
        except:
            print(f"  ⚠️ {tool_name} not available")

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

def get_signing_identity():
    """Get available code signing identity"""
    print("🔍 Looking for code signing identity...")
    
    try:
        result = subprocess.run([
            "security", "find-identity", "-v", "-p", "codesigning"
        ], capture_output=True, text=True, check=True)
        
        # Look for Developer ID Application certificates
        lines = result.stdout.strip().split('\n')
        dev_ids = []
        
        for line in lines:
            if 'Developer ID Application' in line:
                # Extract identity name
                start = line.find('"') + 1
                end = line.rfind('"')
                if start > 0 and end > start:
                    dev_ids.append(line[start:end])
        
        if dev_ids:
            identity = dev_ids[0]
            print(f"  ✅ Found Developer ID: {identity}")
            return identity
        else:
            # Look for any Mac Developer certificates
            for line in lines:
                if 'Mac Developer' in line or 'Apple Development' in line:
                    start = line.find('"') + 1
                    end = line.rfind('"')
                    if start > 0 and end > start:
                        identity = line[start:end]
                        print(f"  ⚠️ Found development certificate: {identity}")
                        print("    Note: This is for development only, not distribution")
                        return identity
            
            print("  ⚠️ No code signing certificates found")
            print("    App will build but may show security warnings on other machines")
            return None
            
    except subprocess.CalledProcessError:
        print("  ⚠️ Could not check signing identities")
        return None

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
        "--hidden-import=AppKit",  # For macOS integration
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
    """Update Info.plist with comprehensive permissions and metadata"""
    print("📝 Updating Info.plist...")
    
    info_plist = "dist/QTKit.app/Contents/Info.plist"
    if not os.path.exists(info_plist):
        print("⚠️ Info.plist not found")
        return False
    
    try:
        with open(info_plist, 'r') as f:
            content = f.read()
        
        # Comprehensive permissions and metadata
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
             '<true/>'),  # Background app
        ]
        
        for key, value in updates:
            if key not in content:
                content = content.replace('</dict>', f'\t{key}\n\t{value}\n</dict>')
        
        with open(info_plist, 'w') as f:
            f.write(content)
        
        print("✅ Info.plist updated with permissions and metadata")
        return True
    except Exception as e:
        print(f"⚠️ Could not update Info.plist: {e}")
        return False

def sign_app(identity=None):
    """Code sign the app bundle"""
    app_path = "dist/QTKit.app"
    
    if not identity:
        print("⚠️ No signing identity, skipping code signing")
        return True
        
    print(f"✍️ Code signing app with: {identity}")
    
    try:
        # Sign with proper entitlements for distribution
        cmd = [
            "codesign",
            "--force",
            "--options", "runtime",  # Hardened runtime
            "--sign", identity,
            "--deep",
            "--strict",
            "--timestamp",  # Secure timestamp
            app_path
        ]
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("✅ Code signing successful!")
        
        # Verify the signature
        verify_cmd = ["codesign", "--verify", "--verbose", app_path]
        subprocess.run(verify_cmd, check=True, capture_output=True)
        print("✅ Code signature verified!")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Code signing failed: {e}")
        if e.stderr:
            print(f"Error details: {e.stderr}")
        return False

def create_professional_dmg():
    """Create professional distribution DMG"""
    print("📀 Creating professional DMG...")
    
    if not os.path.exists("dist/QTKit.app"):
        print("❌ App not found")
        return False
    
    # Clean old DMG
    dmg_name = "QTKit-1.0.0.dmg"
    if os.path.exists(dmg_name):
        os.remove(dmg_name)
    
    # Create temp directory
    temp_dir = "temp_dmg"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    try:
        # Copy app and create Applications symlink
        print("  📁 Setting up DMG contents...")
        shutil.copytree("dist/QTKit.app", f"{temp_dir}/QTKit.app")
        os.symlink("/Applications", f"{temp_dir}/Applications")
        
        # Create comprehensive installation instructions
        instructions = """QTKit - QuickTime Kit v1.0.0
================================

🎯 HƯỚNG DẪN CÁI ĐẶT:

1️⃣ Kéo QTKit.app vào thư mục Applications
2️⃣ Mở QTKit từ Applications hoặc Spotlight (Cmd+Space)
3️⃣ Cấp quyền Accessibility khi được yêu cầu:
   • System Preferences → Security & Privacy → Privacy → Accessibility
   • Hoặc System Settings → Privacy & Security → Accessibility (macOS 13+)
   • Thêm QTKit vào danh sách và tick chọn

📱 CÁCH SỬ DỤNG:

• App sẽ chạy ngầm (icon xuất hiện trong system tray)
• Copy timestamp (như: 1640995200) và nhấn Cmd+C
• Tooltip sẽ hiện thời gian GMT và VN
• Right-click tray icon để:
  - Mở cấu hình
  - Xem hướng dẫn
  - Thoát app

⚙️ TÍNH NĂNG:

• Tự động detect timestamp trong clipboard
• Hiển thị thời gian GMT và VN
• Configurable decimal places
• Detect mode cho text dài
• Professional system tray integration

🆘 KHẮC PHỤC SỰ CỐ:

Nếu app không hoạt động:
• Kiểm tra quyền Accessibility đã được cấp
• Thử khởi động lại app
• Right-click app → Open nếu bị cảnh báo security

Nếu không tìm thấy app:
• Tìm "QTKit" trong Spotlight (Cmd+Space)
• Hoặc vào Applications folder
• Check system tray (góc trên bên phải màn hình)

═══════════════════════════════════════════════════════
Copyright © 2025 QT Corporation. All rights reserved.
Developed by Quang Trần - QT Corporation
═══════════════════════════════════════════════════════
"""
        
        with open(f"{temp_dir}/📖 HƯỚNG DẪN CÀI ĐẶT VÀ SỬ DỤNG.txt", "w", encoding="utf-8") as f:
            f.write(instructions)
        
        # Create troubleshooting guide
        troubleshooting = """QTKit - Khắc phục sự cố
====================

❌ LỖI THƯỜNG GẶP:

1. "QTKit can't be opened because it is from an unidentified developer"
   → Right-click app → Open → Open anyway
   → Hoặc: System Preferences → Security → "Open Anyway"

2. App không phản ứng khi nhấn Cmd+C
   → Kiểm tra quyền Accessibility
   → System Preferences → Security & Privacy → Privacy → Accessibility
   → Đảm bảo QTKit đã được tick chọn

3. Không tìm thấy app sau khi cài
   → Tìm "QTKit" trong Spotlight (Cmd+Space)
   → Hoặc vào /Applications/QTKit.app
   → Check system tray icon

4. App bị crash hoặc không khởi động
   → Mở Terminal và chạy: /Applications/QTKit.app/Contents/MacOS/QTKit
   → Xem error messages
   → Kiểm tra log: ~/Library/Logs/QTKit/qtkit.log

🔧 RESET APP:

Nếu app hoạt động không bình thường:
1. Quit app từ tray menu
2. Xóa settings: ~/Library/Preferences/com.qt-corporation.qtkit.plist
3. Khởi động lại app

📞 HỖ TRỢ:

Nếu vẫn gặp vấn đề, liên hệ QT Corporation
Hoặc check logs tại: ~/Library/Logs/QTKit/qtkit.log
"""
        
        with open(f"{temp_dir}/🔧 KHẮC PHỤC SỰ CỐ.txt", "w", encoding="utf-8") as f:
            f.write(troubleshooting)
        
        # Create DMG with professional settings
        print("  🔨 Creating DMG file...")
        cmd = [
            "hdiutil", "create",
            "-volname", "QTKit Installer",
            "-srcfolder", temp_dir,
            "-ov", "-format", "UDZO",
            "-imagekey", "zlib-level=9",  # Best compression
            dmg_name
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        shutil.rmtree(temp_dir)
        print(f"✅ Professional DMG created: {dmg_name}")
        return True
        
    except Exception as e:
        print(f"❌ DMG creation failed: {e}")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        return False

def main():
    print("🚀 QTKit Enhanced Build Script")
    print("=" * 40)
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {sys.platform}")
    
    if sys.platform != "darwin":
        print("❌ This script is for macOS only!")
        return
    
    # Check requirements
    required_files = ["main.py", "logo.png", "requirements.txt"]
    for file in required_files:
        if not os.path.exists(file):
            print(f"❌ Required file not found: {file}")
            return
        print(f"✅ Found: {file}")
    
    # Build process
    print("\n" + "=" * 40)
    check_tools()
    clean_build()
    
    if not install_requirements():
        return
        
    if not build_app():
        return
        
    if not update_info_plist():
        return
    
    # Code signing
    print("\n" + "=" * 40)
    signing_identity = get_signing_identity()
    signed = sign_app(signing_identity)
    
    # DMG creation
    print("\n" + "=" * 40)
    choice = input("📀 Create professional DMG? (y/n): ").lower()
    dmg_created = False
    if choice == 'y':
        dmg_created = create_professional_dmg()
    
    # Summary
    print("\n" + "=" * 40)
    print("🎉 Build completed!")
    print("\n📁 Output files:")
    print("  ✅ dist/QTKit.app - Application bundle")
    if dmg_created:
        print("  ✅ QTKit-1.0.0.dmg - Distribution installer")
    
    print("\n📋 Build summary:")
    print(f"  • Code signed: {'✅ Yes' if signed and signing_identity else '⚠️ No (may show warnings)'}")
    print(f"  • Permissions: ✅ Comprehensive Info.plist")
    print(f"  • Distribution: {'✅ Professional DMG' if dmg_created else '⚠️ App bundle only'}")
    
    if not signing_identity:
        print("\n💡 To eliminate security warnings:")
        print("  1. Get Apple Developer ID certificate ($99/year)")
        print("  2. Rebuild with proper code signing")
        print("  3. Optionally notarize with Apple")
    
    print("\n🚀 Ready for distribution!")

if __name__ == "__main__":
    main()
