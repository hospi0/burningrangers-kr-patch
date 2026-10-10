# -*- coding: utf-8 -*-
"""PoC 2: 쪽 넘기기 + 음성 끝나면 지우기 (2026-10-09) — poc3 를 바탕으로.
   ADX 머리 0x20 «SUB2» 묶음:
     +0 'SUB2' · +4 u32 끝 샘플 · +8 u16 쪽 수 · +10 u16 묶음 길이 · +12 쪽 표[쪽 수](u32 시작 샘플, u32 쪽 자리)
     쪽 자리(4 정렬, 묶음 처음 기준): u8 w8 · u8 nrow · u8 c0 · u8 0 · 2비트 셀(셀당 16 B)
   훅(0.BIN 끝, RAM 0x0606CC00):
     재생 훅 — 자막 줄 지우고 진행 끔 → 원래 재생 함수
     머리 훅 — r6 ≥ HDR 이고 «SUB2» 면 묶음을 RAM 0x060CF410 에 복사, 상태(진행·다음 쪽·마지막 시각) 초기화 → 원래 함수
     프레임 훅(ADXT_ExecServer 리터럴 0x289C) — 진행 중이면 ADXT_GetTime(음성 핸들) → 시각이 줄었거나 끝 넘으면 지움,
       다음 쪽 시작 넘으면 그 쪽 그림 → 원래 ExecServer
   python tools/poc4.py"""
import os, shutil, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cdmode1
SRC = r'C:\claude\roms\ss\Burning Rangers (Japan)\Burning Rangers (Japan)'
BASE = 'Burning Rangers (Japan)'
OUT = r'F:\hospi\roms\ss roms\Burning Rangers (Japan)'
# 번호: [쪽…] — 쪽 = 한 화면(최대 2줄). 시작 시각은 글자 수 비례로 나눈다.
SUBS = {861: ['쇼, 준비됐어?'],
        862: ['지금부터 당신에게 버닝 레인저로서', '필요한 지식을 가르쳐 줄게.'],
        863: ['나는 리더 겸 내비게이터인 크리스 파튼. 잘 부탁해.']}
