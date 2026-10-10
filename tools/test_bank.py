# -*- coding: utf-8 -*-
"""공용 글꼴 검산 (2026-10-10) — SH-2 흉내기로 머리 훅(dec)을 돌려
   ① 싣기 클립: 묶음 뒤 공용 글꼴이 BANK+위치 로 복사되는지
   ② 쓰기 클립: 공용 글꼴이 묶음 바로 뒤로 이어 붙고, 그 묶음으로 그린 쪽이 기준 그림과 같은지
   ③ r4‥r7(DecodeHeader 인수)·r15 보존, 원래 DecodeHeader 로 넘어가는지
   python tools/test_bank.py"""
import os, struct, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as B, glyphpack as G, sh2sim as S

code, lab = B.hooks()
bank = list('모니터실도착했어시설정보를보낼게소장님께확인')
bb = G.bank_bytes(bank); units = len(bb) // 16; OFF = 3            # 위치 3 × 256 B
small = '알았어.조심해.'
big = '모니터실에 도착했어!시설 정보를 보낼게! | 소장님께 확인했어.돔 부분에는 아이들이 많이 있대. | 나도 위로!'


def mem():
    m = S.Mem(); m.add(B.HOOK, 1024, code); m.add(B.STATE, 0x4000)
    m.add(0x060C9000, 0x1000); m.add(0x060FE000, 0x2000); m.add(0x25E50000, 0x10000)
    m.add(0x06090000, 0x1000)                                     # ADX 머리 버퍼
    return m


def run_dec(m, payload):
    hdr = bytearray(0x800); hdr[0x20:0x20 + len(payload)] = payload
    m._f(0x06090000)[0][:0x800] = hdr
    hit = []
    regs = [0, 0, 0, 0, 0x4444, 0x06090000, 0x800, 0x7777] + [0] * 7 + [0x060FF000]
    r, n = S.run(m, lab['dec'], regs=regs, calls={B.DEC: lambda r, mm: hit.append(list(r))})
    return hit


ok = True
# ① 싣기
m = mem()
blob, _, _ = G.pack(small, 22050, carry=units, bank_off=OFF)
h = run_dec(m, blob + bb)
got = bytes(m.r8(B.BANK + OFF * 256 + i) for i in range(len(bb)))
ok1 = got == bb and h and h[0][4:8] == [0x4444, 0x06090000, 0x800, 0x7777] and h[0][15] == 0x060FF000
print('① 싣기: 공용 글꼴 %d B 복사 %s · 인수 보존 %s' % (len(bb), got == bb, bool(h) and h[0][4:8] == [0x4444, 0x06090000, 0x800, 0x7777]))
# ② 쓰기 (같은 메모리 — 공용 글꼴이 실려 있는 상태)
blob, pages, recs = G.pack(big, 22050, bank=bank, bank_off=OFF)
h = run_dec(m, blob)
total = struct.unpack_from('>H', blob, 10)[0]
after = bytes(m.r8(B.PACK + total + i) for i in range(len(bb)))
ok2 = after == bb
bad = 0
for pi, (w8, nrow, chars, rec) in enumerate(recs):
    page = B.PACK + struct.unpack_from('>I', blob, 16 + 8 * pi + 4)[0]
    S.run(m, lab['draw'], regs=[0, page] + [0] * 13 + [0x060FF000])
    ref = G.cells_4bpp(G.reference(w8, nrow, chars), w8, nrow)
    o = B.CELL_VRAM
    gotc = bytes(m.r8(o + i) for i in range(len(ref)))
    bad += gotc != ref
print('② 쓰기: 묶음 %d B + 공용 %d B 이어 붙음 %s · 쪽 %d개 그림 틀림 %d' % (total, len(bb), ok2, len(recs), bad))
ok = ok1 and ok2 and bad == 0 and bool(h) and h[0][4:8] == [0x4444, 0x06090000, 0x800, 0x7777]
# ③ 공용 글꼴 없는 보통 클립은 그대로
m = mem(); blob, _, _ = G.pack(small, 22050)
h = run_dec(m, blob)
ok3 = bytes(m.r8(B.BANK + i) for i in range(64)) == bytes(64) and bool(h)
print('③ 보통 클립: 공용 글꼴 안 건드림 %s' % ok3)
print('결과', '통과' if ok and ok3 else '실패')
