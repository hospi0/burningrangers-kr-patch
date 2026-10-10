# -*- coding: utf-8 -*-
"""시험 3: 음성 0861(트레이닝 첫 대사) 이 나올 때 화면 아래에 «자막» 글자 띄우기 (2026-10-09)
   - 0.BIN 끝 1,024 B(마지막 섹터의 빈 절반, RAM 0x0606CC00 — 모든 스테이트에서 0) 에 훅 코드·글자 셀·색을 붙인다.
   - 음성 재생 함수 0x0604BC98 을 부르는 리터럴 9곳을 훅으로 바꿈 → 훅: NBG2 지도 24‥25줄 지움, r4==861 이면
     셀 8개(VRAM 0x56200)·팔레트 127(CRAM 1024‥)·지도 칸·NBG2 보조 팔레트(레지스터 사본 0x060FFD14 = 0x80EA) 를 쓴 뒤 원래 함수로.
   - 먼저 test_acx_append.py(머리 2,048 판)를 돌려 F: 에 새로 깐 뒤 그 위에 덮어씀."""
import os, struct, subprocess, sys
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cdmode1
T1 = r'F:\hospi\roms\ss roms\Burning Rangers (Japan)\Burning Rangers (Japan) (Track 1).bin'
EXE_LBA, EXE_SIZE = 37, 429056
LOAD = 0x06004000
HOOK = LOAD + EXE_SIZE                       # 0x0606CC00
ORIG = 0x0604BC98
CALL_LITS = [0x19518, 0x195d0, 0x19644, 0x45584, 0x456dc, 0x45768, 0x45a30, 0x4647c, 0x4652c]
CELL_VRAM = 0x25E56200; CHAR_LO = (0x56200 // 0x20) - 0x2800      # 0x310
MAP = 0x25E5C000; ROW = 21; COLS = 44     # 24행은 «Training space 01» 과 겹침(실기 1차)
CRAM_PAL = 0x060C9000 + 127 * 16 * 2      # ★CRAM 은 RAM 사본 0x060C9000 에서 통째로 복사됨(직접 쓰면 지워져 검게 나옴, 실기 1차)
SHADOW_PNCN2 = 0x060FFCE0 + 0x34


# --- 글자 그림 («자막», 32×16, 1=검은 테두리 2=흰 글자) ------------------------
font = ImageFont.truetype(r'C:\claude\utils\font\nanum-gothic\NanumGothicExtraBold.ttf', 14)
W, H = 32, 16
fill = Image.new('L', (W, H), 0); ImageDraw.Draw(fill).text((2, 0), '자막', font=font, fill=255)
px = [[0] * W for _ in range(H)]
for y in range(H):
    for x in range(W):
        if fill.getpixel((x, y)) >= 128:
            px[y][x] = 2
for y in range(H):
    for x in range(W):
        if px[y][x] == 0 and any(0 <= y + dy < H and 0 <= x + dx < W and px[y + dy][x + dx] == 2
                                 for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
            px[y][x] = 1
cells = b''
for cy in range(H // 8):
    for cx in range(W // 8):
        for y in range(8):
            for x in range(0, 8, 2):
                cells += bytes([px[cy * 8 + y][cx * 8 + x] << 4 | px[cy * 8 + y][cx * 8 + x + 1]])
NC = len(cells) // 32                                   # 8
pal = struct.pack('>16H', 0, 0x8000, 0xFFFF, *([0] * 13))
c0 = (COLS - W // 8) // 2
mapw = []                                               # (지도 주소, PN)
for cy in range(H // 8):
    for cx in range(W // 8):
        mapw.append((MAP + ((ROW + cy) * 64 + c0 + cx) * 2, 0xF000 | (CHAR_LO + cy * (W // 8) + cx)))


# --- SH-2 어셈블(빅 엔디언) ---------------------------------------------------
class A:
    def __init__(s, base): s.base = base; s.c = []; s.lab = {}; s.fix = []
    def w(s, v): s.c.append(v & 0xFFFF)
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
                d = (la[a[1]] - ((pc & ~3) + 4)) // 4; assert 0 <= d < 256; s.c[i] = 0xD000 | (a[0] << 8) | d
            else:
                d = (s.lab[a] - (pc + 4)) // 2
                if op == 'bra': assert -2048 <= d < 2048; s.c[i] = 0xA000 | (d & 0xFFF)
                else: assert -128 <= d < 128; s.c[i] = (0x8900 if op == 'bt' else 0x8B00) | (d & 0xFF)
        return b''.join(struct.pack('>H', x) for x in s.c) + b''.join(struct.pack('>I', v) for v in vals)


def assemble(data_addr):
    a = A(HOOK); W_ = a.w
    W_(0x2F46)                   # mov.l r4,@-r15
    # 지도 24·25줄(128칸) 지우기
    a.ld(1, MAP + ROW * 64 * 2)
    W_(0xE000)                   # mov #0,r0
    a.ld(2, 128)
    a.L('clr')
    W_(0x2101)                   # mov.w r0,@r1
    W_(0x7102)                   # add #2,r1
    W_(0x4210)                   # dt r2
    a.br('bf', 'clr')
    a.ld(3, 861)
    W_(0x3430)                   # cmp/eq r3,r4
    a.br('bf', 'done')
    # 셀 복사(롱 단위)
    a.ld(5, data_addr); a.ld(1, CELL_VRAM); a.ld(2, len(cells) // 4)
    a.L('cp1')
    W_(0x6056)                   # mov.l @r5+,r0
    W_(0x2102)                   # mov.l r0,@r1
    W_(0x7104)                   # add #4,r1
    W_(0x4210)                   # dt r2
    a.br('bf', 'cp1')
    # 팔레트(16색 = 32 B = 8 롱) — r5 는 셀 바로 뒤
    a.ld(1, CRAM_PAL); W_(0xE208)  # mov #8,r2
    a.L('cp2')
    W_(0x6056); W_(0x2102); W_(0x7104); W_(0x4210)
    a.br('bf', 'cp2')
    # 지도 칸: (주소 u32, PN u16, 0 u16) 쌍
    W_(0xE200 | len(mapw))       # mov #n,r2
    a.L('cp3')
    W_(0x6156)                   # mov.l @r5+,r1
    W_(0x6056)                   # mov.l @r5+,r0   ; 상위 16비트 = PN
    W_(0x4029)                   # shlr16 r0
    W_(0x2101)                   # mov.w r0,@r1
    W_(0x4210)
    a.br('bf', 'cp3')
    # NBG2 보조 팔레트 7 (레지스터 사본)
    a.ld(1, SHADOW_PNCN2); a.ld(0, 0x80EA)
    W_(0x2101)                   # mov.w r0,@r1
    a.L('done')
    W_(0x64F6)                   # mov.l @r15+,r4
    a.ld(0, ORIG)
    W_(0x402B)                   # jmp @r0
    W_(0x0009)                   # nop
    return a.build()


code_len = len(assemble(0x06000001))
data_addr = (HOOK + code_len + 3) & ~3
code = assemble(data_addr)
assert len(code) == code_len
blob = bytearray(code) + bytes(data_addr - HOOK - len(code)) + cells + pal
for ad, pn in mapw:
    blob += struct.pack('>IHH', ad, pn, 0)
print('훅 코드 %d B · 데이터 %d B · 합계 %d B (자리 1024)' % (len(code), len(blob) - (data_addr - HOOK), len(blob)))
assert len(blob) <= 1024

# --- 1) 머리 2,048 판 다시 깔기 ------------------------------------------------
subprocess.run([sys.executable, os.path.join(HERE, 'test_acx_append.py')], check=True)

# --- 2) 0.BIN 고치기(제자리 + 끝 1 KB) -----------------------------------------
exe = bytearray(open(os.path.join(ROOT, 'work', 'iso', '0.BIN'), 'rb').read())
for o in CALL_LITS:
    assert struct.unpack_from('>I', exe, o)[0] == ORIG
    struct.pack_into('>I', exe, o, HOOK)
exe += blob
f = open(T1, 'r+b')
for k in range(0, len(exe), 2048):
    lba = EXE_LBA + k // 2048
    f.seek(lba * 2352); s = bytearray(f.read(2352))
    s[16:2064] = bytes(exe[k:k + 2048]).ljust(2048, b'\0'); cdmode1.fix(s)
    f.seek(lba * 2352); f.write(s)
# 디렉터리 크기
f.seek(16 * 2352 + 16); pvd = f.read(2048)
rl = struct.unpack_from('<I', pvd, 158)[0]
f.seek(rl * 2352); s = bytearray(f.read(2352)); i = 16; ok = False
while i < 16 + 2048 and s[i]:
    nl = s[i + 32]
    if bytes(s[i + 33:i + 33 + nl]).split(b';')[0] == b'0.BIN':
        assert struct.unpack_from('<I', s, i + 10)[0] == EXE_SIZE
        struct.pack_into('<I', s, i + 10, len(exe)); struct.pack_into('>I', s, i + 14, len(exe)); ok = True
    i += s[i]
assert ok
cdmode1.fix(s); f.seek(rl * 2352); f.write(s); f.close()
print('0.BIN %d → %d B, 훅 0x%08X → F: 덮어씀' % (EXE_SIZE, len(exe), HOOK))
