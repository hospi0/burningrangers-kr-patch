# -*- coding: utf-8 -*-
"""메일 반각 띄어쓰기 그리기 검산 (2026-10-10) — SH-2 흉내기로
   ① 공백 없는 문자열: 원래 그리기(원본 모듈)와 새 그리기(패치 모듈)의 VRAM 이 바이트까지 같은지 (일반·반전 둘 다)
   ② 반각 공백 섞인 메일: 타일을 화소로 풀어 «파이썬 기준 그림»(글자 x = 반 칸×8px)과 같은지
   ★둘 다 r1·r9‥r15 보존 검사(원래 그리기가 r1 을 안 건드려서 호출자가 r1 = 작업 구조체로 씀)
   python tools/test_mailhalf.py"""
import os, struct, sys
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import mail as M, prs, sh2sim as S

orig = prs.decompress(M.disc(M.MAIL_LBA, M.MAIL_SIZE))[0]
o, font, enc, code, errs = M.build()
STOP = 0xDEAD0000


def run(mod, entry, s, col=0, row=0):
    m = S.Mem()
    m.add(M.BASE, 0x18000, mod)
    m.add(0x00200000, 0x20000, font)
    vram = m.add(M.VRAM0, 0x20000)
    m.add(0x060F0000, 0x10000)
    m.add(0x06070000, 0x1000, s + b'\0')          # 문자열
    regs = [0, 0x0D801000, 0, 0, col, row, 0x06070000, 0] + [0x1111 * k for k in range(8, 15)] + [0x060FF000]
    r, n = S.run(m, entry, regs=regs, stop=STOP)
    return bytes(vram), r, n


def pixels(vram, rows=11):
    """타일(16×16, TL TR BL BR 셀 4비트) → 화소 [rows×16, 512]"""
    im = np.zeros((rows * 16, 512), np.uint8)
    for ty in range(rows):
        for tx in range(32):
            base = ty * 0x1000 + tx * 128
            for ci, (cx, cy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
                for y in range(8):
                    w = struct.unpack_from('>I', vram, base + ci * 32 + y * 4)[0]
                    for x in range(8):
                        im[ty * 16 + cy + y, tx * 16 + cx + x] = w >> (28 - 4 * x) & 15
    return im


def reference(b, inv=False, rows=11):
    im = np.zeros((rows * 16, 512), np.uint8); x = y = 0; i = 0
    while i < len(b):
        if b[i] == 0x20: x += 8; i += 1; continue
        if b[i] < 0x81: y += 1; x = 0; i += 1; continue
        g = M.fidx(b[i] << 8 | b[i + 1]); i += 2
        for r, v in enumerate(struct.unpack('>16H', font[g * 32:g * 32 + 32])):
            if inv: v ^= 0xFFFF
            for cx in range(16):
                im[y * 16 + r, x + cx] = 1 if v >> (15 - cx) & 1 else 0
        x += 16
    return im


bad = 0
# ① 공백 없는 문자열 — 원래와 같아야 함
for nm, ent in (('일반', M.DRAW), ('반전', M.DRAWINV)):
    for k in (0, 5, 77, 182):
        s = orig[struct.unpack_from('>I', orig, M.TAB + 4 * k)[0] - M.BASE:]
        s = s[:s.index(b'\0')]
        for col, row in ((0, 0), (3, 2)):
            a, _, n1 = run(orig, ent, s, col, row); b, r, n2 = run(o, ent, s, col, row)
            ok = a == b and r[1] == 0x0D801000 and r[9:16] == [0x1111 * k for k in range(9, 15)] + [0x060FF000]
            bad += not ok
            print('%s ① %s 원문 메일 %03d (%d,%d) 명령 %d→%d' % ('✓' if ok else '✗', nm, k, col, row, n1, n2))
# ② 반각 공백 섞인 번역 메일
for nm, ent, inv in (('일반', M.DRAW, False), ('반전', M.DRAWINV, True)):
    for k in (0, 5, 144, 147, 182):
        s = enc[k]
        v, r, n = run(o, ent, s)
        got = pixels(v); ref = reference(s, inv)
        if inv:   # 반전은 글자 칸 안에서만 비교(빈 곳은 0)
            mask = reference(s, False) | reference(s, True); got = got * (mask > 0)
        ok = np.array_equal(got, ref) and r[1] == 0x0D801000 and r[9:16] == [0x1111 * k for k in range(9, 15)] + [0x060FF000]
        bad += not ok
        print('%s ② %s 번역 메일 %03d 공백 %d개 명령 %d' % ('✓' if ok else '✗', nm, k, s.count(b' '), n))
        if not ok:
            d = np.argwhere(got != ref); print('   다른 화소 %d개 첫 %s' % (len(d), d[:3].tolist()))
print('틀림 %d' % bad)