HDR = 4096
EXE_LBA, EXE_SIZE = 37, 429056
LOAD = 0x06004000; HOOK = LOAD + EXE_SIZE
PLAY = 0x0604BC98; PLAY_LITS = [0x19518, 0x195d0, 0x19644, 0x45584, 0x456dc, 0x45768, 0x45a30, 0x4647c, 0x4652c]
DEC = 0x060687A4; DEC_LIT = 0x5F8E8
EXEC = 0x0606062C; EXEC_LIT = 0x289C
GETTIME = 0x0606015A; VOICE_H = 0x0605BE38   # ★핸들 변수(0x0604BEA8 은 그 주소를 담은 리터럴 자리 — 잘못 넣어 크래시, 실기)
STATE = 0x060CF400                                  # +0 진행(0/1) · +4 다음 쪽 · +8 마지막 시각 · +12 0 / 묶음 = +16
PACK = STATE + 16
CELL_VRAM = 0x25E56200; CHAR_LO = 0x56200 // 0x20 - 0x2800
MAP = 0x25E5C000; ROW = 20; COLS = 44; MAXW = 320
CRAM_PAL = 0x060C9000 + 127 * 32; SHADOW_PNCN2 = 0x060FFCE0 + 0x34
FONT = ImageFont.truetype(r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.ttf', 12)


# --- 그림 ---------------------------------------------------------------------
_d = ImageDraw.Draw(Image.new('L', (1, 1)))
def tw(s): return _d.textlength(s, font=FONT) + 2


def wrap(t):
    if tw(t) <= MAXW:
        return [t]
    ws = t.split(' '); best = None
    for k in range(1, len(ws)):
        a, b = ' '.join(ws[:k]), ' '.join(ws[k:])
        if tw(a) <= MAXW and tw(b) <= MAXW:
            sc = abs(tw(a) - tw(b))
            if best is None or sc < best[0]: best = (sc, [a, b])
    assert best, '두 줄에 안 들어감: ' + t
    return best[1]


def page_bytes(t, tag):
    lines = wrap(t)
    wpx = max(int(_d.textlength(s, font=FONT)) + 4 for s in lines); w8 = (wpx + 7) // 8
    W, H = w8 * 8, 16 * len(lines)
    fill = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(fill); dr.fontmode = '1'
    for i, s in enumerate(lines):
        dr.text(((W - _d.textlength(s, font=FONT)) / 2, i * 16 + 2), s, font=FONT, fill=255)
    a = (np.array(fill) >= 110).astype(np.uint8) * 2
    o = np.zeros_like(a)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            o |= np.roll(np.roll(a, dy, 0), dx, 1) == 2
    px = np.where((a == 0) & (o == 1), 1, a)
    Image.fromarray(px * 120).save(os.path.join(ROOT, 'work', 'sub_%s.png' % tag))
    nrow = H // 8; out = bytearray()
    for cy in range(nrow):
        for cx in range(w8):
            blk = px[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8]
            for y in range(8):
                for x in range(0, 8, 4):
                    p = blk[y, x:x + 4]; out.append(int(p[0]) << 6 | int(p[1]) << 4 | int(p[2]) << 2 | int(p[3]))
    assert w8 * nrow <= 240
    return bytes([w8, nrow, (COLS - w8) // 2, 0]) + bytes(out), lines


def pack(k, pages, samples):
    total = sum(len(p) for p in pages); t = 0; starts = []
    for p in pages:
        starts.append(int(samples * t / total)); t += len(p)
    body = []; tab = b''
    head = 12 + 8 * len(pages); off = head
    for i, p in enumerate(pages):
        pb, lines = page_bytes(p, '%04d_%d' % (k, i)); body.append(pb)
        tab += struct.pack('>II', starts[i], off); off += (len(pb) + 3) & ~3
        print('  %04d 쪽%d @%5.2f초 %4d B  %s' % (k, i, starts[i] / 22050, len(pb), ' / '.join(lines)))
    blob = bytearray(b'SUB2' + struct.pack('>IHH', samples, len(pages), off) + tab)
    for pb in body:
        blob += pb; blob += bytes(-len(blob) % 4)
    assert len(blob) == off
    return bytes(blob)


# --- ACX ----------------------------------------------------------------------
acx = open(os.path.join(ROOT, 'work', 'iso', 'ADX.ACX'), 'rb').read()
n = struct.unpack_from('>I', acx, 4)[0]
E = [struct.unpack_from('>II', acx, 8 + 8 * i) for i in range(n)]
first = E[0][0]; out = bytearray(first); ents = []
for k, (o, s) in enumerate(E):
    clip = acx[o:o + s]; off = struct.unpack_from('>H', clip, 2)[0]
    assert clip[off - 2:off + 4] == b'(c)CRI' and off == 32
    body = bytearray(HDR - 6 - 0x20)
    if k in SUBS:
        pay = pack(k, SUBS[k], struct.unpack_from('>I', clip, 12)[0])
        assert len(pay) <= len(body), (k, len(pay)); body[:len(pay)] = pay
    c = bytearray(clip[:0x20]) + body + clip[off - 2:]; c[0x1E:0x20] = b'\0\0'
    struct.pack_into('>H', c, 2, HDR - 4); assert c[HDR - 6:HDR] == b'(c)CRI'
    ents.append((len(out), len(c))); out += c; out += bytes(-len(out) % 2048)
struct.pack_into('>II', out, 0, 0, n)
for i, (o, s) in enumerate(ents):
    struct.pack_into('>II', out, 8 + 8 * i, o, s)
out[8 + 8 * n:first] = acx[8 + 8 * n:first]


# --- SH-2 ---------------------------------------------------------------------
class A:
    def __init__(s, base): s.base = base; s.c = []; s.lab = {}; s.fix = []
    def w(s, *v): s.c.extend(x & 0xFFFF for x in v)
    def L(s, n): s.lab[n] = s.base + 2 * len(s.c)
    def br(s, op, n): s.fix.append((len(s.c), op, n)); s.c.append(0)
    def ld(s, rn, val): s.fix.append((len(s.c), 'lit', (rn, val))); s.c.append(0)
    def build(s):
        if len(s.c) % 2: s.c.append(0x0009)
        pool = s.base + 2 * len(s.c); vals = []
        for _, op, a in s.fix:
            if op == 'lit' and a[1] not in vals: vals.append(a[1])
        la = {v: pool + 4 * k for k, v in enumerate(vals)}
        for i, op, a in s.fix:
            pc = s.base + 2 * i
            if op == 'lit':
                d = la[a[1]] - ((pc & ~3) + 4); assert d >= 0 and d % 4 == 0 and d // 4 < 256, (hex(pc), d); s.c[i] = 0xD000 | (a[0] << 8) | d // 4
            else:
                d = (s.lab[a] - (pc + 4)) // 2
                if op in ('bra', 'bsr'): assert -2048 <= d < 2048; s.c[i] = (0xA000 if op == 'bra' else 0xB000) | (d & 0xFFF)
                else: assert -128 <= d < 128, (op, a, d); s.c[i] = (0x8900 if op == 'bt' else 0x8B00) | (d & 0xFF)
        return b''.join(struct.pack('>H', x) for x in s.c) + b''.join(struct.pack('>I', v) for v in vals)


# 그리기 펼침은 손으로 짜기 어려워 단순 루프로 다시 쓴다(아래 assemble2 가 실제 사용).
def assemble2():
    a = A(HOOK); W = a.w
    a.L('play')
    W(0x4F22); a.br('bsr', 'clear'); W(0x0009); W(0x4F26)
    a.ld(1, STATE); W(0xE000, 0x2102)
    a.ld(0, PLAY); W(0x402B, 0x0009)

    a.L('dec')
    a.ld(0, HDR); W(0x3603); a.br('bf', 'dgo')
    W(0x6153, 0x7120)
    for k, ch in enumerate(b'SUB2'):
        W(0x8410 | k, 0x8800 | ch); a.br('bf', 'dgo')
    W(0x841A, 0x600C, 0x6203, 0x4218, 0x841B, 0x600C, 0x220B)
    a.ld(3, PACK)
    a.L('cpy'); W(0x6014, 0x2300, 0x7301, 0x4210); a.br('bf', 'cpy')
    a.ld(1, STATE); W(0xE001, 0x2102, 0xE000, 0x1101, 0x1102)
    a.L('dgo'); a.ld(0, DEC); W(0x402B, 0x0009)

    a.L('frame')
    W(0x4F22, 0x2F46, 0x2F56, 0x2F66, 0x2F76)
    a.ld(1, STATE); W(0x6012, 0x2008); a.br('bt', 'fout')
    W(0x7FF8); a.ld(4, VOICE_H); W(0x6442, 0x65F3, 0x66F3, 0x7604)
    a.ld(0, GETTIME); W(0x400B, 0x0009)
    W(0x67F2, 0x7F08)                           # r7 = 지금 샘플
    a.ld(1, STATE)
    W(0x5012)                                   # r0 = 마지막
    W(0x1172)                                   # 마지막 = r7
    W(0x3702); a.br('bf', 'fend')               # r7 < 마지막 → 끝(되돌아감)
    a.ld(2, PACK)
    W(0x5021)                                   # r0 = 끝 샘플 @(4,r2)
    W(0x3702); a.br('bt', 'fend')               # r7 ≥ 끝 → 끝
    W(0x5311)                                   # r3 = 다음 쪽
    W(0x8524, 0x600D)                           # r0 = 쪽 수(@(8,r2) u16)
    W(0x3302); a.br('bt', 'fout')               # 다음 ≥ 쪽 수
    W(0x6033, 0x4008, 0x4000, 0x700C)           # r0 = 8*k + 12
    W(0x062E)                                   # r6 = 시작
    W(0x3762); a.br('bf', 'fout')               # r7 < 시작 → 아직
    W(0x7004, 0x062E)                           # r6 = 쪽 자리
    W(0x7301, 0x1131)                           # 다음 += 1
    W(0x6123, 0x316C)                           # r1 = r2 + r6
    a.br('bsr', 'draw'); W(0x0009)
    a.br('bra', 'fout'); W(0x0009)
    a.L('fend')
    a.br('bsr', 'clear'); W(0x0009)
    a.ld(1, STATE); W(0xE000, 0x2102)
    a.L('fout')
    W(0x67F6, 0x66F6, 0x65F6, 0x64F6, 0x4F26)
    a.ld(0, EXEC); W(0x402B, 0x0009)

    # ---- draw(r1) ----
    a.L('draw')
    W(0x4F22, 0x2F16)
    a.br('bsr', 'clear'); W(0x0009)
    W(0x61F6)
    W(0x8410, 0x600C, 0x6703)                   # r7 = w8
    W(0x8411, 0x600C, 0x6503)                   # r5 = nrow
    W(0x0757, 0x021A, 0x4208, 0x4208)           # r2 = w8*nrow*16
    W(0x6413, 0x7404)                           # r4 = 셀 그림
    a.ld(3, CELL_VRAM)
    a.L('ex')
    W(0x6044, 0x600C, 0x6603)                   # mov.b @r4+,r0 · extu.b · mov r0,r6     (r6 = b)
    W(0x6063, 0xC903, 0x6503)                   # r5 = b & 3
    W(0x6063, 0x4009, 0xC903, 0x4008, 0x4008, 0x250B)            # r5 |= ((b>>2)&3) << 4
    W(0x6063, 0x4009, 0x4009, 0xC903, 0x4018, 0x250B)            # r5 |= ((b>>4)&3) << 8
    W(0x6063, 0x4009, 0x4009, 0x4009, 0xC903, 0x4018, 0x4008, 0x4008, 0x250B)   # r5 |= ((b>>6)&3) << 12
    W(0x2351, 0x7302, 0x4210)                   # mov.w r5,@r3 · add #2,r3 · dt r2
    a.br('bf', 'ex')
    # 지도
    W(0x8410, 0x600C, 0x6703)                   # r7 = w8
    W(0x8412, 0x600C, 0x6303, 0x4300)           # r3 = c0*2
    a.ld(2, MAP + ROW * 128); W(0x323C)
    W(0x8411, 0x600C, 0x6503)                   # r5 = nrow
    a.ld(4, 0xF000 | CHAR_LO)
    a.L('row'); W(0x6023, 0x6673)               # r0 = 줄 주소 · r6 = w8
    a.L('col'); W(0x2041, 0x7002, 0x7401, 0x4610); a.br('bf', 'col')   # mov.w r4,@r0 · add #2 · add #1,r4 · dt r6
    a.ld(0, 128); W(0x320C, 0x4510); a.br('bf', 'row')
    a.ld(1, CRAM_PAL); a.ld(0, 0x00008000); W(0x2102); a.ld(0, 0xFFFF0000); W(0x1101)
    a.ld(1, SHADOW_PNCN2); a.ld(0, 0x80EA); W(0x2101)
    W(0x4F26, 0x000B, 0x0009)                   # lds.l pr · rts
    # ---- clear: 지도 ROW‥ROW+3 지움 (r0‥r2) ----
    a.L('clear')
    a.ld(1, MAP + ROW * 128); W(0xE000); a.ld(2, 256)
    a.L('clr'); W(0x2101, 0x7102, 0x4210); a.br('bf', 'clr')
    W(0x000B, 0x0009)
    return a


a = assemble2(); code = a.build(); lab = a.lab
print('훅 %d B (자리 1024) · 재생 0x%08X · 머리 0x%08X · 프레임 0x%08X' % (len(code), lab['play'], lab['dec'], lab['frame']))
assert len(code) <= 1024


# --- 디스크 -------------------------------------------------------------------
def bcd(v): return (v // 10) << 4 | v % 10


def new_sector(lba, data):
    m = lba + 150; s = bytearray(2352)
    s[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'; s[12:16] = bytes([bcd(m // 4500), bcd(m // 75 % 60), bcd(m % 75), 1])
    s[16:2064] = data.ljust(2048, b'\0'); return cdmode1.fix(s)


if '--dry' in sys.argv:
    open(os.path.join(ROOT, 'work', 'poc4_hook.bin'), 'wb').write(code); sys.exit()
t1 = os.path.join(OUT, BASE + ' (Track 1).bin')
shutil.copyfile(os.path.join(SRC, BASE + ' (Track 1).bin'), t1)
f = open(t1, 'r+b'); f.seek(0, 2); new_lba = f.tell() // 2352
for k in range(0, len(out), 2048):
    f.write(new_sector(new_lba + k // 2048, out[k:k + 2048]))
total = f.tell() // 2352
exe = bytearray(open(os.path.join(ROOT, 'work', 'iso', '0.BIN'), 'rb').read())
for o in PLAY_LITS:
    assert struct.unpack_from('>I', exe, o)[0] == PLAY; struct.pack_into('>I', exe, o, lab['play'])
assert struct.unpack_from('>I', exe, DEC_LIT)[0] == DEC; struct.pack_into('>I', exe, DEC_LIT, lab['dec'])
assert struct.unpack_from('>I', exe, EXEC_LIT)[0] == EXEC; struct.pack_into('>I', exe, EXEC_LIT, lab['frame'])
exe += code


def rsec(l): f.seek(l * 2352); return bytearray(f.read(2352))
def wsec(l, s): cdmode1.fix(s); f.seek(l * 2352); f.write(s)


for k in range(0, len(exe), 2048):
    s = rsec(EXE_LBA + k // 2048); s[16:2064] = bytes(exe[k:k + 2048]).ljust(2048, b'\0'); wsec(EXE_LBA + k // 2048, s)
pvd = rsec(16); struct.pack_into('<I', pvd, 96, total); struct.pack_into('>I', pvd, 100, total); wsec(16, pvd)
rl = struct.unpack_from('<I', pvd, 16 + 158)[0]; rs = struct.unpack_from('<I', pvd, 16 + 166)[0]; got = set()
for k in range((rs + 2047) // 2048):
    s = rsec(rl + k); i = 16
    while i < 16 + 2048 and s[i]:
        nm = bytes(s[i + 33:i + 33 + s[i + 32]]).split(b';')[0]
        if nm == b'ADX.ACX':
            struct.pack_into('<I', s, i + 2, new_lba); struct.pack_into('>I', s, i + 6, new_lba)
            struct.pack_into('<I', s, i + 10, len(out)); struct.pack_into('>I', s, i + 14, len(out)); got.add(nm)
        if nm == b'0.BIN':
            struct.pack_into('<I', s, i + 10, len(exe)); struct.pack_into('>I', s, i + 14, len(exe)); got.add(nm)
        i += s[i]
    wsec(rl + k, s)
assert got == {b'ADX.ACX', b'0.BIN'}
f.close()
print('ADX.ACX %d B @LBA %d · 0.BIN %d B → %s' % (len(out), new_lba, len(exe), OUT))
