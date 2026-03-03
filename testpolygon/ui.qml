
import QtQuick 2.15
import QtQuick.Controls 2.15

Rectangle {
    id: root
    width: 1280
    height: 720
    color: "#050510"

    // Background
    Image {
        anchors.fill: parent
        source: "file:///windowsxp.png"
        fillMode: Image.PreserveAspectCrop
        opacity: 0.4
    }

    // "3D" Rotating Cube Simulation
    Rectangle {
        id: cube
        width: 300; height: 300
        anchors.centerIn: parent
        color: "transparent"
        
        // Face 1
        Rectangle {
            width: 250; height: 250
            anchors.centerIn: parent
            color: Qt.rgba(0, 1, 0.8, 0.2)
            border.color: "#00ffcc"
            border.width: 4
            antialiasing: true
            
            Text {
                anchors.centerIn: parent
                text: "RZ"
                color: "#00ffcc"
                font.pixelSize: 100
                font.bold: true
            }
        }

        transform: [
            Rotation { id: rotY; axis { x: 0; y: 1; z: 0 }; origin.x: 150; origin.y: 150 },
            Rotation { id: rotX; axis { x: 1; y: 0; z: 0 }; origin.x: 150; origin.y: 150 }
        ]

        NumberAnimation on transform {
            target: rotY; property: "angle"; from: 0; to: 360; duration: 3000; loops: Animation.Infinite
        }
        NumberAnimation on transform {
            target: rotX; property: "angle"; from: 0; to: 360; duration: 5000; loops: Animation.Infinite
        }
    }

    // Diagnostic Panel
    Column {
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 40
        spacing: 5
        Text { text: "D3D11 RHI STABLE"; color: "#00ffcc"; font.pixelSize: 32; font.bold: true }
        Text { text: "API: " + GraphicsInfo.api; color: "white"; font.pixelSize: 18 }
        Text { id: statusLabel; text: "Status: Waiting for hook..."; color: "yellow"; font.pixelSize: 18 }
    }

    function setStatus(s, c) {
        statusLabel.text = "Status: " + s
        statusLabel.color = c
    }
}
