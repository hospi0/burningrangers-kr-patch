# -*- coding: utf-8 -*-
"""PoC: 트레이닝 첫 세 줄(0861·0862·0863) 한국어 자막 (2026-10-09)
   ① ADX.ACX 다시 쌓기 — 모든 클립 데이터 시작 2,048 B(실기로 검증된 한계). 자막 있는 클립은 머리 0x20 에
      «SUB1» + 폭(셀)·셀 줄 수·시작 열 + 2비트 셀 그림(셀당 16 B: 0 투명·1 검은 테두리·2 흰 글자).
   ② 0.BIN 끝 빈 절반 섹터(RAM 0x0606CC00) 에 훅 두 개 + 2비트→4비트 변환표(512 B).
      - 재생 훅(음성 재생 0x0604BC98 리터럴 9곳): NBG2 지도 ROW‥ROW+3 줄 지움 → 원래 함수.
      - 머리 해석 훅(ADXB_DecodeHeader 0x060687A4 리터럴 1곳 0x5F8E8): r6 ≥ 2048 이고 머리+0x20 이 «SUB1» 이면
        셀 → VRAM 0x56200, 지도 칸, 팔레트 127(CRAM 사본 0x060C9FE0), PNCN2 사본 0x80EA → 원래 함수.
   ③ ADX.ACX 를 Track 1 끝에 덧붙이고 디렉터리(ADX.ACX·0.BIN)·볼륨 크기 고침 → F: 에 덮어씀.
   python tools/poc3.py"""
import os, shutil, struct, sys
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cdmode1
SRC = r'C:\claude\roms\ss\Burning Rangers (Japan)\Burning Rangers (Japan)'
BASE = 'Burning Rangers (Japan)'
OUT = r'F:\hospi\roms\ss roms\Burning Rangers (Japan)'
SUBS = {861: '쇼, 준비됐어?',
        862: '지금부터 당신에게 버닝 레인저로서 필요한 지식을 가르쳐 줄게.',
        863: '나는 리더 겸 내비게이터인 크리스 파튼. 잘 부탁해.'}
