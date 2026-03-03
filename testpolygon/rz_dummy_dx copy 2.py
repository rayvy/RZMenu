import sys
import os
import argparse
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtCore import QUrl, QSize

# --- D3D11 FORCING ---
# We force D3D11 and a stable render loop to behave like a game
os.environ["QSG_RHI_BACKEND"] = "d3d11"
os.environ["QSG_RENDER_LOOP"] = "basic" 
os.environ["QSG_INFO"] = "1"
os.environ["QSG_D3D11_WINDOW_BACK_BUFFER_COUNT"] = "2" # Common for games

# --- ASSET PATHS ---
EXE_DIR = os.path.dirname(os.path.abspath(__file__))
# Check for background image in current and parent folder
BG_PATH = os.path.join(EXE_DIR, "windowsxp.png").replace("\\", "/")
if not os.path.exists(BG_PATH):
    BG_PATH = os.path.join(EXE_DIR, "..", "windowsxp.png").replace("\\", "/")

# --- ARGUMENT PARSING ---
parser = argparse.ArgumentParser(description="RZMenu Dummy DirectX 11 App")
parser.add_argument("--width", type=int, default=2560)
parser.add_argument("--height", type=int, default=1080)
parser.add_argument("--fullscreen", action="store_true")
args, unknown = parser.parse_known_args()

# QML optimized for 3DMigoto Overlays
# We use f-strings to inject resolution and asset paths safely.
QML_DATA = f"""
import QtQuick 2.15

Rectangle {{
    id: window
    width: {args.width}
    height: {args.height}
    color: "#050610" // Dark blue "Clear Color"

    // Background image to prove it's rendering
    Image {{
        anchors.fill: parent
        source: "file:///{BG_PATH}" 
        fillMode: Image.PreserveAspectCrop
        opacity: 0.2
    }}

    // Animated element to ensure the swapchain is Presenting every frame
    Rectangle {{
        id: spinner
        width: 100; height: 100
        color: "#00ffcc"
        radius: 50
        anchors.centerIn: parent
        
        property real angle: 0
        transform: [
            Rotation {{ angle: spinner.angle; origin.x: 50; origin.y: 50 }},
            Translate {{ x: Math.cos(spinner.angle/50) * 200; y: Math.sin(spinner.angle/50) * 200 }}
        ]
        
        NumberAnimation on angle {{
            from: 0; to: 360; duration: 2000; loops: Animation.Infinite
        }}
    }}

    // Diagnostic HUD
    Column {{
        anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 40
        spacing: 5
        Text {{ text: "RZ EMULATOR - D3D11"; color: "#00ffcc"; font.pixelSize: 32; font.bold: true }}
        Text {{ text: "3DMigoto Hook: Auto (via d3d11.dll)"; color: "white"; font.pixelSize: 18 }}
        Text {{ text: "Resolution: " + parent.parent.width + "x" + parent.parent.height; color: "#aaa"; font.pixelSize: 16 }}
        Text {{ text: "GPU Context: " + GraphicsInfo.renderer; color: "#777"; font.pixelSize: 10 }}
    }}
}}
"""

if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    
    qml_file = os.path.join(EXE_DIR, "ui_runtime.qml")
    with open(qml_file, "w", encoding="utf-8") as f:
        f.write(QML_DATA)
    
    view = QQuickView()
    view.setTitle("RZMenu Emulator - DirectX 11 Mode")
    
    # Configure size from arguments
    target_size = QSize(args.width, args.height)
    view.setMinimumSize(target_size)
    
    if args.fullscreen:
        view.showFullScreen()
    else:
        view.resize(target_size)
        view.show()
    
    view.setSource(QUrl.fromLocalFile(qml_file))
    
    # We no longer need manual LoadLibrary logic here because the user
    # indicated that the .exe will handle loading the d3d11.dll (3DMigoto)
    # natively if placed in the same directory.

    res = app.exec()
    if os.path.exists(qml_file): 
        try: os.remove(qml_file)
        except: pass
    sys.exit(res)
