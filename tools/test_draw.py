# -*- coding: utf-8 -*-
"""훅 draw 검산 — SH-2 흉내기로 쪽을 그려 glyphpack.reference() 와 셀·지도·팔레트 비교. python tools/test_draw.py [글…]"""
import os, random, struct, sys
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import build as B, glyphpack as G, sh2sim as S

code, lab = B.hooks()
tests = sys.argv[1:] or ['아직 훈련 중이야, 쇼. 긴장 풀지 말고 끝까지 따라와!', '좋아!', 'Wg%… 「확인」 12,345?',
                        'ABCDEFGHIJKLMNOPQRSTUVWXYZ 가나다라마바사아자차카타파하 뷁똠쀍 0123456789 abcdefghijklmnop']
random.seed(3)
pool = [chr(c) for c in range(0xAC00, 0xD7A4)]
for _ in range(4):
    tests.append(' '.join(''.join(random.choice(pool) for _ in range(random.randint(1, 6))) for _ in range(random.randint(3, 40))))
bad = 0; worst = 0
for t in tests:
    blob, pages, recs = G.pack(t, 100000)
    for pi, (w8, nrow, chars, rec) in enumerate(recs):
        m = S.Mem()
        m.add(B.HOOK, 1024, code)
        m.add(B.STATE, 0x2000)
        m.add(0x060C9000, 0x1000); m.add(0x060FE000, 0x2000)
        vram = m.add(0x25E50000, 0x10000)
        m._f(B.PACK)[0][B.PACK - B.STATE:B.PACK - B.STATE + len(blob)] = blob
        page = B.PACK + struct.unpack_from('>I', blob, 16 + 8 * pi + 4)[0]
        r, n = S.run(m, lab['draw'], regs=[0, page] + [0x1111 * k for k in range(2, 15)] + [0x060FF000])
        assert r[8:15] == [0x1111 * k for k in range(8, 15)] and r[15] == 0x060FF000, '레지스터 보존 실패'
        ref = G.cells_4bpp(G.reference(w8, nrow, chars), w8, nrow)
        o = B.CELL_VRAM & 0xFFFF
        got = bytes(vram[o:o + len(ref)])
        mp = [struct.unpack_from('>H', vram, (B.MAP & 0xFFFF) + B.ROW * 128 + y * 128 + x * 2)[0] for y in range(nrow) for x in range(G.COLS)]
        c0 = (G.COLS - w8) // 2
        want = [(0xF000 | B.CHAR_LO) + (cy * w8 + (x - c0)) if c0 <= x < c0 + w8 and cy < nrow else 0 for cy in range(nrow) for x in range(G.COLS)]
        ok = got == ref and mp == want
        worst = max(worst, n); bad += not ok
        print('%s 쪽%d %d×%d칸 글자 %d 명령 %d  %s' % ('✓' if ok else '✗', pi, w8, nrow, len(chars), n, ' / '.join(pages[pi])[:40]))
        if not ok:
            if got != ref:
                d = next(i for i in range(len(ref)) if got[i] != ref[i]); print('   셀 다름 @%d: %s vs %s' % (d, got[d:d + 8].hex(), ref[d:d + 8].hex()))
            if mp != want:
                d = next(i for i in range(len(mp)) if mp[i] != want[i]); print('   지도 다름 @%d: %04X vs %04X' % (d, mp[d], want[d]))
print('틀림 %d · 최악 명령 수 %d (≈ %.1f ms @28.6 MHz, 명령당 ~1.5클럭 가정)' % (bad, worst, worst * 1.5 / 28.6e3))