HDR = 4096   # 시험: 2048 정상·6144 잡음 → 4096 은?
EXE_LBA, EXE_SIZE = 37, 429056
LOAD = 0x06004000; HOOK = LOAD + EXE_SIZE
PLAY = 0x0604BC98; PLAY_LITS = [0x19518, 0x195d0, 0x19644, 0x45584, 0x456dc, 0x45768, 0x45a30, 0x4647c, 0x4652c]
DEC = 0x060687A4; DEC_LIT = 0x5F8E8
CELL_VRAM = 0x25E56200; CHAR_LO = 0x56200 // 0x20 - 0x2800
MAP = 0x25E5C000; ROW = 20; COLS = 44; MAXW = 320   # 머리 4 KB 라 폭 여유(갈무리11 두 줄 × 320 px)
CRAM_PAL = 0x060C9000 + 127 * 32; SHADOW_PNCN2 = 0x060FFCE0 + 0x34
FONT = ImageFont.truetype(r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.ttf', 12)   # 사용자 «갈무리 11 이 적당»(14 는 큼). 한글 1‥11행 → +2 내려 16행 가운데. (나눔 14px 는 «게»가 «계»처럼 뭉개짐)


# --- 자막 그림 ----------------------------------------------------------------
def wrap(t):
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    w = lambda s: d.textlength(s, font=FONT) + 2
    if w(t) <= MAXW:
        return [t]
    ws = t.split(' '); best = None
    for k in range(1, len(ws)):
        a, b = ' '.join(ws[:k]), ' '.join(ws[k:])
        if w(a) <= MAXW and w(b) <= MAXW:
            sc = abs(w(a) - w(b))
            if best is None or sc < best[0]:
                best = (sc, [a, b])
    assert best, '두 줄에 안 들어감: ' + t
    return best[1]


def render(t):
    lines = wrap(t)
    d = ImageDraw.Draw(Image.new('L', (1, 1)))
    wpx = max(int(d.textlength(s, font=FONT)) + 4 for s in lines); w8 = (wpx + 7) // 8
    W, H = w8 * 8, 16 * len(lines)
    fill = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(fill); dr.fontmode = '1'   # 안티에일리어싱 끔
    for i, s in enumerate(lines):
        lw = d.textlength(s, font=FONT); dr.text(((W - lw) / 2, i * 16 + 2), s, font=FONT, fill=255)
    px = [[2 if fill.getpixel((x, y)) >= 110 else 0 for x in range(W)] for y in range(H)]
    for y in range(H):
        for x in range(W):
            if px[y][x] == 0 and any(0 <= y + dy < H and 0 <= x + dx < W and px[y + dy][x + dx] == 2
                                     for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                px[y][x] = 1
    nrow = H // 8; out = b''
    for cy in range(nrow):
        for cx in range(w8):
            for y in range(8):
                for x in range(0, 8, 4):
                    p = px[cy * 8 + y][cx * 8 + x:cx * 8 + x + 4]
                    out += bytes([p[0] << 6 | p[1] << 4 | p[2] << 2 | p[3]])
    c0 = (COLS - w8) // 2
    Image.fromarray(__import__('numpy').array(px, 'uint8') * 120).save(os.path.join(ROOT, 'work', 'sub_%04d.png' % k_cur))
    return b'SUB1' + bytes([w8, nrow, c0, 0]) + out, lines


# --- ① ACX ------------------------------------------------------------------
acx = open(os.path.join(ROOT, 'work', 'iso', 'ADX.ACX'), 'rb').read()
n = struct.unpack_from('>I', acx, 4)[0]
E = [struct.unpack_from('>II', acx, 8 + 8 * i) for i in range(n)]
first = E[0][0]; out = bytearray(first); ents = []
for k_cur, (o, s) in enumerate(E):
    clip = acx[o:o + s]; off = struct.unpack_from('>H', clip, 2)[0]
    assert clip[off - 2:off + 4] == b'(c)CRI' and off == 32
    body = bytearray(HDR - 6 - 0x20)
    if k_cur in SUBS:
        pay, lines = render(SUBS[k_cur]); assert len(pay) <= len(body), (k_cur, len(pay))
        body[:len(pay)] = pay; print('%04d %d B %s' % (k_cur, len(pay), ' / '.join(lines)))
    c = bytearray(clip[:0x20]) + body + clip[off - 2:]
    c[0x1E:0x20] = b'\0\0'
    struct.pack_into('>H', c, 2, HDR - 4)
    assert c[HDR - 6:HDR] == b'(c)CRI'
    ents.append((len(out), len(c))); out += c; out += bytes(-len(out) % 2048)
struct.pack_into('>II', out, 0, 0, n)
for i, (o, s) in enumerate(ents):
    struct.pack_into('>II', out, 8 + 8 * i, o, s)
out[8 + 8 * n:first] = acx[8 + 8 * n:first]


# --- ② 훅 ---------------------------------------------------------------------
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
                d = (la[a[1]] - ((pc & ~3) + 4)) // 4; assert 0 <= d < 256 and (la[a[1]] - ((pc & ~3) + 4)) % 4 == 0; s.c[i] = 0xD000 | (a[0] << 8) | d
            else:
                d = (s.lab[a] - (pc + 4)) // 2
                if op == 'bra': assert -2048 <= d < 2048; s.c[i] = 0xA000 | (d & 0xFFF)
                else: assert -128 <= d < 128, (op, a, d); s.c[i] = (0x8900 if op == 'bt' else 0x8B00) | (d & 0xFF)
        return b''.join(struct.pack('>H', x) for x in s.c) + b''.join(struct.pack('>I', v) for v in vals)


def assemble(tab):
    a = A(HOOK); W = a.w
    # ---- 재생 훅: 지도 ROW‥ROW+3 (256 칸) 지우기 ----
    a.L('play')
    a.ld(1, MAP + ROW * 128); W(0xE000); a.ld(2, 256)       # r1, r0=0, r2
    a.L('clr'); W(0x2101, 0x7102, 0x4210); a.br('bf', 'clr')  # mov.w r0,@r1 · add #2,r1 · dt r2
    a.ld(0, PLAY); W(0x402B, 0x0009)                          # jmp @r0 · nop
    # ---- 머리 해석 훅 ----
    a.L('dec')
    a.ld(0, HDR); W(0x3603)                                   # cmp/ge r0,r6  (r6 ≥ HDR — 머리 전체가 버퍼에 있을 때만)
    a.br('bf', 'go')
    W(0x6153)                                                 # mov r5,r1
    W(0x7120)                                                 # add #0x20,r1
    for k, ch in enumerate(b'SUB1'):                          # 바이트씩(버퍼가 4 정렬이 아닐 수 있다 — 롱 읽기는 주소 오류)
        W(0x8410 | k, 0x8800 | ch)                            # mov.b @(k,r1),r0 · cmp/eq #ch,r0
        a.br('bf', 'go')
    # 머리값: w8 @+4, nrow @+5, c0 @+6  → 셀 수 = w8*nrow
    W(0x8414)                                                 # mov.b @(4,r1),r0
    W(0x600C)                                                 # extu.b r0,r0
    W(0x6303)                                                 # mov r0,r3        ; r3 = w8
    W(0x8415)                                                 # mov.b @(5,r1),r0
    W(0x600C)                                                 # extu.b r0,r0     ; r0 = nrow
    W(0x0307)                                                 # mul.l r0,r3      ; macl = 셀 수
    W(0x021A)                                                 # sts macl,r2
    W(0x4208, 0x4208)                                         # shll2 r2 ×2 → 셀 수 × 16 = 바이트
    W(0x7108)                                                 # add #8,r1        ; 그림 시작
    a.ld(7, tab); a.ld(3, CELL_VRAM)
    a.L('ex')
    W(0x6014)                                                 # mov.b @r1+,r0
    W(0x600C)                                                 # extu.b r0,r0
    W(0x300C)                                                 # add r0,r0
    W(0x007D)                                                 # mov.w @(r0,r7),r0
    W(0x2301)                                                 # mov.w r0,@r3
    W(0x7302)                                                 # add #2,r3
    W(0x4210)                                                 # dt r2
    a.br('bf', 'ex')
    # 지도: r 줄마다 MAP + ((ROW+r)*64 + c0)*2 에 w8 칸
    W(0x6153, 0x7120)                                         # r1 = r5+0x20
    W(0x8414, 0x600C, 0x6703)                                 # r7 = w8
    W(0x8416, 0x600C, 0x6303)                                 # r3 = c0
    W(0x4300)                                                 # shll r3          ; c0*2
    a.ld(2, MAP + ROW * 128); W(0x323C)                       # add r3,r2        ; r2 = 첫 줄 첫 칸 주소
    W(0x8415, 0x600C, 0x6103)                                 # r1 = nrow (r1 덮어씀 — 머리 포인터는 r5 에 있음)
    a.ld(3, 0xF000 | CHAR_LO)                                 # r3 = PN
    a.L('row')
    W(0x6023)                                                 # mov r2,r0  ; 이 줄 시작 주소
    W(0x2F76)                                                 # mov.l r7,@-r15 ; w8 보존
    a.L('col')
    W(0x2031)                                                 # mov.w r3,@r0
    W(0x7002)                                                 # add #2,r0
    W(0x7301)                                                 # add #1,r3
    W(0x4710)                                                 # dt r7
    a.br('bf', 'col')
    W(0x67F6)                                                 # mov.l @r15+,r7
    W(0x7280)                                                 # add #-128,r2  … 아래에서 +256
    a.ld(0, 256); W(0x320C)                                   # add r0,r2  ; 다음 줄(+128)
    W(0x4110)                                                 # dt r1
    a.br('bf', 'row')
    # 팔레트(CRAM 사본) · PNCN2 사본
    a.ld(1, CRAM_PAL); a.ld(0, 0x00008000); W(0x2102)        # (0, 0x8000) 롱
    a.ld(0, 0xFFFF0000); W(0x1101)                            # mov.l r0,@(4,r1)  (0xFFFF, 0)
    a.ld(1, SHADOW_PNCN2); a.ld(0, 0x80EA); W(0x2101)
    a.L('go')
    a.ld(0, DEC); W(0x402B, 0x0009)
    return a.build(), a.lab


tab = b''.join(struct.pack('>H', (b >> 6 & 3) << 12 | (b >> 4 & 3) << 8 | (b >> 2 & 3) << 4 | (b & 3)) for b in range(256))
c1, lab = assemble(0x06000000)
tab_addr = (HOOK + len(c1) + 3) & ~3
code, lab = assemble(tab_addr)
assert len(code) == len(c1)
blob = code + bytes(tab_addr - HOOK - len(code)) + tab
print('훅 %d B + 변환표 512 B = %d B (자리 1024) · 재생 훅 0x%08X · 머리 훅 0x%08X' % (len(code), len(blob), lab['play'], lab['dec']))
assert len(blob) <= 1024

# --- ③ 디스크 -----------------------------------------------------------------
def bcd(v): return (v // 10) << 4 | v % 10


def new_sector(lba, data):
    m = lba + 150; s = bytearray(2352)
    s[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'; s[12:16] = bytes([bcd(m // 4500), bcd(m // 75 % 60), bcd(m % 75), 1])
    s[16:2064] = data.ljust(2048, b'\0'); return cdmode1.fix(s)


os.makedirs(OUT, exist_ok=True)
t1 = os.path.join(OUT, BASE + ' (Track 1).bin')
shutil.copyfile(os.path.join(SRC, BASE + ' (Track 1).bin'), t1)
for fn in (BASE + ' (Track 2).bin', BASE + '.cue'):
    d = os.path.join(OUT, fn)
    if not os.path.exists(d) or os.path.getsize(d) != os.path.getsize(os.path.join(SRC, fn)):
        shutil.copyfile(os.path.join(SRC, fn), d)
f = open(t1, 'r+b'); f.seek(0, 2); new_lba = f.tell() // 2352
for k in range(0, len(out), 2048):
    f.write(new_sector(new_lba + k // 2048, out[k:k + 2048]))
total = f.tell() // 2352
exe = bytearray(open(os.path.join(ROOT, 'work', 'iso', '0.BIN'), 'rb').read())
for o in PLAY_LITS:
    assert struct.unpack_from('>I', exe, o)[0] == PLAY; struct.pack_into('>I', exe, o, lab['play'])
assert struct.unpack_from('>I', exe, DEC_LIT)[0] == DEC; struct.pack_into('>I', exe, DEC_LIT, lab['dec'])
exe += blob


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
