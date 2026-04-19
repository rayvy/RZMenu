import struct
import math
from dataclasses import dataclass, field
from typing import Optional, List, Dict

@dataclass
class RZBone:
    name: str
    parent_name: Optional[str] = None
    pos: tuple = (0.0, 0.0)      # Local rest position
    rot: float = 0.0             # Local rotation (radians)
    scale: tuple = (1.0, 1.0)    # Local scale
    pivot: tuple = (0.0, 0.0)    # Pivot relative to bone start

    # Runtime calculated values
    parent_id: int = -1
    world_pos: tuple = (0.0, 0.0)
    world_rot: float = 0.0
    world_scale: tuple = (1.0, 1.0)

class RZSkeleton:
    def __init__(self):
        self.bones: List[RZBone] = []
        self._name_to_idx: Dict[str, int] = {}

    def add_bone(self, bone: RZBone):
        self._name_to_idx[bone.name] = len(self.bones)
        self.bones.append(bone)

    def build(self):
        """Resolves parent hierarchy and computes world rest matrices."""
        for bone in self.bones:
            bone.parent_id = self._name_to_idx.get(bone.parent_name, -1) if bone.parent_name else -1
        
        self._compute_world_transforms()

    def _compute_world_transforms(self):
        """
        Computes world transforms for the rest pose. 
        Uses a simple iterative approach assuming parents are added before children, 
        or correctly topological sorting would be better.
        """
        # For simplicity in this initial version, we assume basic hierarchy.
        # RZMenu bones are usually defined in order.
        for bone in self.bones:
            if bone.parent_id == -1:
                bone.world_pos = bone.pos
                bone.world_rot = bone.rot
                bone.world_scale = bone.scale
            else:
                parent = self.bones[bone.parent_id]
                
                # Apply parent rotation/scale to local position
                pr, ps = parent.world_rot, parent.world_scale
                lx = bone.pos[0] * ps[0]
                ly = bone.pos[1] * ps[1]
                
                cos_pr = math.cos(pr)
                sin_pr = math.sin(pr)
                
                rotated_x = lx * cos_pr - ly * sin_pr
                rotated_y = lx * sin_pr + ly * cos_pr
                
                bone.world_pos = (parent.world_pos[0] + rotated_x, parent.world_pos[1] + rotated_y)
                bone.world_rot = parent.world_rot + bone.rot
                bone.world_scale = (parent.world_scale[0] * bone.scale[0], parent.world_scale[1] * bone.scale[1])

    def to_binary(self) -> bytes:
        """
        Exports the skeleton to BoneBuffer format (2x float4 per bone).
        Format:
        [0] = (local_pos.x, local_pos.y, local_rot, local_scale)
        [1] = (parent_id, flags, pad, pad)
        """
        # Resolve parent IDs but don't compute world transforms here (CS will do it)
        for bone in self.bones:
            bone.parent_id = self._name_to_idx.get(bone.parent_name, -1) if bone.parent_name else -1

        data = bytearray()
        for b in self.bones:
            # float4[0]
            data += struct.pack('4f', b.pos[0], b.pos[1], b.rot, b.scale[0])
            # float4[1]
            data += struct.pack('f f f f', float(b.parent_id), 0.0, 0.0, 0.0)
            
        return bytes(data)
