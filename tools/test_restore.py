# -*- coding: utf-8 -*-
"""훅 검산 — 지도 20‥23행의 게임 그림 보존·PNCN2 보충 비트 복원·팔레트 비추기 (2026-10-10)"""
import os, struct, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as B, glyphpack as G, sh2sim as S
code, lab = B.hooks()
m = S.Mem(); m.add(B.HOOK, 1024, code); m.add(B.STATE, 0x2000); cram = m.add(0x060C9000, 0x1000); m.add(0x060FE000, 0x2000)
vram = m.add(0x25E50000, 0x10000); m.add(0x0605B000, 0x1000); m.w32(B.VOICE_H, 0x0605B800)
mo = (B.MAP & 0xFFFF) + B.ROW * 128
game = bytes((i * 7 + 3) & 0xFF for i in range(512)); vram[mo:mo + 512] = game          # 게임이 그린 줄
m.w16(B.SHADOW_PNCN2, 0x800A)
for i in range(256): struct.pack_into('>H', cram, i * 2, 0x1000 + i)                     # 팔레트 0‥15
blob, pages, recs = G.pack('시험 자막 하나 | 둘째 쪽', 100000)
m._f(B.PACK)[0][B.PACK - B.STATE:B.PACK - B.STATE + len(blob)] = blob
page = B.PACK + struct.unpack_from('>I', blob, 20)[0]
S.run(m, lab['draw'], regs=[0, page] + [0] * 13 + [0x060FF000])
ok1 = m.r16(B.SHADOW_PNCN2) == 0x80EA and bytes(vram[mo:mo + 512]) != game
m.w32(0x0605B804, 0x0605BA00); m.w8(0x0605BA01, 4); m.w32(0x0605BA10, 0x0605BC00)
m.w32(B.STATE, 1); S.run(m, lab['frame'], calls={B.EXEC: lambda r, mm: None})
ok2 = all(struct.unpack_from('>H', cram, 0xE00 + i * 2)[0] == (0x8000 if i == 241 else 0xFFFF if i == 255 else 0x1000 + i) for i in range(256))
S.run(m, lab['clear'])
ok3 = bytes(vram[mo:mo + 512]) == game and m.r16(B.SHADOW_PNCN2) == 0x800A
vram[mo:mo + 512] = game; S.run(m, lab['clear'])                                         # 저장 없이 지우기 → 그대로
ok4 = bytes(vram[mo:mo + 512]) == game
print('그리기 후 보충 켬·자막 그림 %s · 팔레트 비춤 %s · 지우면 게임 줄·PNCN2 복원 %s · 그린 적 없으면 안 건드림 %s' % (ok1, ok2, ok3, ok4))
