# -*- coding: utf-8 -*-
"""버닝 레인저 한글 자막 빌더 (2026-10-09) — poc4 를 정식으로.
   번역표(work/trans/*.tsv 또는 --trans 폴더)의 ko 열 → 클립마다 쪽 묶음(SUB4, 글꼴 조각 + 글자 위치) → ADX 머리 4 KB 에 실음
   → ADX.ACX 다시 쌓아 Track 1 끝에 덧붙임 + 0.BIN 끝에 훅 → F: 에 덮어씀(--write 일 때만).
   ko 규칙: 비우면 자막 없음 · « | » = 쪽 나눔(없으면 한 줄 320 px 로 줄 나눔, 2줄씩 한 쪽) · 쪽 시작 시각은 글자 수 비례.
   python tools/build.py            # 미리보기(넘치는 번호·크기 보고)
   python tools/build.py --write    # 디스크 기록
   python tools/build.py --stress   # 번역 대신 일본어 글자 수만큼 «가» 를 채워 최악 크기 재기"""
import glob, json, os, re, shutil, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import cdmode1
SRC = r'C:\claude\roms\ss\Burning Rangers (Japan)\Burning Rangers (Japan)'
BASE = 'Burning Rangers (Japan)'
OUT = r'F:\hospi\roms\ss roms\Burning Rangers (Japan)'
HDR = 4096                                   # 실기: 2048·4096 정상, 6144 잡음
LINGER = 45                                  # 음성 끝난 뒤 마지막 쪽을 남기는 프레임(0.75초 — 사용자 «너무 빨리 사라짐» 2026-10-10)
SMALL_HDR = 2048                             # 묶음이 작으면 이쪽(지직 방지)
ROOM = SMALL_HDR - 6 - 0x20                  # 묶음 자리 = 머리 2,048 B 의 0x20 ‥ «(c)CRI» 앞 (★4,096 B 머리는 미션 중 멈춤 — 안 씀)
EXE_LBA, EXE_SIZE = 37, 429056
INPLACE = [  # 제자리로 바꿔 쓰는 파일: (이름, LBA, 섹터 수, 만든 파일) — 원래 섹터를 넘으면 빌드 중지
    (b'LOADDATA.BIN', 6072, 50, os.path.join(ROOT, 'work', 'LOADDATA_kr.BIN')),   # 부팅 로딩 화면(tools/loadscreen.py --pack) · 뒤 MAILDATA 6122
    (b'TXTRDATA.BIN', 7270, 17, os.path.join(ROOT, 'work', 'TXTRDATA_kr.BIN')),   # 대원 소개 카드(tools/cards.py --pack) · 뒤 PLDATA 7287
    (b'MAIL.BIN', 7753, 17, os.path.join(ROOT, 'work', 'MAIL_kr.BIN')),            # 메일 본문(tools/mail.py --pack) · 뒤 PRG11 7770
    (b'ZENFONT.FNT', 6666, 37, os.path.join(ROOT, 'work', 'ZENFONT_kr.FNT')),      # 메일 글꼴(tools/mail.py --pack) · 뒤 OPTDATA 6703
] + [(n.encode() + b'.CAK', lba, (size + 2047) // 2048, os.path.join(ROOT, 'work', 'kr', n + '.CAK'))   # 컷신 자막(tools/moviesub.py, 원본 크기)
     for n, lba, size in [('OP', 99602, 19843808), ('R01', 109292, 4033800), ('R02', 111262, 6998352), ('R03S', 114680, 6465128),
                          ('R03T', 117837, 6533432), ('R04ES', 121028, 11344040), ('R04ET', 126568, 12792596),
                          ('R04HS', 132815, 19145288), ('R04HT', 142164, 19145288)]]
LOAD = 0x06004000; HOOK = LOAD + EXE_SIZE    # 0.BIN 마지막 섹터 빈 절반(1,024 B)
PLAY = 0x0604BC98; PLAY_LITS = [0x19518, 0x195d0, 0x19644, 0x45584, 0x456dc, 0x45768, 0x45a30, 0x4647c, 0x4652c]
DEC = 0x060687A4; DEC_LIT = 0x5F8E8          # ADXB_DecodeHeader(→ DecodeHeaderAdx) 리터럴
EXEC = 0x0606062C; EXEC_LIT = 0x289C         # ADXT_ExecServer — VBlank 인터럽트 안
GETTIME = 0x0606015A; VOICE_H = 0x0605BE38   # 음성 ADXT 핸들 «변수»(⚠0x0605BEA8 은 리터럴 자리) · ★GETTIME 은 부르지 말 것(핸들에 시각 저장 — 위 frame 참고)
# ★⛔0x060CF400 은 미션 장면에서 게임이 쓴다(2026-10-10 «자막 안 나옴·크리스 대답 지직») → VDP2 VRAM B1 끝 17 KB(스테이트 16장 모두 0)로
STATE = 0x25E7C000; PACK = STATE + 16; TMP = 0x25E7D000   # VRAM 0x7BD5F‥0x7FFFF 안
CELL_VRAM = 0x25E56200; CHAR_LO = 0x56200 // 0x20 - 0x2800; MAXCELL = 240
MAP = 0x25E5C000; ROW = 20; COLS = 44; MAXW = 320
CRAM_SH = 0x060C9000; CRAM_PAL = CRAM_SH + 127 * 32; SHADOW_PNCN2 = 0x060FFCE0 + 0x34; SHADOW_BGON = 0x060FFCE0 + 0x20
SAVE = 0x25E7D800                                # 지도 20‥23행 저장(512 B) — 저장 표시는 PNCN2 보충 비트
BANK = 0x25E7E000                                # 공용 글꼴(VRAM 0x7E000‥0x7FFFF 8 KB — 모든 장면 덤프에서 빈 곳)


# ============ 글자 → 쪽 : tools/glyphpack.py (SUB4 = 클립별 글꼴 조각 + 글자 위치, 게임 코드가 찍고 테두리) ============
import glyphpack as G
BUF = TMP; BSTR = 52                         # 1비트 쪽 버퍼: 행 52 B(왼쪽 8 px 여유) × 34행(위아래 1행 여유)


# ============ SH-2 훅 ============
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
            if op == 'lit':
                v = s.lab[a[1]] if isinstance(a[1], str) else a[1]
                if v not in vals: vals.append(v)
        la = {v: pool + 4 * k for k, v in enumerate(vals)}
        for i, op, a in s.fix:
            pc = s.base + 2 * i
            if op == 'lit':
                d = la[s.lab[a[1]] if isinstance(a[1], str) else a[1]] - ((pc & ~3) + 4); assert d >= 0 and d % 4 == 0 and d // 4 < 256, (hex(pc), d); s.c[i] = 0xD000 | (a[0] << 8) | d // 4
            else:
                d = (s.lab[a] - (pc + 4)) // 2
                if op in ('bra', 'bsr'): assert -2048 <= d < 2048; s.c[i] = (0xA000 if op == 'bra' else 0xB000) | (d & 0xFFF)
                else: assert -128 <= d < 128, (op, a, d); s.c[i] = {'bt': 0x8900, 'bf': 0x8B00, 'bts': 0x8D00, 'bfs': 0x8F00}[op] | (d & 0xFF)   # ★bt/s·bf/s(지연) — 예전엔 bf 로 잘못 만들어짐
        return b''.join(struct.pack('>H', x) for x in s.c) + b''.join(struct.pack('>I', v) for v in vals)


def hooks():
    a = A(HOOK); W = a.w
    # ---- 재생 훅: 지우고 진행 끔 ----
    a.L('play')
    W(0x4F22); a.br('bsr', 'clear'); W(0x0009); W(0x4F26)
    a.ld(1, STATE); W(0xE200); a.ld(0, PLAY); W(0x402B, 0x2122)   # 진행 0 (jmp 지연 칸)
    # ---- 머리 훅: SUB4 묶음 복사 ----
    a.L('dec')
    W(0xE008, 0x4018, 0x3603); a.br('bf', 'dgo')          # r6 ≥ 2,048(작은 머리도 받음) — mov #8,r0 · shll8
    W(0x6153, 0x7120)                                     # r1 = r5+0x20
    for k, ch in enumerate(b'SU'):                       # «SU» 두 글자만(자리 아끼기 — 원본 ADX 는 이 자리가 «)C…»)
        W(0x8410 | k, 0x8800 | ch); a.br('bf', 'dgo')
    W(0x841A, 0x600C, 0x6203, 0x4218, 0x841B, 0x600C, 0x220B)   # r2 = 묶음 길이
    a.ld(3, PACK)
    a.L('cpy'); W(0x6014, 0x2300, 0x7301, 0x4210); a.br('bf', 'cpy')
    # ★공용 글꼴(2026-10-10 — 0305 등 큰 클립이 머리 2,048 B 를 넘어 4,096 B 머리를 쓰면 미션 중 멈춤):
    #   묶음 14번 바이트 = 16 B 단위 수 | 0x80(쓰기) · 15번 = 위치(256 B 단위), 공용 글꼴 = BANK + 위치
    #   싣기(0x80 없음): 머리의 묶음 바로 뒤(r1) → 공용 글꼴 · 쓰기: 공용 글꼴 → 묶음 바로 뒤(r3, 글자 번호 L.. 로 이어짐)
    #   r4‥r7 은 DecodeHeader 인수라 r4 는 스택에 저장
    a.ld(2, PACK); W(0x842E, 0x2008); a.br('bt', 'bkend')  # r0 = 14번(부호 붙음) · 0 이면 없음
    W(0x2F46, 0x6403)                                     # push r4 · r4 = 14번
    W(0x842F, 0x600C, 0x4018)                             # r0 = 15번 << 8
    a.ld(2, BANK); W(0x320C)                              # r2 = 공용 글꼴 자리
    W(0x6043, 0xC97F, 0x4008, 0x4008, 0x4411, 0x6403)     # r4 = 바이트 수(단위×16) · T = 싣기(14번 ≥ 0)
    a.br('bf', 'bkuse'); W(0x0009)
    a.br('bra', 'bkcp'); W(0x6323)                        # 싣기: 받는 곳 = 공용 글꼴
    a.L('bkuse'); W(0x6123)                               # 쓰기: 보내는 곳 = 공용 글꼴
    a.L('bkcp'); W(0x6014, 0x2300, 0x7301, 0x4410); a.br('bf', 'bkcp')   # 바이트씩(머리 버퍼 정렬 보장 없음)
    W(0x64F6)                                             # pop r4
    a.L('bkend')
    a.ld(1, STATE); W(0xE001, 0x2102, 0xE000, 0x1101, 0x1102)  # 진행 1 · 다음 쪽 0 · 마지막 시각 0
    a.L('dgo'); a.ld(0, DEC); W(0x402B, 0x0009)
    # ---- 프레임 훅(VBlank) ----
    a.L('frame')
    W(0x4F22, 0x2F46, 0x2F56, 0x2F66, 0x2F76)
    a.ld(1, STATE); W(0x6012, 0x2008); a.br('bt', 'fout')
    a.br('bsr', 'mirror'); W(0x0009)                      # 자막이 있는 동안 팔레트 0‥14 → 보충 7 자리
    a.ld(1, STATE); W(0x6012)
    W(0x8802); a.br('bt', 'linger')                       # 진행 2 = 끝난 뒤 남겨 두는 중
    # ★지금 샘플 = ADXT_GetTime 과 같은 계산을 «저장 없이» (2026-10-10): GetTime 은 핸들+52 에 마지막 시각을 저장·고정해서,
    #   인터럽트에서 부르면 튄 값이 박혀 게임의 «음성 끝?»(0x0604BD90, 시각 ≥ 전체−0x4000) 이 일찍 참 → 컷신이 대사 도중 넘어감(0314)
    #   t = 핸들 0 이거나 상태<3 ? 0 : 상태==5 ? @44 : @44 − @(28,@16) + @56   (핸들 = @(4,@VOICE_H))
    a.ld(4, VOICE_H); W(0x6442, 0x5441, 0x2448)
    a.br('bts', 'tdone'); W(0xE700)                       # ★안쪽 객체 0(미션 시작 때 핸들 다시 만드는 중) → 0 — 없으면 주소 0(BIOS 벡터)을 읽어 엄청 큰 시각 → 자막 바로 끝남(2026-10-10 미션 도입)
    W(0x8441, 0xE102, 0x3017); a.br('bf', 'tdone')       # 상태 ≤ 2 → 0
    W(0x574B, 0x8805); a.br('bt', 'tdone')                # r7 = @44 · 상태 5 → 그대로
    W(0x5044, 0x5007, 0x3708, 0x504E, 0x370C)             # r7 −= @(28,@16) · r7 += @56
    a.L('tdone')
    # ★시각이 0 으로 떨어질 때만 «끝»(정지·핸들 다시 만듦) — 조금 뒤로 가는 출렁임(버퍼 양)은 직전 시각으로 고정(우리 상태 칸에만).
    #   예전엔 «뒤로 가면 끝»이라 직접 계산으로 바꾼 뒤 자막이 잠깐 나오고 지워졌다(2026-10-10)
    a.ld(1, STATE); W(0x5012, 0x3702); a.br('bt', 'tok')  # r0 = 마지막 · r7 ≥ 마지막 → 그대로
    W(0x2778); a.br('bt', 'fend')                         # r7 == 0 → 재생 끝
    W(0x6703)                                             # 뒤로 조금 → r7 = 마지막
    a.L('tok'); W(0x1172)                                 # 마지막 = r7
    a.ld(2, PACK); W(0x5021, 0x3702); a.br('bt', 'fend')  # r7 ≥ 끝 샘플 → 끝
    W(0x5311, 0x8524, 0x600D, 0x3302); a.br('bt', 'fout') # 다음 ≥ 쪽 수
    W(0x6033, 0x4008, 0x4000, 0x7010, 0x062E)             # r6 = 쪽 시작
    W(0x3762); a.br('bf', 'fout')
    W(0x7004, 0x062E, 0x7301, 0x1131, 0x6123)             # r1 = PACK + 쪽 자리 · 다음 += 1
    a.br('bsr', 'draw'); W(0x316C)                        # 지연 칸
    a.br('bra', 'fout2'); W(0x67F6)                       # 지연 칸 = fout 첫 명령(pop r7)
    a.L('fend')                                           # 끝 → 바로 지우지 않고 LINGER 프레임 남김
    a.ld(1, STATE); W(0xE002, 0x2102, 0xE000 | LINGER, 0x1103)
    a.br('bra', 'fout2'); W(0x67F6)                       # 지연 칸 = fout 첫 명령(pop r7)
    a.L('linger'); W(0x5013, 0x4010, 0x1103); a.br('bf', 'fout')   # 셈 −1, 0 이 되면 지움
    a.br('bsr', 'clear'); W(0x0009)
    a.ld(1, STATE); W(0xE000, 0x2102)
    a.L('fout'); W(0x67F6); a.L('fout2'); W(0x66F6, 0x65F6, 0x64F6)
    a.ld(0, EXEC); W(0x402B, 0x4F26)                      # 지연 칸 = PR 복원
    # ---- draw(r1 = 쪽) : 글자 찍기(1비트 버퍼) → 3×3 테두리 → 4비트 셀 ----
    mov = lambda m, n: 0x6003 | n << 8 | m << 4
    ldb = lambda m, n: 0x6000 | n << 8 | m << 4          # mov.b @Rm,Rn
    ldbp = lambda m, n: 0x6004 | n << 8 | m << 4         # mov.b @Rm+,Rn
    stb = lambda m, n: 0x2000 | n << 8 | m << 4          # mov.b Rm,@Rn
    ldb0 = lambda m, d: 0x8400 | m << 4 | d              # mov.b @(d,Rm),R0
    stb0 = lambda n, d: 0x8000 | n << 4 | d              # mov.b R0,@(d,Rn)
    exb = lambda m, n: 0x600C | n << 8 | m << 4
    exw = lambda m, n: 0x600D | n << 8 | m << 4
    OR = lambda m, n: 0x200B | n << 8 | m << 4
    AND = lambda m, n: 0x2009 | n << 8 | m << 4
    ADD = lambda m, n: 0x300C | n << 8 | m << 4
    addi = lambda n, i: 0x7000 | n << 8 | (i & 0xFF)
    movi = lambda n, i: 0xE000 | n << 8 | (i & 0xFF)
    shll = lambda n: 0x4000 | n << 8; shlr = lambda n: 0x4001 | n << 8
    shll2 = lambda n: 0x4008 | n << 8; shlr2 = lambda n: 0x4009 | n << 8
    shll8 = lambda n: 0x4018 | n << 8; shlr8 = lambda n: 0x4019 | n << 8
    shll16 = lambda n: 0x4028 | n << 8; shlr16 = lambda n: 0x4029 | n << 8
    dt = lambda n: 0x4010 | n << 8
    ldw_r0 = lambda m, n: 0x000D | n << 8 | m << 4       # mov.w @(R0,Rm),Rn
    push = lambda m: 0x2F06 | m << 4; pop = lambda n: 0x60F6 | n << 8
    a.L('draw')
    W(0x4F22, push(1)); W(*[push(r) for r in range(8, 14)])
    a.br('bsr', 'clear'); W(push(14))                    # 지연 칸(clear 는 스택 안 씀)
    a.ld(1, MAP + ROW * 128); a.ld(2, SAVE); a.ld(3, 128)  # 지도 20‥23행(게임 그림) 저장
    a.L('dsv'); W(0x6016, 0x2202, 0x7204, 0x4310); a.br('bf', 'dsv')
    W(0x58F7)                                             # r8 = 쪽 (mov.l @(28,r15))
    a.ld(2, BUF); a.ld(3, BSTR * 34 // 4); W(movi(0, 0))
    a.L('cb'); W(0x2202, addi(2, 4), dt(3)); a.br('bf', 'cb')
    a.ld(9, PACK); W(0x8596, exw(0, 0), ADD(0, 9))        # r9 = 글꼴 = PACK + @(12,PACK)
    W(ldb0(8, 3), exb(0, 10), mov(8, 11), addi(11, 4))    # r10 = 글자 수 · r11 = 글자 표
    W(0x2AA8); a.br('bt', 'chd')                          # tst r10,r10
    a.L('ch')
    W(ldbp(11, 0), exb(0, 1), shll(1), mov(1, 12), shll2(12), shll(12), ADD(1, 12), ADD(9, 12))   # r12 = 글꼴 + 번호*18
    W(ldbp(11, 0), exb(0, 13))                            # r13 = x 하위
    W(ldbp(11, 0), exb(0, 0), mov(0, 2), 0xC901, shll8(0), OR(0, 13), addi(13, 8), shlr(2))   # r13 = x+8 · r2 = 줄
    W(shll2(2), shll2(2), addi(2, 4), movi(3, BSTR), 0x0237, 0x021A)   # r2 = (줄*16+4)*52
    a.ld(3, BUF); W(ADD(3, 2), mov(13, 0), shlr2(0), shlr(0), ADD(0, 2))   # r2 = 버퍼 + 행 + (x>>3)
    W(mov(13, 0), 0xC907, mov(0, 14), movi(3, 6))         # r14 = x&7 · r3 = 6 (두 행씩)
    a.L('gp')
    W(ldbp(12, 4), exb(4, 4), ldbp(12, 5), exb(5, 5), ldbp(12, 6), exb(6, 6))
    W(mov(4, 0), shll2(0), shll2(0), mov(5, 1), shlr2(1), shlr2(1))
    a.br('bsr', 'stamp'); W(OR(1, 0))                    # 지연 칸
    W(mov(5, 0), 0xC90F, shll8(0))
    a.br('bsr', 'stamp'); W(OR(6, 0))                    # 지연 칸
    W(dt(3)); a.br('bf', 'gp')
    W(dt(10)); a.br('bf', 'ch')
    a.L('chd')
    # 셀 변환: r9 = nrow 칸 · r10 = 이 칸 줄 버퍼(가운데 행, 바이트 cx) · r11 = VRAM · r12 = 펼침 표
    W(ldb0(8, 1), exb(0, 9))                              # r9 = nrow
    a.ld(10, BUF); W(addi(10, BSTR)); a.ld(11, CELL_VRAM); a.ld(12, 'etab')
    a.L('cy'); W(ldb0(8, 0), exb(0, 13), mov(10, 14))
    a.L('cx'); W(mov(14, 2), movi(3, 8))
    a.L('cyy')
    W(mov(2, 4), addi(4, -BSTR), mov(2, 5), addi(5, BSTR))
    W(ldb(4, 0), ldb(2, 1), OR(1, 0), ldb(5, 1), OR(1, 0), exb(0, 6), shll8(6))
    W(ldb0(4, 1), mov(0, 1), ldb0(2, 1), OR(0, 1), ldb0(5, 1), OR(1, 0), exb(0, 0), OR(0, 6), shll8(6))
    W(ldb0(4, 2), mov(0, 1), ldb0(2, 2), OR(0, 1), ldb0(5, 2), OR(1, 0), exb(0, 0), OR(0, 6))
    W(mov(6, 1), shlr8(1), mov(6, 0), shll(0), shlr8(0), OR(0, 1), mov(6, 0), shlr(0), shlr8(0), OR(0, 1))
    W(ldb0(2, 1), exb(0, 7), 0x6077, AND(0, 1), exb(1, 1))   # r7 = 글자 · r1 = 테두리(= 팽창 & ~글자)
    W(mov(7, 0), shlr2(0), shlr2(0), ADD(0, 0), ldw_r0(12, 4), exw(4, 4), shll16(4))
    W(mov(7, 0), 0xC90F, ADD(0, 0), ldw_r0(12, 0), exw(0, 0), OR(0, 4))
    W(mov(4, 0), shll(0), OR(0, 4), mov(4, 0), shll2(0), OR(0, 4))   # 글자 니블 1 → 15(×15 = x|x<<1|x<<2|x<<3, 니블 안에서만)
    W(mov(1, 0), shlr2(0), shlr2(0), ADD(0, 0), ldw_r0(12, 5), exw(5, 5), shll16(5))
    W(mov(1, 0), 0xC90F, ADD(0, 0), ldw_r0(12, 0), exw(0, 0), OR(0, 5), OR(5, 4))
    W(0x2B42, addi(11, 4), addi(2, BSTR), dt(3)); a.br('bf', 'cyy')
    W(addi(14, 1), dt(13)); a.br('bf', 'cx')
    W(movi(0, BSTR * 2), shll2(0), ADD(0, 10), dt(9)); a.br('bf', 'cy')   # r0 = BSTR×8 (즉치 104 × 4)
    W(*[pop(r) for r in range(14, 7, -1)]); W(pop(1))
    # 지도
    W(0x8410, 0x600C, 0x6703)                             # r7 = w8
    W(0x8412, 0x600C, 0x6303, 0x4300)                     # r3 = c0*2
    a.ld(2, MAP + ROW * 128); W(0x323C)
    W(0x8411, 0x600C, 0x6503)                             # r5 = nrow
    a.ld(4, 0xF000 | CHAR_LO)
    a.L('row'); W(0x6023, 0x6673)
    a.L('col'); W(0x2041, 0x7002, 0x7401, 0x4610); a.br('bf', 'col')
    a.ld(0, 128); W(0x320C, 0x4510); a.br('bf', 'row')
    a.ld(1, SHADOW_PNCN2); W(0x6011, 0xCBE0, 0x2101)      # PNCN2 보충 비트 7 켬(지울 때 끔)
    W(0x4F26, 0x000B, 0x0009)
    # ---- clear ----
    # ★저장한 게 있을 때만: 지도 20‥23행 되돌림 + PNCN2 보충 비트 끔(사용자 «미션 제목·결과 화면 글자가 검은 상자» 2026-10-10)
    a.L('clear')
    a.ld(1, SHADOW_PNCN2); W(0x6011, 0xC880); a.br('bt', 'cdone')   # ★저장 표시 = PNCN2 보충 비트(그릴 때 켜고 지울 때 끔)
    a.ld(1, SAVE); a.ld(2, MAP + ROW * 128); a.ld(3, 128)
    a.L('crs'); W(0x6016, 0x2202, 0x7204, 0x4310); a.br('bf', 'crs')
    a.ld(1, SHADOW_PNCN2); W(0x6011, 0xCBE0, 0xCAE0, 0x2101)   # 보충 비트 5‥7 끔(or·xor)
    a.L('cdone'); W(0x000B, 0x0009)
    # ---- mirror : CRAM 사본 팔레트 0‥15(0‥511 B) → 보충 7 자리(+0xE00) · 그다음 127 의 1 = 검정(테두리)·15 = 흰색(글자) ----
    #   ★15 까지 비춤: 미션 제목 «Second Mission»이 팔레트 15(회색 단계, 1 검정·15 흰색)를 써서, 127 을 자막 전용으로 두면 검게 나왔다(2026-10-10)
    a.L('mirror')
    a.ld(1, CRAM_SH); a.ld(2, CRAM_SH + 0xE00); a.ld(3, 128)
    a.L('mrl'); W(0x6016, 0x2202, 0x7204, 0x4310); a.br('bf', 'mrl')
    # ★NBG2 켬(BGON 비트 2) — 컷신(0360 등)은 NBG2 를 끄고 자막만 안 보였다. 매 프레임 세우고, 자막 끝나면 게임 값으로 돌아감.
    #   단 VRAM 접근 주기 CYCB0U 가 FFFF(NBG2 몫 없음 — 메일 화면 등 고해상도)면 안 켬(켜면 쓰레기)
    a.ld(1, SHADOW_BGON - 0x10); W(0x8515, 0x88FF); a.br('bt', 'nbg')   # r1 = 사본+0x10 · @(10) = CYCB0U
    W(0x8518, 0xCB04, 0x8118)                             # @(16) = BGON |= 4
    a.L('nbg')
    W(0x72E0, 0xE080, 0x4018, 0x8121, 0xE0FF)           # r2 = 팔레트 127 · @(2) = 0x8000 · @(30) = 0xFFFF
    W(0x000B, 0x812F)                                     # 지연 칸
    # ---- stamp(r0 = 12비트 행, r2 = 버퍼 자리, r14 = x&7) : 3 바이트에 OR, r2 += 한 행 ----
    a.L('stamp')
    W(shll8(0), shll2(0), shll2(0), mov(14, 1), 0x2118); a.br('bt', 'sd')
    a.L('sl'); W(shlr(0), dt(1)); a.br('bf', 'sl')
    a.L('sd'); W(mov(0, 7), shlr16(0), ldb(2, 1), OR(1, 0), stb(0, 2))
    W(mov(7, 1), shlr8(1), ldb0(2, 1), OR(1, 0), stb0(2, 1))
    W(ldb0(2, 2), OR(7, 0), stb0(2, 2), 0x000B, addi(2, BSTR))   # 지연 칸
    # ---- 펼침 표: 4비트 → 네 니블(각 1) ----
    a.L('etab'); W(*[sum(((n >> (3 - i)) & 1) << (12 - 4 * i) for i in range(4)) for n in range(16)])
    code = a.build(); assert len(code) <= 1024, len(code)
    return code, a.lab


# ============ 번역표 ============
PUNCT = ',.!?:;)]}\'"~、。，．！？：；）］｝」』】…'
FIXES = os.path.join(ROOT, 'work', 'fixes.tsv')   # 검토 수정 표(id/*, 바꿀 글, 새 글) — 번역 파일은 그대로 두고 여기서 고침


def clean(ko):
    """부호 뒤 공백 지움(전프로젝트 규칙) · 겹공백 하나로 · 쪽 나눔 « | » 은 그대로"""
    if '받아쓰기 실패' in ko: return ''         # 내보내기 자리표가 번역 칸에 복사된 줄 — 자막으로 내보내지 말 것
    parts = []
    for part in ko.split('|'):
        t = re.sub(r'\s+', ' ', part).strip()
        t = re.sub('([%s]) +' % re.escape(PUNCT), r'\1', t)
        parts.append(t)
    return ' | '.join(p for p in parts if p)


def apply_fixes(raw):
    """fixes.tsv 를 «정리 전» 원문에 적용(부호 뒤 공백이 지워지기 전이라야 표의 글과 맞는다). 못 찾은 줄은 경고."""
    if not os.path.exists(FIXES): return
    for ln in open(FIXES, encoding='utf-8-sig'):
        if ln.startswith('#') or ln.startswith('id\t') or not ln.strip(): continue
        k, old, new = ln.rstrip('\r\n').split('\t')
        if old and ((old[-1:] == ' ') != (new[-1:] == ' ') or (old[:1] == ' ') != (new[:1] == ' ')):
            print('⚠수정 표: %s «%s» → «%s» 앞뒤 공백이 달라짐(띄어쓰기 사라짐)' % (k, old, new))   # 2026-10-10 «방금 그걸로격벽»
        if k == '*':
            for i in raw: raw[i] = raw[i].replace(old, new)
        elif old == '':
            raw[int(k)] = new                    # 빈 줄 채우기
        elif int(k) in raw and old in raw[int(k)]:
            raw[int(k)] = raw[int(k)].replace(old, new)
        else:
            print('⚠수정 표: %s «%s» 못 찾음' % (k, old))


def load_trans(dirs):
    """뒤 폴더가 앞 폴더를 덮는다: work/trans(내 표) → my files/번역(사용자 번역) → work/fixes.tsv 적용 → 정리"""
    raw = {}; src = {}
    for d in dirs:
        for p in sorted(glob.glob(os.path.join(d, '*.tsv'))):
            for ln in open(p, encoding='utf-8-sig'):
                c = ln.rstrip('\r\n').split('\t')
                if len(c) >= 5 and c[0].isdigit() and c[4].strip():
                    raw[int(c[0])] = c[4]; src[int(c[0])] = os.path.basename(p); JA[int(c[0])] = c[3]
    apply_fixes(raw)
    T = {k: clean(v) for k, v in raw.items()}
    apply_turns(T)
    # ★구출 «좌표 세트»(대원) 다음 «(전송) 좌표 확인…»(크리스)은 화자가 다르다 — 그 사이를 쪽 나눔(사용자 2026-10-10). 쉼표면 마침표로
    for k in T:
        T[k] = clean(re.sub(r'좌표 세트[.!,]?\s*(?!\|)(?=(?:전송 )?좌표 확인)',
                            lambda m: m.group(0).rstrip(' ,').rstrip('.!') + ('!' if '!' in m.group(0) else '.') + ' | ', T[k]))
    return {k: v for k, v in T.items() if v}, src


TURNS = os.path.join(ROOT, 'work', 'turns.tsv')


def apply_turns(T):
    """work/turns.tsv — 화자 바뀌는 곳에 쪽 나눔 « | » (2026-10-10). « | »·공백을 빼고 «,»=«.» 로 본 글이 번역과 같을 때만 덮어씀.
       쪽마다 문장 끝 부호로 끝나야 쪽 시각(문장 수 기준)이 안 겹친다 — 아니면 경고."""
    if not os.path.exists(TURNS): return
    norm = lambda t: re.sub(r'[\s|]', '', t).replace(',', '.')
    n = 0
    for ln in open(TURNS, encoding='utf-8-sig'):
        if ln.startswith('#') or ln.startswith('id\t') or not ln.strip(): continue
        k, new = ln.rstrip('\r\n').split('\t'); k = int(k)
        if k not in T: print('⚠쪽 나눔 표: %04d 번역 없음' % k); continue
        if norm(new) != norm(T[k]):
            print('⚠쪽 나눔 표: %04d 글이 번역과 다름 — 건너뜀' % k); continue
        new = clean(new)
        for part in new.split('|'):
            if part.strip()[-1:] not in G.END: print('⚠쪽 나눔 표: %04d 쪽 끝 부호 없음: %s' % (k, part.strip()))
        T[k] = new; n += 1
    print('쪽 나눔 표 %d줄 적용' % n)


ASRW = None
JA = {}                                       # id → 일본어(받아쓰기) — 낱말 시각이 원문을 얼마나 덮는지 보는 데
MIN_PAGE = 0.8                                # 쪽 최소 표시 초


def page_starts(k, pages, nsmp, rate):
    """쪽 시작 샘플 — 위스퍼 낱말 시각(work/asr_words.json)으로 (2026-10-10 사용자 «다음 자막 전에 너무 빨리 사라짐»)
       한국어 문장 수 == 일본어 문장 수 → 쪽 첫 문장의 일본어 문장 시작 · 아니면 글자 비율 → 일본어 글자 시각"""
    global ASRW
    if ASRW is None:
        pth = os.path.join(ROOT, 'work', 'asr_words.json')
        ASRW = json.load(open(pth, encoding='utf-8')) if os.path.exists(pth) else {}
    words = ASRW.get(str(k), [])
    if len(pages) <= 1: return None
    jc = len(re.sub(r'\W', '', JA.get(k, ''))); wc = sum(len(re.sub(r'\W', '', w)) for w, _ in words)
    if not words or (jc and wc < 0.7 * jc):     # 낱말 시각이 원문의 70% 도 못 덮음(0987: 끝 13자만) → 클립 전체를 한국어 글자 비율로
        kl = [len(''.join(p).replace(' ', '')) for p in pages]; kt = max(1, sum(kl))
        sec = [nsmp / rate * sum(kl[:i]) / kt for i in range(len(pages))]
        return _min_page(sec, nsmp, rate)
    ends = '。！？!?…'
    jst = [words[0][1]] + [w[1] for a, w in zip(words, words[1:]) if a[0].rstrip()[-1:] in ends]
    ksent = [sum(1 for w, _ in G.tokens(' '.join(p)) if w[-1:] in G.END) for p in pages]
    tot = sum(ksent)
    if tot == len(jst):
        sec = [jst[sum(ksent[:i])] for i in range(len(pages))]
    else:
        tl = []                                                     # 일본어 글자마다 시각
        for i, (w, t0) in enumerate(words):
            t1 = words[i + 1][1] if i + 1 < len(words) else t0 + 0.15 * len(w)
            cs = [c for c in w if c.strip()]
            tl += [t0 + (t1 - t0) * j / max(1, len(cs)) for j in range(len(cs))]
        kl = [len(''.join(p).replace(' ', '')) for p in pages]; kt = max(1, sum(kl))
        sec = [tl[min(len(tl) - 1, int(len(tl) * sum(kl[:i]) / kt))] for i in range(len(pages))]
    sec[0] = 0.0
    return _min_page(sec, nsmp, rate)


def _min_page(sec, nsmp, rate):
    out = []; prev = 0
    for t in sec:
        v = max(prev, min(int(t * rate), nsmp - 1)); out.append(v); prev = v
    # ★쪽마다 최소 표시 시간(화자별로 짧게 나눈 쪽이 0초로 묻히지 않게 — 2026-10-10 사용자 «짧게 끊어지는 대사 표시 시간»)
    #   앞→뒤: 앞 쪽 + MIN 이후로 밀기 · 뒤→앞: 다음 쪽(마지막은 음성 끝) − MIN 이전으로 당기기. 클립이 MIN×쪽 수보다 짧으면 고르게.
    m = int(MIN_PAGE * rate); n = len(out)
    if m * n > nsmp: m = nsmp // n
    for i in range(1, n): out[i] = max(out[i], out[i - 1] + m)
    nxt = nsmp
    for i in range(n - 1, 0, -1): out[i] = min(out[i], nxt - m); nxt = out[i]
    return out


KIND = {}


def bank_plan(T, acx, E):
    """★공용 글꼴 계획(2026-10-10): 묶음이 머리 2,048 B(ROOM)를 넘는 클립은 주인공 길(쇼/티리스)별 공용 글꼴을 «쓰고»,
       같은 길의 작은 미션 무전들이 그 공용 글꼴을 머리에 «싣는다»(어느 하나만 먼저 나와도 VRAM 에 올라감).
       4,096 B 머리는 미션 중 앞 2,048 B 만 와 있는 채 해독돼 묶음이 깨지고 게임이 멈췄다(0305 실기).
       → {id: ('use', 글자 목록, 위치) | ('carry', 공용 글꼴 바이트, 위치)}"""
    if not KIND:
        for p in glob.glob(os.path.join(ROOT, 'my files', '번역', 'br*.tsv')):
            for ln in open(p, encoding='utf-8-sig'):
                c = ln.rstrip('\r\n').split('\t')
                if c[0].isdigit() and len(c) > 1: KIND[int(c[0])] = c[1]
    def args(k):
        o = E[k][0]; clip = acx[o:o + 32]
        nsmp, rate = struct.unpack_from('>I', clip, 12)[0], struct.unpack_from('>I', clip, 8)[0]
        return nsmp, page_starts(k, G.pages_of(T[k]), nsmp, rate)
    size = lambda k, bank=None: len(G.pack(T[k], *args(k), bank=bank)[0])
    big = [k for k in T if size(k) > ROOM]
    paths = {}
    for k in big:
        kd = KIND.get(k, '')
        assert kd.startswith('미션무전_'), ('미션 무전 아닌 큰 클립', k, kd)
        paths.setdefault(kd, []).append(k)
    plan = {}; off = 0
    for kd, ks in sorted(paths.items()):
        bank = []
        while True:
            ov = [k for k in ks if size(k, bank) > ROOM]
            if not ov: break
            cnt = {}
            for k in ov:
                for c in sorted(set(T[k])):
                    if c.strip() and c != '|' and c not in bank: cnt[c] = cnt.get(c, 0) + sum(c in T[j] for j in ks)
            bank.append(max(sorted(cnt), key=lambda c: (cnt[c], c)))   # ★동점은 글자 순 — 빌드마다 같게(집합 순서는 실행마다 다름)
        bb = G.bank_bytes(bank)
        car = [k for k in T if KIND.get(k) == kd and k not in ks and size(k) + len(bb) <= ROOM]
        for k in ks: plan[k] = ('use', bank, off)
        for k in car: plan[k] = ('carry', bb, off)
        print('공용 글꼴 %s: %d자 %d B @%d×256 · 쓰는 클립 %s · 싣는 클립 %d개(첫 %s)' % (
            kd, len(bank), len(bb), off, ' '.join('%04d' % k for k in sorted(ks)), len(car), ' '.join('%04d' % k for k in sorted(car)[:6])))
        off += (len(bb) + 255) // 256
    assert off * 256 <= 0x2000
    return plan


def main():
    dirs = [os.path.join(ROOT, 'work', 'trans'), os.path.join(ROOT, 'my files', '번역')]
    if '--trans' in sys.argv: dirs = [sys.argv[sys.argv.index('--trans') + 1]]
    T, src = load_trans(dirs)
    miss = sorted({ch for t in T.values() for ch in t if ch not in ' |' and not any(G.glyph(ch))})
    if miss: print('⚠글꼴에 없는 글자(빈칸으로 나옴):', ' '.join('%s(U+%04X)' % (c, ord(c)) for c in miss))
    if '--stress' in sys.argv:
        for ln in open(os.path.join(ROOT, 'work', 'asr.tsv'), encoding='utf-8'):
            k, sec, ja = ln.rstrip('\n').split('\t')
            n = len(re.sub(r'\s', '', ja)); T[int(k)] = ' '.join('가나다라마' for _ in range(max(1, n // 5)))
    os.makedirs(os.path.join(ROOT, 'work', 'pv'), exist_ok=True)
    acx = open(os.path.join(ROOT, 'work', 'iso', 'ADX.ACX'), 'rb').read()
    n = struct.unpack_from('>I', acx, 4)[0]
    E = [struct.unpack_from('>II', acx, 8 + 8 * i) for i in range(n)]
    first = E[0][0]; out = bytearray(first); ents = []; over = []; sizes = []; n_small = 0
    plan = bank_plan(T, acx, E)
    for k, (o, s) in enumerate(E):
        clip = acx[o:o + s]; off = struct.unpack_from('>H', clip, 2)[0]
        assert clip[off - 2:off + 4] == b'(c)CRI' and off == 32
        if k not in T:                           # 자막 없는 클립은 원본 그대로(머리 32 B)
            ents.append((len(out), len(clip))); out += clip; out += bytes(-len(out) % 2048); continue
        nsmp, rate = struct.unpack_from('>I', clip, 12)[0], struct.unpack_from('>I', clip, 8)[0]
        pg = G.pages_of(T[k]); st = page_starts(k, pg, nsmp, rate); how = plan.get(k)
        if how and how[0] == 'use':
            pay = G.pack(T[k], nsmp, st, bank=how[1], bank_off=how[2])[0]
        elif how and how[0] == 'carry':
            pay = G.pack(T[k], nsmp, st, carry=len(how[1]) // 16, bank_off=how[2])[0] + how[1]
        else:
            pay = G.pack(T[k], nsmp, st)[0]
        pages = pg
        sizes.append(len(pay))
        # ★머리는 되도록 2,048 B — 4,096 B 머리는 «크리스!» 뒤 곧바로 이어지는 대답에서 지직(사용자 2026-10-10, 버퍼 덜 찬 채 해독 추정)
        hdr = SMALL_HDR
        n_small += hdr == SMALL_HDR
        body = bytearray(hdr - 6 - 0x20)
        if len(pay) > ROOM: over.append((k, len(pay), len(pages)))
        else: body[:len(pay)] = pay
        c = bytearray(clip[:0x20]) + body + clip[off - 2:]; c[0x1E:0x20] = b'\0\0'
        struct.pack_into('>H', c, 2, hdr - 4)
        ents.append((len(out), len(c))); out += c; out += bytes(-len(out) % 2048)
    struct.pack_into('>II', out, 0, 0, n)
    for i, (o, s) in enumerate(ents):
        struct.pack_into('>II', out, 8 + 8 * i, o, s)
    out[8 + 8 * n:first] = acx[8 + 8 * n:first]
    print('머리 2,048 B: %d개 · 4,096 B: %d개' % (n_small, len(sizes) - n_small))
    print('자막 %d개 · 묶음 평균 %d B · 최대 %d B (자리 %d) · 넘침 %d' % (len(sizes), sum(sizes) // max(1, len(sizes)), max(sizes or [0]), ROOM, len(over)))
    for k, L, p in over[:20]:
        print('  ⚠넘침 %04d %d B (%d쪽) — 번역을 줄이거나 쪽을 줄일 것' % (k, L, p))
    code, lab = hooks()
    print('훅 %d B (자리 1024)' % len(code))
    if '--write' not in sys.argv or over:
        print('[미리보기]' + (' 넘침이 있어 기록 안 함' if over and '--write' in sys.argv else ''))
        return
    write_disc(out, code, lab)


def bcd(v): return (v // 10) << 4 | v % 10


def new_sector(lba, data):
    m = lba + 150; s = bytearray(2352)
    s[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'; s[12:16] = bytes([bcd(m // 4500), bcd(m // 75 % 60), bcd(m % 75), 1])
    s[16:2064] = data.ljust(2048, b'\0'); return cdmode1.fix(s)


def write_disc(out, code, lab):
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
    assert struct.unpack_from('>I', exe, EXEC_LIT)[0] == EXEC; struct.pack_into('>I', exe, EXEC_LIT, lab['frame'])
    exe += code
    rsec = lambda l: (f.seek(l * 2352), bytearray(f.read(2352)))[1]
    def wsec(l, s): cdmode1.fix(s); f.seek(l * 2352); f.write(s)
    for k in range(0, len(exe), 2048):
        s = rsec(EXE_LBA + k // 2048); s[16:2064] = bytes(exe[k:k + 2048]).ljust(2048, b'\0'); wsec(EXE_LBA + k // 2048, s)
    put = {}
    for nm, lba, secs, path in INPLACE:
        if not os.path.exists(path): continue
        if nm.endswith(b'.CAK') and '--movie' not in sys.argv: continue      # 동영상은 --movie 일 때만
        d = open(path, 'rb').read(); assert len(d) <= secs * 2048, (nm, '원래 섹터를 넘침')
        for k in range(secs):
            sc = rsec(lba + k); sc[16:2064] = d[k * 2048:k * 2048 + 2048].ljust(2048, b'\0'); wsec(lba + k, sc)
        put[nm] = (lba, len(d))
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
            if nm in put:
                assert struct.unpack_from('<I', s, i + 2)[0] == put[nm][0]
                struct.pack_into('<I', s, i + 10, put[nm][1]); struct.pack_into('>I', s, i + 14, put[nm][1]); got.add(nm)
            i += s[i]
        wsec(rl + k, s)
    assert got == {b'ADX.ACX', b'0.BIN'} | set(put)
    f.close()
    print('기록: ADX.ACX %d B @LBA %d · 0.BIN %d B%s → %s' % (len(out), new_lba, len(exe), ''.join(' · %s %d B' % (k.decode(), v[1]) for k, v in put.items()), OUT))


if __name__ == '__main__':
    main()
