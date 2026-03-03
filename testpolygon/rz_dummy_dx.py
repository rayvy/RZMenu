import sys
import os
import argparse
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtCore import QUrl, QSize

# --- D3D11 FORCING ---
os.environ["QSG_RHI_BACKEND"] = "d3d11"
os.environ["QSG_RENDER_LOOP"] = "basic" 
os.environ["QSG_INFO"] = "1"
os.environ["QSG_D3D11_WINDOW_BACK_BUFFER_COUNT"] = "2"
os.environ["QSG_NO_PARTIAL_UPDATE"] = "1" # Чтобы Scissor всегда был на весь экран

# --- ASSET PATHS ---
EXE_DIR = os.path.dirname(os.path.abspath(__file__))
BG_PATH = os.path.join(EXE_DIR, "windowsxp.png").replace("\\", "/")
if not os.path.exists(BG_PATH):
    BG_PATH = os.path.join(EXE_DIR, "..", "windowsxp.png").replace("\\", "/")

# --- ARGUMENT PARSING ---
parser = argparse.ArgumentParser(description="RZMenu Dummy DirectX 11 App")
parser.add_argument("--width", type=int, default=2560)
parser.add_argument("--height", type=int, default=1080)
parser.add_argument("--fullscreen", action="store_true")
args, unknown = parser.parse_known_args()

QML_DATA = f"""
import QtQuick 2.15

Rectangle {{
    id: window
    width: {args.width}
    height: {args.height}
    color: "#050610" 
    
    focus: true 

    Keys.onPressed: (event) => {{
        if (event.key === Qt.Key_Z) {{
            migotoAnchor.visible = !migotoAnchor.visible;
            event.accepted = true;
        }}
    }}

    // Обычный фон
    Image {{
        anchors.fill: parent
        source: "file:///{BG_PATH}" 
        fillMode: Image.PreserveAspectCrop
        opacity: 0.2
    }}

    // Спиннер (без radius, чтобы не триггерить трафареты)
    Rectangle {{
        id: spinner
        width: 100; height: 100
        color: "#00ffcc"
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

    Column {{
        anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 40
        spacing: 5
        Text {{ text: "RZ EMULATOR - D3D11"; color: "#00ffcc"; font.pixelSize: 32; font.bold: true }}
        Text {{ text: "3DMigoto Hook: Auto"; color: "white"; font.pixelSize: 18 }}
        Text {{ text: "Press 'Z' to toggle Dummy Quad"; color: "#ffcc00"; font.pixelSize: 24; font.bold: true }}
    }}

    // =======================================================
    // DUMMY QUAD (ЯКОРЬ ДЛЯ 3DMIGOTO)
    // =======================================================
    Image {{
        id: migotoAnchor
        anchors.fill: parent
        source: "file:///{BG_PATH}" 
        fillMode: Image.Stretch
        mirror: true  // Отзеркален, чтобы ты мог визуально понять, что это он
        visible: true
        opacity: 0.8  // Сделал поярче, чтобы текстура гарантированно прошла оптимизации
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