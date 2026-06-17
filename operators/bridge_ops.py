import bpy

from ..utils import bridge_client


class RZM_OT_BridgeConnect(bpy.types.Operator):
    bl_idname = "rzm.bridge_connect"
    bl_label = "Bridge Connect"
    bl_options = {'REGISTER'}

    host: bpy.props.StringProperty(name="Host", default="127.0.0.1")
    port: bpy.props.IntProperty(name="Port", default=39393, min=1, max=65535)

    def execute(self, context):
        try:
            bridge_client.connect(self.host, self.port)
        except Exception as exc:
            self.report({'ERROR'}, f"Bridge connect failed: {exc}")
            print(f"[RZM Bridge] connect failed: {exc}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Bridge connected to {self.host}:{self.port}")
        print(f"[RZM Bridge] connected to {self.host}:{self.port}")
        return {'FINISHED'}


class RZM_OT_BridgePing(bpy.types.Operator):
    bl_idname = "rzm.bridge_ping"
    bl_label = "Bridge Ping"
    bl_options = {'REGISTER'}

    message: bpy.props.StringProperty(name="Message", default="Ping from Blender")

    def execute(self, context):
        if not bridge_client.send_signal(self.message):
            self.report({'ERROR'}, "Bridge is not connected")
            return {'CANCELLED'}

        print(f"[RZM Bridge] ping sent: {self.message}")
        return {'FINISHED'}


class RZM_OT_BridgeDisconnect(bpy.types.Operator):
    bl_idname = "rzm.bridge_disconnect"
    bl_label = "Bridge Disconnect"
    bl_options = {'REGISTER'}

    def execute(self, context):
        bridge_client.disconnect()
        print("[RZM Bridge] disconnected")
        return {'FINISHED'}


classes_to_register = [
    RZM_OT_BridgeConnect,
    RZM_OT_BridgePing,
    RZM_OT_BridgeDisconnect,
]


def unregister_menus():
    bridge_client.disconnect()

