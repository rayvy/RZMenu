#RZMenu/diagnose_pyside.py
#!/usr/bin/env python3
"""
Diagnostic and Repair script for PySide6 in Blender RZMenu addon.
Run this script to fix pip and install PySide6 6.9.1.
"""

import sys
import subprocess
import importlib

TARGET_VERSION = "6.10.1"

print("=" * 60)
print("PySide6 Diagnostic & Repair for Blender RZMenu")
print("=" * 60)

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print()

def run_pip_command(args, description):
    print(f"[{description}]...")
    full_args = [sys.executable, "-m", "pip"] + args
    try:
        result = subprocess.run(full_args, capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ Success")
            return True
        else:
            print("✗ Failed")
            print(f"  Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"✗ Exception: {e}")
        return False

# 1. Check and Repair pip
print("1. Checking pip installation...")
pip_broken = False
try:
    import pip
    # Try a simple pip command to check for corruption
    subprocess.check_call([sys.executable, "-m", "pip", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("✓ pip seems to be working")
except (ImportError, subprocess.CalledProcessError):
    print("! pip is broken or missing. Attempting repair...")
    pip_broken = True

if pip_broken:
    print("Attempting to repair pip using ensurepip...")
    try:
        subprocess.check_call([sys.executable, "-m", "ensurepip", "--default-pip"])
        print("✓ pip repaired successfully")
        # Upgrade pip to be sure
        run_pip_command(["install", "--upgrade", "pip"], "Upgrading pip")
    except Exception as e:
        print(f"✗ Failed to repair pip: {e}")
        print("Please try running Blender as Administrator.")

# 2. Install/Update PySide6
print(f"\n2. Checking PySide6 (Target: {TARGET_VERSION})...")
current_version = None
try:
    importlib.invalidate_caches()
    import PySide6
    current_version = PySide6.__version__
    print(f"  Current PySide6 version: {current_version}")
except ImportError:
    print("  PySide6 is not installed")

if current_version != TARGET_VERSION:
    print(f"\nInstalling PySide6 {TARGET_VERSION}...")
    # Use --force-reinstall to fix potential broken files
    success = run_pip_command(["install", f"PySide6=={TARGET_VERSION}", "--force-reinstall"], "Installing PySide6")
    
    if success:
        print("\n✓ Installation complete. Please RESTART Blender.")
    else:
        print("\n✗ Installation failed. Check permissions or internet connection.")
else:
    print("\n✓ PySide6 is already installed at the correct version.")

print("\n" + "=" * 60)
