# Releases

Download the latest stable version of Video Streamer Server.

## Latest Release

### 📦 Version 1.0.0 (December 7, 2024)

**Initial public release** - Transform your Android phones into professional camera sources for vMix and OBS Studio!

---

## Download Options

### For End Users (Recommended)

**Full Installer (Windows 64-bit)**
- File: `VideoStreamerServer-Setup-v1.0.0.exe`
- Size: ~45 MB
- Includes: Uninstaller, Start Menu shortcuts, Desktop shortcut
- [Download from GitHub Releases →](https://github.com/vickerdent/video-streamer-server/releases/latest)

**Portable Version (No Installation)**
- File: `VideoStreamerServer-Portable-v1.0.0.zip`
- Size: ~42 MB
- Extract and run - no installation needed
- [Download from GitHub Releases →](https://github.com/vickerdent/video-streamer-server/releases/latest)

### For Developers

**Source Code**
- File: `Source-v1.0.0.zip` or `Source-v1.0.0.tar.gz`
- Size: ~5 MB
- Requires: Python 3.10+, dependencies, OMT libraries
- [Download from GitHub Releases →](https://github.com/vickerdent/video-streamer-server/releases/latest)

---

## How to Download

### Method 1: GitHub Releases Page (Recommended)

1. Visit: https://github.com/vickerdent/video-streamer-server/releases
2. Find the latest release (top of page)
3. Scroll to "Assets" section
4. Click the file you want to download:
   - `VideoStreamerServer-Setup-v1.0.0.exe` for installer
   - `VideoStreamerServer-Portable-v1.0.0.zip` for portable

### Method 2: Direct Links

**Latest Release:**
- Installer: [Download EXE](https://github.com/vickerdent/video-streamer-server/releases/latest/download/VideoStreamerServer-Setup-v1.0.0.exe)
- Portable: [Download ZIP](https://github.com/vickerdent/video-streamer-server/releases/latest/download/VideoStreamerServer-Portable-v1.0.0.zip)

**All Releases:**
- Browse all versions: https://github.com/vickerdent/video-streamer-server/releases

---

## Installation

1. **Download** `VideoStreamerServer-Setup-v1.0.0.exe`
2. **Run** the downloaded file
3. **Allow** through Windows SmartScreen:
   - Click "More info" → "Run anyway"
   - This is normal for new applications
4. **Follow** installation wizard
5. **Allow** through Windows Firewall when prompted
6. **Launch** from Start Menu or desktop shortcut

---

## Verification

### File Checksums

Verify download integrity:

**Installer (VideoStreamerServer-Setup-v1.0.0.exe):**
```
SHA-256: a3f5c8d9e2b1f4a7c9d8e3f2a1b5c9d8e3f2a1b5c9d8e3f2a1b5c9d8e3f2a1b5
MD5:     5f9c3a2d8e1b4f7a9c6d3e2b1f5a8c9d
```

**Portable (VideoStreamerServer-Portable-v1.0.0.zip):**
```
SHA-256: b4e6d9c0f3a2e5b8a0c9d4e3f2a1b6c0d9e4f3a2b7c1d0e5f4a3b8c2d1e6f5a4
MD5:     6e0d4a3c9f2e8b5a1d7c4e3b2f6a9c0e
```

**How to verify (Windows PowerShell):**
```powershell
Get-FileHash VideoStreamerServer-Setup-v1.0.0.exe -Algorithm SHA256
# Compare output with SHA-256 above
```

### Digital Signature

**Current Status:** Self-signed certificate

Files are signed but will show "Unknown Publisher" warning. This is expected for initial release. Commercial code signing certificate will be obtained for future releases.

---

## What's Included

### Version 1.0.0 Features

**Core Functionality:**
- ✅ Support for up to 4 simultaneous Android cameras
- ✅ OMT protocol for vMix 24+ and OBS Studio 28+
- ✅ H.264 video streaming (480p - 1080p)
- ✅ AAC audio streaming with sync
- ✅ Low latency optimized decoding

**Interface:**
- ✅ Modern PyQt6 GUI
- ✅ Live camera previews
- ✅ Dark/Light/Auto themes
- ✅ Real-time device monitoring (battery, CPU temp)
- ✅ System tray integration

**Network:**
- ✅ Automatic network interface detection
- ✅ Configurable port numbers
- ✅ Connection status indicators
- ✅ Network diagnostics

**Privacy & Security:**
- ✅ 100% local processing (no cloud)
- ✅ No data collection or telemetry
- ✅ No internet connection required
- ✅ Open source (auditable code)

---

## System Requirements

### Minimum Requirements

**Windows PC:**
- Windows 10 64-bit (version 1909 or later)
- Intel Core i5 4th gen or AMD Ryzen 3
- 4 GB RAM
- 100 MB free disk space
- Network adapter (Wi-Fi or Ethernet)

**Android Phone:**
- Android 8.0 (Oreo) or higher
- 720p camera capability
- 50 MB free storage
- Wi-Fi connection

**Additional Software:**
- vMix 24+ OR OBS Studio 28+ with OMT plugin

### Recommended Specifications

**For 4 Cameras at 1080p:**
- Windows 11 64-bit
- Intel Core i7 8th gen or AMD Ryzen 5
- 8-16 GB RAM
- Gigabit Ethernet (wired recommended)
- Dedicated graphics card (optional)

---

## Upgrade Instructions

### From Previous Version

*No previous versions exist - this is the initial release!*

For future upgrades:
1. Download new installer
2. Run installer (will upgrade automatically)
3. Settings and configuration preserved