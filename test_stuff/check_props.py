import struct
import os

def analyze(p):
    print(f"--- {p} ---")
    if not os.path.exists(p):
        print("Not found")
        return
    with open(p, 'rb') as f:
        f.seek(8)
        while True:
            try:
                l_raw = f.read(4)
                if not l_raw: break
                l = struct.unpack('>I', l_raw)[0]
                t = f.read(4)
                d = f.read(l)
                f.read(4) # crc
                if t == b'sRGB':
                    print(f"sRGB intent: {struct.unpack('>B', d)[0]}")
                elif t == b'gAMA':
                    print(f"gAMA: {struct.unpack('>I', d)[0]}")
                elif t == b'tEXt':
                    print(f"tEXt: {d[:50]}...")
                elif t == b'eXIf':
                    print(f"eXIf: {d[:50].hex()}...")
                    if b'ColorSpace' in d or b'icc' in d.lower():
                        print("Found color related string in EXIF")
            except:
                break

analyze('iconsLinearBeforePaintNet.png')
analyze('iconsLinearAfterPaintNet.png')
analyze('iconsSRGB.png')
analyze('iconsLINEAR.png')
