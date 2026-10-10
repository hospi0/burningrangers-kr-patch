# -*- coding: utf-8 -*-
"""튜토리얼 대원 소개 카드 이름 한글화 (2026-10-10) — TXTRDATA.BIN(PRS) 안 144×80 8bpp 카드 5장(쇼·티리스·리드·빅·크리스)
   «NAME:» 뒤(x 37‥143, y 63‥79)를 바탕색(1)으로 지우고 나눔고딕 11px 안티앨리어싱(원본 회색 팔레트)으로 이름을 쓴다.
   python tools/cards.py         → 미리보기 work/cards_pv.png
   python tools/cards.py --pack  → work/TXTRDATA_kr.BIN (PRS)"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import prs

LBA, SIZE = 7270, 34273
FIRST, STEP, CW, CH = 2544, 11520, 144, 80
NAMES = ['쇼 아마바네', '티리스', '리드 피닉스', '빅 랜드맨', '크리스 파튼']   # 카드 순서(번호 07·06·05·03·01)
X0, Y0 = 37, 64; TX, INK_BOT = 39, 76   # ★아랫선 = «NAME:»·가타카나 76행 · 63행은 초상화 맨 아랫줄(지우지 말 것) — 사용자 «높다·초상화 침범» 2026-10-10
BG = 1
FONT = ImageFont.truetype(r'C:\claude\utils\font\nanum-gothic\NanumGothicBold.ttf', 10)   # 사용자 선택(10px Bold, 68‥76행) 2026-10-10
GRAYS = [(1, 0), (40, 32), (81, 56), (95, 64), (122, 80), (148, 96), (162, 104), (173, 112), (182, 120), (189, 128), (193, 136),
         (200, 144), (204, 152), (216, 168), (222, 176), (227, 184), (242, 216), (255, 248)]   # 원본 글자가 쓰는 순회색 (번호, 밝기) — ★안티앨리어싱 필수(«안티 없어 튄다»)


def src():
    d = open(os.path.join(ROOT, 'work', 'track1_user.bin'), 'rb').read()[LBA * 2048:LBA * 2048 + SIZE]
    return prs.decompress(d)[0]


def shift():
    """기준 글자열의 잉크(옅은 안티 포함) 아랫선을 INK_BOT 에 맞추는 세로 이동량"""
    im = Image.new('L', (CW, CH), 0); ImageDraw.Draw(im).text((TX, 60), '가각간갈감갑강개', font=FONT, fill=255)
    return INK_BOT - np.where(np.array(im).max(1) > 12)[0][-1]


def build():
    o = bytearray(src())
    for k, nm in enumerate(NAMES):
        s = FIRST + k * STEP
        a = np.frombuffer(bytes(o[s:s + CW * CH]), np.uint8).reshape(CH, CW).copy()
        a[Y0:, X0:] = BG
        im = Image.new('L', (CW, CH), 0); dr = ImageDraw.Draw(im)
        dr.text((TX, 60), nm, font=FONT, fill=255)
        g = np.array(im).astype(int)
        g = np.roll(g, shift(), 0)                                       # 모든 이름 같은 아랫선(76행)
        rows = np.where(g.max(1) > 12)[0]
        assert rows[-1] <= INK_BOT and not g[:Y0].any() and not g[:, CW - 1].any(), ('이름이 칸을 넘음', nm, rows)
        lv = np.array([b for _, b in GRAYS]); ix = np.array([i for i, _ in GRAYS])
        sel = g > 12
        a[sel] = ix[np.abs(g[sel][:, None] * 248 / 255 - lv[None, :]).argmin(1)]
        o[s:s + CW * CH] = a.tobytes()
    return bytes(o)


def preview(o):
    c = open(os.path.join(ROOT, 'work', 'mem', 'p2', 'CRAM.bin'), 'rb').read(); c = bytes(x for i in range(0, len(c), 2) for x in (c[i + 1], c[i]))
    cr = np.frombuffer(c, '>u2').astype(int); pal = np.stack([(cr & 31) << 3, ((cr >> 5) & 31) << 3, ((cr >> 10) & 31) << 3], -1).astype(np.uint8)
    W = Image.new('RGB', (CW, CH * 5))
    for k in range(5):
        s = FIRST + k * STEP; a = np.frombuffer(o[s:s + CW * CH], np.uint8).reshape(CH, CW).astype(int)
        W.paste(Image.fromarray(pal[(0x200 + a) & 0x7FF]), (0, CH * k))
    W.resize((CW * 3, CH * 15), Image.NEAREST).save(os.path.join(ROOT, 'work', 'cards_pv.png'))


if __name__ == '__main__':
    o = build(); preview(o)
    if '--pack' in sys.argv:
        c = prs.compress(o); assert prs.decompress(c)[0] == o
        open(os.path.join(ROOT, 'work', 'TXTRDATA_kr.BIN'), 'wb').write(c)
        print('압축 %d B (원본 %d, 자리 %d)' % (len(c), SIZE, (SIZE + 2047) // 2048 * 2048))
