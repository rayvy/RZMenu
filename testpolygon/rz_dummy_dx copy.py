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
if hasattr(sys, '_MEIPASS'):
    EXE_DIR = sys._MEIPASS
else:
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))

BG_PATH = os.path.join(EXE_DIR, "windowsxp.png").replace("\\", "/")
if not os.path.exists(BG_PATH):
    # Try parent directory as fallback for development
    BG_PATH = os.path.join(os.path.dirname(EXE_DIR), "windowsxp.png").replace("\\", "/")

# --- ARGUMENT PARSING ---
parser = argparse.ArgumentParser(description="RZMenu Dummy DirectX 11 App")
parser.add_argument("--width", type=int, default=2560)
parser.add_argument("--height", type=int, default=1080)
parser.add_argument("--fullscreen", action="store_true")
args, unknown = parser.parse_known_args()

# QML optimized for 3DMigoto Overlays
# 1. NO RADIUS (to avoid Stencil Buffer usage)
# 2. Full-screen animation (to force Scissor Rect = Full Screen)
QML_DATA = f"""
import QtQuick 2.15

Rectangle {{
    id: window
    width: {args.width}
    height: {args.height}
    color: "#050610" // Dark blue "Clear Color"

    // Background image
    Image {{
        anchors.fill: parent
        source: "file:///{BG_PATH}" 
        fillMode: Image.PreserveAspectCrop
        opacity: 0.2
    }}

    // Rotating full-screen gradient OR large element 
    // to ensure NO partial updates and NO small Scissor Rects.
    Rectangle {{
        id: bgAnim
        anchors.fill: parent
        opacity: 0.1
        gradient: Gradient {{
            GradientStop {{ position: 0.0; color: "transparent" }}
            GradientStop {{ position: 0.5; color: "#00ffcc" }}
            GradientStop {{ position: 1.0; color: "transparent" }}
        }}
        
        property real angle: 0
        transform: Rotation {{ angle: bgAnim.angle; origin.x: {args.width/2}; origin.y: {args.height/2} }}
        
        NumberAnimation on angle {{
            from: 0; to: 360; duration: 5000; loops: Animation.Infinite
        }}
    }}

    // Large central element without radius
    Rectangle {{
        width: 300; height: 300
        color: "#00ffcc"
        opacity: 0.5
        anchors.centerIn: parent
        
        property real scale: 1.0
        scale: scale
        
        SequentialAnimation on scale {{
            loops: Animation.Infinite
            NumberAnimation {{ from: 1.0; to: 1.2; duration: 1000; easing.type: Easing.InOutQuad }}
            NumberAnimation {{ from: 1.2; to: 1.0; duration: 1000; easing.type: Easing.InOutQuad }}
        }}
    }}

    // Diagnostic HUD
    Column {{
        anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 40
        spacing: 5
        Text {{ text: "RZ EMULATOR - D3D11 (CLEAN)"; color: "#00ffcc"; font.pixelSize: 32; font.bold: true }}
        Text {{ text: "3DMigoto Hook: Auto"; color: "white"; font.pixelSize: 18 }}
        Text {{ text: "Resolution: " + parent.parent.width + "x" + parent.parent.height; color: "#aaa"; font.pixelSize: 16 }}
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
    
    target_size = QSize(args.width, args.height)
    view.setMinimumSize(target_size)
    
    if args.fullscreen:
        view.showFullScreen()
    else:
        view.resize(target_size)
        view.show()
    
    view.setSource(QUrl.fromLocalFile(qml_file))
    
    res = app.exec()
    if os.path.exists(qml_file): 
        try: os.remove(qml_file)
        except: pass
    sys.exit(res)
