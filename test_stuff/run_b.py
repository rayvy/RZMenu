import subprocess
import os

blender_exe = r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"
if not os.path.exists(blender_exe):
    # try 5.0
    blender_exe = r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"

script = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\test_spatial_blender.py"
print(f"Running {blender_exe} with script {script}")

cmd = [blender_exe, "-b", "-P", script]
result = subprocess.run(cmd, capture_output=True, text=True)

print("STDOUT:")
print(result.stdout)
print("STDERR:")
print(result.stderr)
