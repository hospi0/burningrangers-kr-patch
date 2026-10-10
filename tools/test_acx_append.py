# -*- coding: utf-8 -*-
"""시험 2: ADX.ACX 전체 다시 쌓기 — 모든 클립 «데이터 시작 = HDR 바이트»(머리 속 0) → Track 1 맨 뒤에 덧붙이고
   ISO 디렉터리(위치·크기)·볼륨 크기만 고친다. 다른 파일은 안 움직인다. (2026-10-09)
   → F:\\hospi\\roms\\ss roms\\Burning Rangers (Japan)\\ 에 덮어씀"""
import os, shutil, struct, sys
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cdmode1
SRC = r'C:\claude\roms\ss\Burning Rangers (Japan)\Burning Rangers (Japan)'
BASE = 'Burning Rangers (Japan)'
OUT = r'F:\hospi\roms\ss roms\Burning Rangers (Japan)'
HDR = 2048   # 시험 2: 6144 는 잡음(실기) → 첫 섹터 안까지만


def bcd(v):
    return (v // 10) << 4 | v % 10


def new_sector(lba, data):
    m = lba + 150
    s = bytearray(2352)
    s[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'
    s[12:16] = bytes([bcd(m // 4500), bcd(m // 75 % 60), bcd(m % 75), 1])
    s[16:2064] = data.ljust(2048, b'\0')
    return cdmode1.fix(s)


# --- 1) ACX 다시 쌓기 ---------------------------------------------------
acx = open(os.path.join(ROOT, 'work', 'iso', 'ADX.ACX'), 'rb').read()
n = struct.unpack_from('>I', acx, 4)[0]
E = [struct.unpack_from('>II', acx, 8 + 8 * i) for i in range(n)]
first = E[0][0]
out = bytearray(first); ents = []
for o, s in E:
    clip = acx[o:o + s]; off = struct.unpack_from('>H', clip, 2)[0]
    assert clip[off - 2:off + 4] == b'(c)CRI'
    pad = HDR - (off + 4); assert pad >= 0
    c = bytearray(clip[:off - 2] + bytes(pad) + clip[off - 2:]); struct.pack_into('>H', c, 2, off + pad)
    ents.append((len(out), len(c))); out += c
    out += bytes(-len(out) % 2048)
struct.pack_into('>II', out, 0, 0, n)
for i, (o, s) in enumerate(ents):
    struct.pack_into('>II', out, 8 + 8 * i, o, s)
out[8 + 8 * n:first] = acx[8 + 8 * n:first]
print('새 ADX.ACX %d B (원본 %d, +%.1f MB)' % (len(out), len(acx), (len(out) - len(acx)) / 1e6))

# --- 2) 트랙 복사 + 덧붙이기 --------------------------------------------
os.makedirs(OUT, exist_ok=True)
t1 = os.path.join(OUT, BASE + ' (Track 1).bin')
shutil.copyfile(os.path.join(SRC, BASE + ' (Track 1).bin'), t1)
for f in (BASE + ' (Track 2).bin', BASE + '.cue'):
    d = os.path.join(OUT, f)
    if not os.path.exists(d) or os.path.getsize(d) != os.path.getsize(os.path.join(SRC, f)):
        shutil.copyfile(os.path.join(SRC, f), d)
f = open(t1, 'r+b')
f.seek(0, 2); nsec0 = f.tell() // 2352; new_lba = nsec0
for k in range(0, len(out), 2048):
    f.write(new_sector(new_lba + k // 2048, out[k:k + 2048]))
total = f.tell() // 2352
print('덧붙임 LBA %d‥%d (트랙 %d → %d 섹터)' % (new_lba, total - 1, nsec0, total))


def rsec(lba):
    f.seek(lba * 2352); return bytearray(f.read(2352))


def wsec(lba, s):
    cdmode1.fix(s); f.seek(lba * 2352); f.write(s)


# --- 3) ISO: 디렉터리 레코드·볼륨 크기 ---------------------------------
pvd = rsec(16)
struct.pack_into('<I', pvd, 16 + 80, total); struct.pack_into('>I', pvd, 16 + 84, total)
wsec(16, pvd)
rl = struct.unpack_from('<I', pvd, 16 + 156 + 2)[0]; rs = struct.unpack_from('<I', pvd, 16 + 156 + 10)[0]
done = False
for k in range((rs + 2047) // 2048):
    s = rsec(rl + k); i = 16
    while i < 16 + 2048 and s[i]:
        ln = s[i]; nl = s[i + 32]; name = bytes(s[i + 33:i + 33 + nl])
        if name.split(b';')[0] == b'ADX.ACX':
            struct.pack_into('<I', s, i + 2, new_lba); struct.pack_into('>I', s, i + 6, new_lba)
            struct.pack_into('<I', s, i + 10, len(out)); struct.pack_into('>I', s, i + 14, len(out))
            wsec(rl + k, s); done = True
        i += ln
assert done, 'ADX.ACX 디렉터리 레코드 못 찾음'
f.close()
print('디렉터리 고침 → ', OUT)
