import struct
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class RZKeyframe:
    time: float
    pos: tuple = (0.0, 0.0)
    rot: float = 0.0
    scale: tuple = (1.0, 1.0)
    easing: str = 'LINEAR'
    # For bezier
    cp: tuple = (0.25, 0.25, 0.75, 0.75) 

@dataclass
class RZBoneTrack:
    bone_name: str
    bone_index: int = -1
    keyframes: List[RZKeyframe] = field(default_factory=list)

@dataclass
class RZAnimation:
    name: str
    duration: float = 2.0
    loop: bool = True
    tracks: Dict[str, RZBoneTrack] = field(default_factory=dict)

class RZAnimationSystem:
    def __init__(self):
        self.animations: Dict[str, RZAnimation] = {}

    def add_animation(self, anim: RZAnimation):
        self.animations[anim.name] = anim

    def to_binary(self, skeleton_bone_names: List[str]) -> bytes:
        """
        Exports all animations to a binary format.
        Header:
          uint32: num_animations
        
        Per Animation:
          char[64]: name
          float32: duration
          uint32: loop
          uint32: num_tracks
          
          Per Track:
            uint32: bone_index
            uint32: num_keyframes
            
            Per Keyframe:
              float32: time
              float4:  pos.x, pos.y, rot, padding
              float4:  scale.x, scale.y, easing_type, padding
              float4:  cp1x, cp1y, cp2x, cp2y (bezier)
        """
        name_to_idx = {name: i for i, name in enumerate(skeleton_bone_names)}
        
        buf = bytearray()
        buf += struct.pack('I', len(self.animations))
        
        for name, anim in self.animations.items():
            # char[64]
            name_bytes = name.encode('utf-8')[:63].ljust(64, b'\0')
            buf += name_bytes
            buf += struct.pack('f I I', anim.duration, 1 if anim.loop else 0, len(anim.tracks))
            
            for b_name, track in anim.tracks.items():
                b_idx = name_to_idx.get(b_name, -1)
                buf += struct.pack('I I', b_idx, len(track.keyframes))
                
                for kf in track.keyframes:
                    easing_id = 0 # LINEAR
                    if kf.easing == 'EASE': easing_id = 1
                    elif kf.easing == 'BEZIER': easing_id = 2
                    
                    buf += struct.pack('f', kf.time)
                    buf += struct.pack('4f', kf.pos[0], kf.pos[1], kf.rot, 0.0)
                    buf += struct.pack('4f', kf.scale[0], kf.scale[1], float(easing_id), 0.0)
                    buf += struct.pack('4f', kf.cp[0], kf.cp[1], kf.cp[2], kf.cp[3])
                    
        return bytes(buf)
