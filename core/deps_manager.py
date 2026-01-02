# RZMenu/core/deps_manager.py (ex dependencies.py)
import bpy
import sys
import subprocess
import importlib
import threading
import urllib.request
import os
import platform
import tempfile
import site
import shutil
import time
import datetime

# --- КОНФИГУРАЦИЯ ---
DEPS = [
    {
        "name": "PySide6",
        "import_name": "PySide6",
        "pip_name": "PySide6",
        "target_version": "6.10.1", 
        "is_optional": True 
    },
    {
        "name": "XXMI Tools",
        "import_name": "XXMITools",
        "pip_name": None,
        "target_version": "1.6.3",
        "is_optional": True
    }
]

_installing = False
_install_log = []

def is_installing():
    global _installing
    return _installing

def get_last_log():
    global _install_log
    return "\n".join(_install_log[-30:])

def log_msg(msg):
    print(f"[RZM-Installer] {msg}")
    global _install_log
    _install_log.append(msg)

def check_internet():
    try:
        urllib.request.urlopen('https://pypi.org', timeout=3.0)
        return True
    except:
        return False

def get_package_version(import_name):
    try:
        from importlib.metadata import version
        return version(import_name)
    except Exception:
        try:
            mod = importlib.import_module(import_name)
            for attr in ["__version__", "VERSION", "version"]:
                if hasattr(mod, attr):
                    return str(getattr(mod, attr))
        except:
            pass
    return None

def check_addon_version(addon_identifier):
    import addon_utils
    addon_utils.modules()
    for mod in addon_utils.modules():
        if mod.__name__ == addon_identifier or mod.bl_info.get("name") == addon_identifier:
            version_tuple = mod.bl_info.get("version", (0, 0, 0))
            return ".".join(map(str, version_tuple))
    return None

def compare_versions(current, target):
    if not current: return -1
    if current == target: return 0
    try:
        c_parts = [int(x) for x in current.split('.')]
        t_parts = [int(x) for x in target.split('.')]
        if c_parts < t_parts: return -1
        if c_parts > t_parts: return 1
        return 0
    except:
        return -1 if current < target else 1

def run_command_live(args, callback=None):
    """Запуск с живым логом и защитой от проблем кодировки."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    
    user_base = site.getuserbase()
    scripts_path = os.path.join(user_base, "Scripts") if os.name == 'nt' else os.path.join(user_base, "bin")
    env["PATH"] = scripts_path + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"

    startupinfo = None
    if platform.system() == 'Windows':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8', 
        errors='replace',
        env=env,
        startupinfo=startupinfo,
        bufsize=1,
        universal_newlines=True
    )

    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            clean_line = line.strip()
            if clean_line:
                log_msg(f"CMD: {clean_line}")
                if callback and "%" in clean_line:
                    callback(50, f"Working... {clean_line[:15]}...")

    return process.poll()

def get_user_pip_exe():
    user_base = site.getuserbase()
    candidates = [
        os.path.join(user_base, "Scripts", "pip.exe"),
        os.path.join(user_base, "Scripts", "pip3.exe"),
        os.path.join(user_base, f"Python{sys.version_info.major}{sys.version_info.minor}", "Scripts", "pip.exe"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def ensure_user_pip(callback):
    url = "https://bootstrap.pypa.io/get-pip.py"
    temp_dir = tempfile.gettempdir()
    target_path = os.path.join(temp_dir, "get-pip.py")
    
    log_msg("Downloading get-pip.py...")
    if callback: callback(10, "Downloading bootstrap tool...")
    
    try:
        with urllib.request.urlopen(url) as response, open(target_path, 'wb') as out_file:
            out_file.write(response.read())
    except Exception as e:
        log_msg(f"Download failed: {e}")
        return False

    log_msg("Running get-pip.py to create User PIP...")
    if callback: callback(20, "Creating User Environment...")

    cmd = [sys.executable, target_path, "--user", "--force-reinstall", "--no-warn-script-location"]
    code = run_command_live(cmd, callback)
    
    try:
        os.remove(target_path)
    except:
        pass
        
    return code == 0

def move_conflicting_packages(callback):
    """
    Пытается переименовать существующие папки PySide6 и shiboken6,
    чтобы освободить место для новой установки, даже если файлы заблокированы.
    """
    try:
        site_packages = site.getusersitepackages()
        if not os.path.exists(site_packages):
            return True

        targets = ["PySide6", "shiboken6"]
        ts = int(time.time())
        
        for name in targets:
            path = os.path.join(site_packages, name)
            if os.path.exists(path):
                new_name = f"{name}_trash_{ts}"
                new_path = os.path.join(site_packages, new_name)
                log_msg(f"Moving locked folder {name} to {new_name}...")
                
                try:
                    os.rename(path, new_path)
                except OSError as e:
                    # Если переименовать не удалось (совсем жесткий лок), это проблема
                    log_msg(f"Warning: Could not move {name}: {e}")
                    # Но мы продолжим, надеясь, что pip справится
                    
    except Exception as e:
        log_msg(f"Pre-install cleanup error: {e}")

def install_logic(package_name, callback):
    if callback: callback(5, "Checking Internet...")
    if not check_internet():
        log_msg("No Internet.")
        if callback: callback(-1, "No Internet Connection")
        return

    if not ensure_user_pip(callback):
        log_msg("Failed to bootstrap pip.")
        if callback: callback(-1, "Bootstrap Failed.")
        return

    pip_exe = get_user_pip_exe()
    if not pip_exe:
        log_msg("Error: pip.exe not found.")
        pip_exe = "pip" 
    else:
        log_msg(f"Found User PIP at: {pip_exe}")

    # --- ЭТАП ОЧИСТКИ ---
    # Перемещаем старые папки, чтобы обойти блокировку Windows
    if callback: callback(35, "Cleaning up old files...")
    move_conflicting_packages(callback)
    # --------------------

    if callback: callback(40, f"Installing {package_name}...")
    log_msg(f"Installing {package_name} using isolated User PIP...")
    
    install_cmd = [
        pip_exe, "install", package_name,
        "--user",
        "--upgrade",
        "--ignore-installed",
        "--no-warn-script-location"
    ]
    
    code = run_command_live(install_cmd, callback)

    if code == 0:
        log_msg("Installation Success!")
        if callback: callback(100, "Done! Restart Blender.")
        try:
            importlib.reload(site)
            user_site = site.getusersitepackages()
            if user_site not in sys.path:
                sys.path.append(user_site)
        except:
            pass
    else:
        log_msg(f"Install failed with code {code}.")
        if callback: callback(-1, "Installation Failed. Check Log.")

def install_package(package_name, callback=None):
    global _installing
    if _installing: return

    def _worker():
        global _installing
        _installing = True
        try:
            install_logic(package_name, callback)
        except Exception as e:
            import traceback
            log_msg(f"Critical: {traceback.format_exc()}")
            if callback: callback(-1, f"Script Error: {e}")
        finally:
            _installing = False

    threading.Thread(target=_worker, daemon=True).start()