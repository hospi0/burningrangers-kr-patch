# -*- coding: utf-8 -*-
"""부팅 로딩 화면 안내문 한글화 (2026-10-10) — LOADDATA.BIN(PRS) 안 화면 하나(지도 0x33064 · 셀 0x35064)
   원본 글자를 줄 배경(x=351 열의 색)으로 지우고 → 한글을 흰 글자 + 남색 테두리로 오른쪽 맞춤 → 16×16 칸으로 다시 잘라
   중복 제거(188칸 안) → 지도·셀 제자리 → PRS 다시 압축. 미리보기 work/loadscreen_pv.png
   python tools/loadscreen.py           → work/LOADDATA_kr.BIN + 미리보기"""
import os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import prs

MAP, CELL, NCELL = 0x33064, 0x35064, 0xBC00          # 풀린 LOADDATA 안 이 화면의 지도·셀(0x60000‥0x6BC00 로 감)
W, H = 352, 224                                       # 22×14 칸
LINES = ['이 게임은', '음성을 이용한', '내비게이션 시스템을', '채용하고 있습니다.', '음성이 들리는 상태에서', '즐겨 주세요.']
TOPS = [48, 71, 93, 115, 138, 160]                    # 원본 줄의 흰 글자 윗선(밑선 +13)
RIGHT = 335                                           # 원본 흰 글자 오른쪽 끝
ERASE = [(44, 66, 205), (67, 88, 230), (89, 111, 133), (111, 133, 205), (134, 156, 162), (156, 178, 188)]  # 지울 상자 y0,y1,x0
KEEP = lambda x, y: x < 166 and y >= 141              # «NOW LOADING…» 글자(지우지 말 것)
FONT = ImageFont.truetype(r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf', 16 * 4)
CRAM_BANK = 3                                         # 지도 0x3C00 → 팔레트 뱅크 3


def palette():
    c = open(os.path.join(ROOT, 'work', 'mem', 'load', 'CRAM.bin'), 'rb').read()
    c = bytes(b for i in range(0, len(c), 2) for b in (c[i + 1], c[i]))
    cr = np.frombuffer(c, '>u2').astype(int)[CRAM_BANK * 256:CRAM_BANK * 256 + 256]
    return np.stack([(cr & 31) << 3, ((cr >> 5) & 31) << 3, ((cr >> 10) & 31) << 3], -1)


def to_index(o):
    mp = struct.unpack('>1024H', o[MAP:MAP + 0x800]); idx = np.zeros((H, W), np.uint8)
    for ty in range(H // 16):
        for tx in range(W // 16):
            t = (mp[ty * 32 + tx] & 0xFFF) * 0x80
            for k in range(4):
                c = np.frombuffer(o[CELL + t + k * 64:CELL + t + k * 64 + 64], np.uint8).reshape(8, 8)
                idx[ty * 16 + (k >> 1) * 8:ty * 16 + (k >> 1) * 8 + 8, tx * 16 + (k & 1) * 8:tx * 16 + (k & 1) * 8 + 8] = c
    return idx, mp


def text_layer():
    """4배로 그려 줄여서 글자·테두리 덮임(0‥1)"""
    S = 4; fill = Image.new('L', (W * S, H * S), 0); dr = ImageDraw.Draw(fill)
    for s, top in zip(LINES, TOPS):
        bb = dr.textbbox((0, 0), s, font=FONT)
        x = RIGHT * S - (bb[2] - bb[0]) - bb[0]; y = top * S - bb[1] - S // 2
        dr.text((x, y), s, font=FONT, fill=255)
    f = np.array(fill.resize((W, H), Image.LANCZOS)).astype(float) / 255
    f = np.clip(f * 1.15, 0, 1)
    o = np.zeros_like(f)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            if dx * dx + dy * dy <= 5: o = np.maximum(o, np.roll(np.roll(f, dy, 0), dx, 1))
    return f, np.clip(o * 1.3, 0, 1)


def build():
    src = open(os.path.join(ROOT, 'work', 'iso', 'LOADDATA.BIN'), 'rb').read()
    o, _ = prs.decompress(src); o = bytearray(o)
    pal = palette(); idx, mp = to_index(o)
    rgb = pal[idx].astype(float)
    for y0, y1, x0 in ERASE:                          # 원본 글자 지우기
        for y in range(y0, y1):
            bg = rgb[y, 351].copy()
            for x in range(x0, W):
                p = rgb[y, x]
                textlike = p.min() >= 150 or (p[0] <= 16 and 8 <= p[1] <= 32 and 72 <= p[2] <= 104)   # 흰 글자·남색 테두리
                if not KEEP(x, y) or textlike: rgb[y, x] = bg
    f, ol = text_layer()
    WHITE = np.array([248, 248, 248.]); NAVY = np.array([0, 16, 88.])
    a = ol[..., None]; rgb = rgb * (1 - a) + NAVY * a
    a = f[..., None]; rgb = rgb * (1 - a) + WHITE * a
    d = ((rgb[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(-1); new = d.argmin(-1).astype(np.uint8)
    Image.fromarray(pal[new].astype(np.uint8)).resize((W * 3, H * 3), Image.NEAREST).save(os.path.join(ROOT, 'work', 'loadscreen_pv.png'))
    # 다시 자르기: 칸 0 = 원본 칸 0(바깥 지도도 이걸 가리킴)
    tiles = [bytes(o[CELL:CELL + 0x100])]; look = {tiles[0]: 0}; newmap = list(mp)
    for ty in range(H // 16):
        for tx in range(W // 16):
            blk = new[ty * 16:ty * 16 + 16, tx * 16:tx * 16 + 16]
            b = b''.join(blk[(k >> 1) * 8:(k >> 1) * 8 + 8, (k & 1) * 8:(k & 1) * 8 + 8].tobytes() for k in range(4))
            if b not in look: look[b] = len(tiles); tiles.append(b)
            newmap[ty * 32 + tx] = (mp[ty * 32 + tx] & 0xF000) | look[b] * 2
    print('칸 %d / %d' % (len(tiles), NCELL // 0x100))
    assert len(tiles) * 0x100 <= NCELL, '칸이 넘침'
    o[MAP:MAP + 0x800] = struct.pack('>1024H', *newmap)
    o[CELL:CELL + NCELL] = b''.join(tiles).ljust(NCELL, b'\0')
    chk, _ = to_index(bytes(o)); assert (chk == new).all()
    return bytes(o), src


if __name__ == '__main__':
    o, src = build()
    if '--pack' in sys.argv:
        c = prs.compress(o); assert prs.decompress(c)[0] == o
        open(os.path.join(ROOT, 'work', 'LOADDATA_kr.BIN'), 'wb').write(c)
        print('압축 %d B (원본 %d B, 자리 %d B)' % (len(c), len(src), (len(src) + 2047) // 2048 * 2048))
