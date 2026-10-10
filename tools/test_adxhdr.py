# -*- coding: utf-8 -*-
"""시험: ADX 머리를 늘려도 게임이 정상 재생하는가 (2026-10-09)
   트레이닝 첫 대사 0861(+360)·0862(+1014)·0863(+452) 머리에 0 을 끼우고
   «데이터까지 거리»(u16 @2)·ACX 표 크기를 고친다. 각 클립 끝의 정렬 여유 안이라 ADX.ACX 크기·다른 클립 위치는 그대로.
   → F:\\hospi\\roms\\ss roms\\Burning Rangers (Japan) 시험_adx머리\\ (cue + 트랙 1·2)"""
import os, shutil, struct, sys
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cdmode1
SRC = r'C:\claude\roms\ss\Burning Rangers (Japan)\Burning Rangers (Japan)'
BASE = 'Burning Rangers (Japan)'
OUT = r'F:\hospi\roms\ss roms\Burning Rangers (Japan)'   # 시험판도 원래 폴더에 덮어씀(사용자 2026-10-09)
ACX_LBA, ACX_SIZE = 9712, 80119808
PAD = {861: 360, 862: 1014, 863: 452}   # 트레이닝 첫 대사 3개(사용자 «게임 시작하면 나오는 트레이닝부터»), 정렬 여유 끝까지

acx = bytearray(open(os.path.join(ROOT, 'work', 'iso', 'ADX.ACX'), 'rb').read())
assert len(acx) == ACX_SIZE
n = struct.unpack_from('>I', acx, 4)[0]
E = [list(struct.unpack_from('>II', acx, 8 + 8 * i)) for i in range(n)]
for i, pad in PAD.items():
    o, s = E[i]; nxt = E[i + 1][0]
    assert nxt - o - s >= pad, (i, nxt - o - s)
    clip = bytes(acx[o:o + s]); off = struct.unpack_from('>H', clip, 2)[0]
    assert clip[:2] == b'\x80\x00' and clip[off - 2:off + 4] == b'(c)CRI'
    new = bytearray(clip[:off - 2] + bytes(pad) + clip[off - 2:])        # «(c)CRI» 앞에 0 채움 → 데이터가 pad 만큼 뒤로
    struct.pack_into('>H', new, 2, off + pad)
    acx[o:o + len(new)] = new
    acx[o + len(new):nxt] = bytes(nxt - o - len(new))
    struct.pack_into('>I', acx, 8 + 8 * i + 4, len(new))
    print('클립 %04d 머리 %d → %d B, 크기 %d → %d' % (i, off + 4, off + 4 + pad, s, len(new)))

os.makedirs(OUT, exist_ok=True)
for t in (1, 2):
    s = os.path.join(SRC, '%s (Track %d).bin' % (BASE, t)); d = os.path.join(OUT, os.path.basename(s))
    if not os.path.exists(d) or os.path.getsize(d) != os.path.getsize(s) or t == 1:
        shutil.copyfile(s, d)
shutil.copyfile(os.path.join(SRC, BASE + '.cue'), os.path.join(OUT, BASE + '.cue'))
orig = open(os.path.join(ROOT, 'work', 'iso', 'ADX.ACX'), 'rb').read()
f = open(os.path.join(OUT, BASE + ' (Track 1).bin'), 'r+b'); nsec = 0
for k in range(0, ACX_SIZE, 2048):
    if acx[k:k + 2048] == orig[k:k + 2048]:
        continue
    lba = ACX_LBA + k // 2048
    f.seek(lba * 2352); sec = bytearray(f.read(2352))
    sec[16:2064] = acx[k:k + 2048].ljust(2048, b'\0')
    cdmode1.fix(sec)
    f.seek(lba * 2352); f.write(sec); nsec += 1
f.close()
print('섹터 %d개 고침 → %s' % (nsec, OUT))
