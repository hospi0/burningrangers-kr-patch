# -*- coding: utf-8 -*-
"""훅 dec/frame 검산 — 머리 복사 → 시각을 흘리며 쪽 넘김·끝 지움 확인. python tools/test_frame.py"""
import os, struct, sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as B, glyphpack as G, sh2sim as S
code, lab = B.hooks()
t = '모니터 룸에 도착했어! 시설 정보를 보낼게! | 서장한테 확인했어. 돔에는 초대받은 아이들이 잔뜩 있대. | 리드 팀만으로는 도저히…'
SAMP = 22050 * 10
blob, pages, recs = G.pack(t, SAMP)
m = S.Mem(); m.add(B.HOOK, 1024, code); m.add(B.STATE, 0x2000); m.add(0x060C9000, 0x1000); m.add(0x060FE000, 0x2000)
vram = m.add(0x25E50000, 0x10000); m.add(0x0605B000, 0x1000)
hdr = m.add(0x06200000, B.HDR); hdr[0x20:0x20 + len(blob)] = blob
m.w32(B.VOICE_H, 0x0605B800)                       # 바깥 핸들 → 안쪽 ADXT(0x0605BA00): 상태 4 · @44 디코드 샘플 · @16 소리 객체(@28 버퍼 남은 양) · @56 보정
IN = 0x0605BA00; m.w32(0x0605B804, IN); m.w8(IN + 1, 4); m.w32(IN + 16, 0x0605BC00); m.w32(0x0605BC00 + 28, 300); m.w32(IN + 56, 300)
class Now:
    def __setitem__(s, i, v): m.w32(IN + 44, v)     # 지금 샘플 = @44 − 300 + 300
now = Now()
log = []
calls = {B.DEC: lambda r, mem: log.append('DEC'), B.EXEC: lambda r, mem: None}
S.run(m, lab['dec'], regs=[0, 0, 0, 0, 0, 0x06200000, B.HDR], calls=calls)
assert m.r32(B.PACK) == struct.unpack('>I', blob[:4])[0] and log == ['DEC']
print('복사 OK, 진행', m.r32(B.STATE))
def rowmap(): return sum(struct.unpack_from('>H', vram, (B.MAP & 0xFFFF) + B.ROW * 128 + i * 2)[0] != 0 for i in range(4 * 64))
starts = [struct.unpack_from('>I', blob, 16 + 8 * i)[0] for i in range(len(pages))]
print('쪽 시작', starts)
for s in range(0, SAMP + 30000, 11025):
    now[0] = s; S.run(m, lab['frame'], calls=calls)
    print('%6d샘플 다음쪽 %d 진행 %d 지도칸 %d' % (s, m.r32(B.STATE + 4), m.r32(B.STATE), rowmap()))
now[0] = 0
# 끝난 뒤 남기기(LINGER) 검사: 재생이 끝난 상태(시각 0)로 프레임을 흘림
S.run(m, lab['dec'], regs=[0, 0, 0, 0, 0, 0x06200000, B.HDR], calls=calls)
for s in (0, 200000): now[0] = s; S.run(m, lab['frame'], calls=calls)
now[0] = 0; seen = []
for f in range(B.LINGER + 3):
    S.run(m, lab['frame'], calls=calls); seen.append(rowmap() > 0)
print('끝난 뒤 자막 남은 프레임', sum(seen), '(기대 %d)' % B.LINGER, '진행', m.r32(B.STATE))

# ★안쪽 객체 0(핸들 다시 만드는 중)이면 시각 0 — 자막이 바로 끝나면 안 됨
m.w32(0x0605B804, 0); S.run(m, lab['dec'], regs=[0, 0, 0, 0, 0, 0x06200000, B.HDR], calls=calls)
for f in range(5): S.run(m, lab['frame'], calls=calls)
print('핸들 0 동안: 진행', m.r32(B.STATE), '마지막 시각', m.r32(B.STATE + 8), '(기대 1 · 0)')
# ★상태 ≤ 2(재생 준비 중)면 시각 0 — @44 에 이전 파일 값이 남아 있어도
m.w32(0x0605B804, IN); m.w8(IN + 1, 2); m.w32(IN + 44, 900000)
S.run(m, lab['dec'], regs=[0, 0, 0, 0, 0, 0x06200000, B.HDR], calls=calls)
for f in range(5): S.run(m, lab['frame'], calls=calls)
print('상태 2 동안: 진행', m.r32(B.STATE), '마지막 시각', m.r32(B.STATE + 8), '(기대 1 · 0)')
# ★출렁임: 시각이 조금 뒤로 가도 안 끝남(직전 값으로 고정) · 0 으로 떨어지면 끝
m.w8(IN + 1, 4); S.run(m, lab['dec'], regs=[0, 0, 0, 0, 0, 0x06200000, B.HDR], calls=calls)
for t in (30000, 50000, 48500, 49000, 52000):
    m.w32(IN + 44, t); S.run(m, lab['frame'], calls=calls)
ok_j = m.r32(B.STATE) == 1 and m.r32(B.STATE + 8) == 52000
m.w32(IN + 44, 0); S.run(m, lab['frame'], calls=calls)
print('출렁임에 안 끝남', ok_j, '· 0 이면 끝(진행 2)', m.r32(B.STATE) == 2)
