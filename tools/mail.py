# -*- coding: utf-8 -*-
"""메일 183통 한글화 (2026-10-10 준비) — MAIL.BIN(PRS, 모듈 0x06078000) 본문 + ZENFONT.FNT(PRS, 16×16 1비트 3,952자)
   본문: 모듈 +0x4B4C 주소표 183개 → SJIS 문자열(«\» = 줄바꿈, 0 끝). 영역 +0x4E28‥+0x109C3.
   글꼴 번호: 0x81‥0x84 = (앞−0x81)×192 + (뒤−0x40) · 0x88‥0x98 = 688 + (앞−0x88)×192 + (뒤−0x40) (메일 화면 15자로 검산)
   한글 = 한자 칸(0x889F‥, 올바른 SJIS 둘째 바이트만)에 차례로 배정, 부호·숫자·영문은 원래 전각 칸을 그대로.
   번역: my files/번역/mail*.tsv 또는 work/trans/mail_*.tsv (id · ja · ko), ko 안 «\» = 줄바꿈.
   검사(쓰는 순간): 한 줄 반 칸 64개 이하(한글·전각 2, 반각 공백 1) · 11줄 이하 · 글꼴에 없는 글자.
   ★반각 띄어쓰기(2026-10-10): 원래 그리기(0x06078F24 일반·0x06078FC0 반전)는 16×16 타일(8×8 셀 4개, TL·TR·BL·BR 순 128 B)을
     한 글자씩 찍는다. 두 함수 머리를 새 함수(본문 영역 끝)로 돌려, 바이트 0x20 = 셀 하나(8px)만 전진하고
     그 뒤 글자는 «오른쪽 반 = 다음 타일 TL»로 반 칸 어긋나게 찍는다. 원문엔 0x20 이 없어서 다른 문자열은 그대로.
   python tools/mail.py [--test] [--pack]   --test = 번역 대신 시험 문장 · --pack = work/MAIL_kr.BIN·ZENFONT_kr.FNT"""
import glob, os, re, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import prs

MAIL_LBA, MAIL_SIZE, MAIL_SECS = 7753, 33434, 17
FONT_LBA, FONT_SIZE, FONT_SECS = 6666, 74558, 37
BASE, TAB, N = 0x06078000, 0x4B4C, 183
TXT0, TXT1 = 0x4E28, 0x109C4                 # 본문 영역(끝 0 포함)
MAXCOL, MAXROW = 32, 11
MAXW = MAXCOL * 2                            # 반 칸 단위 줄 폭
DRAW, DRAWINV = 0x06078F24, 0x06078FC0      # 원래 그리기 함수(일반·반전)
LEAD_TAB, LUT, VRAM0 = 0x06079A80, 0x06079680, 0x25E40000
FONT_RAM, SPILL0 = 0x00200000, 3600 * 32     # ZENFONT 이 실리는 자리 · 넘친 메일을 둘 글꼴 끝(3600번 칸‥, 11 KB) — 한자 칸은 어차피 전부 덮어씀
BS = 0x5C
KFONT = ImageFont.truetype(r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri.ttc', 15, index=0)   # Galmuri14 — 판정은 사용자


def disc(lba, size):
    return open(os.path.join(ROOT, 'work', 'track1_user.bin'), 'rb').read()[lba * 2048:lba * 2048 + size]


def fidx(code):
    a, b = code >> 8, code & 0xFF
    if 0x81 <= a <= 0x84: return (a - 0x81) * 192 + b - 0x40
    if 0x88 <= a <= 0x98: return 688 + (a - 0x88) * 192 + b - 0x40
    return None


def kanji_slots():
    for a in range(0x88, 0x99):
        for b in list(range(0x40, 0x7F)) + list(range(0x80, 0xFD)):
            if (a, b) < (0x88, 0x9F): continue
            yield a << 8 | b


def zen(ch):
    """한글 아닌 글자 → 원래 글꼴에 있는 SJIS(반각은 전각으로)"""
    if '!' <= ch <= '~': ch = chr(ord(ch) + 0xFEE0)
    ch = {'…': '…', '·': '・', '~': '～', '-': '－', '＇': '’', '＂': '”'}.get(ch, ch)   # 전각 ' " 는 IBM 확장(글꼴 밖) → 따옴표 기호로
    try: b = ch.encode('cp932')
    except UnicodeEncodeError: return None
    return b[0] << 8 | b[1] if len(b) == 2 else None


def load_ko(test=False):
    o = prs.decompress(disc(MAIL_LBA, MAIL_SIZE))[0]
    ja = []
    for k in range(N):
        t = struct.unpack_from('>I', o, TAB + 4 * k)[0] - BASE
        ja.append(o[t:o.index(b'\0', t)].decode('cp932'))
    if test:
        return o, ja, {k: '시험 메일 %d번이야.\\버닝 레인저 여러분, 구해 줘서 고마워요!\\\\다음에 또 만나요~' % k for k in range(N)}
    ko = {}
    for p in sorted(glob.glob(os.path.join(ROOT, 'my files', '번역', 'mail*.tsv'))) or sorted(glob.glob(os.path.join(ROOT, 'work', 'trans', 'mail_*.tsv'))):
        for ln in open(p, encoding='utf-8-sig'):
            c = ln.rstrip('\r\n').split('\t')
            if len(c) >= 3 and c[0].isdigit() and c[2].strip(): ko[int(c[0])] = c[2]
    return o, ja, ko


FIXES = os.path.join(ROOT, 'work', 'mail_fixes.tsv')
QUOTE = re.compile(r'''「[^」]*」|『[^』]*』|“[^”]*”|‘[^’]*’|"[^"]*"|'[^'\\]*\'''')   # 괄호·따옴표 쌍(원문처럼 줄을 넘을 수 있음, ' 만 줄 안)


def apply_fixes(ko):
    """work/mail_fixes.tsv (id|* · 바꿀 글|* · 새 글) — 번역 파일은 그대로 두고 여기서 고친다"""
    errs = []
    if not os.path.exists(FIXES): return errs
    for ln in open(FIXES, encoding='utf-8-sig'):
        c = ln.rstrip('\r\n').split('\t')
        if len(c) < 3 or ln.startswith('#') or c[0] == 'id': continue
        ids = sorted(ko) if c[0] == '*' else [int(c[0])]
        hit = 0
        for k in ids:
            if k not in ko: continue
            if c[1] == '*': ko[k] = c[2]; hit += 1
            elif c[1] in ko[k]: ko[k] = ko[k].replace(c[1], c[2]); hit += 1
        if not hit: errs.append('수정 표: %s 에서 %r 못 찾음' % (c[0], c[1]))
    return errs


def blank_rows(t):
    return sum(1 for r in t.rstrip('\\').split('\\') if not r.strip('　 '))


def restore_tokens(ja, ko):
    """★원문 토큰(「」『』·빈 줄) — 번역이 '…' \"…\" “…” 로 바꾼 괄호를 원문 순서대로 되돌리고, 모자라면 실패"""
    errs = []
    for k, t in ko.items():
        want = re.findall('[「『]', ja[k])
        got = list(QUOTE.finditer(t))
        if [m.group(0)[0] for m in got] != want:
            if len(got) == len(want):
                out = []; last = 0
                for m, b in zip(got, want):
                    out += [t[last:m.start()], b, m.group(0)[1:-1], '」' if b == '「' else '』']; last = m.end()
                ko[k] = t = ''.join(out) + t[last:]
            else:
                errs.append('%03d 괄호 원문 %s ↔ 번역 %s' % (k, ''.join(want), ''.join(m.group(0)[0] for m in got)))
        if blank_rows(t) < blank_rows(ja[k]):
            errs.append('%03d 빈 줄 원문 %d ↔ 번역 %d' % (k, blank_rows(ja[k]), blank_rows(t)))
    return errs


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
                d = la[a[1]] - ((pc & ~3) + 4); assert 0 <= d and d % 4 == 0 and d // 4 < 256; s.c[i] = 0xD000 | a[0] << 8 | d // 4
            else:
                d = (s.lab[a] - (pc + 4)) // 2
                if op in ('bra', 'bsr'): assert -2048 <= d < 2048; s.c[i] = (0xA000 if op == 'bra' else 0xB000) | (d & 0xFFF)
                else: assert -128 <= d < 128, (op, a, d); s.c[i] = {'bt': 0x8900, 'bf': 0x8B00, 'bts': 0x8D00, 'bfs': 0x8F00}[op] | (d & 0xFF)
        return b''.join(struct.pack('>H', x) for x in s.c) + b''.join(struct.pack('>I', v) for v in vals)


def half_code(base):
    """새 그리기(r4 = 열(16px), r5 = 줄, r6 = 문자열). r0·r2‥r8 은 원래도 망가뜨림, ★r1·r9‥r13 은 저장(r1 망가뜨리면 메일 번호가 틀어짐 2026-10-10 실기).
       r5 = 셀 쓰는 자리 · r8 = 줄 머리 · r9 = 반 칸 어긋남(0/1) · r10 = 오른쪽 반까지 거리(32 / 96) · r13 = 반전 xor"""
    a = A(base); W = a.w
    a.L('inv'); W(0x2FD6, 0xEDFF); a.br('bra', 'go'); W(0x0009)       # push r13 · r13 = −1
    a.L('norm'); W(0x2FD6, 0xED00)                                    # push r13 · r13 = 0
    a.L('go'); W(0x2F16, 0x2F96, 0x2FA6, 0x2FB6, 0x2FC6)              # push r1·r9‥r12 (★r1 = 호출자의 작업 구조체 — 원래 그리기는 안 건드림)
    W(0x4508, 0x4508, 0x4500, 0x354C, 0x4518, 0x4501)                 # r5 = ((줄×32+열)<<8)>>1  (원래와 같음)
    a.ld(0, VRAM0); W(0x350C)
    a.ld(4, LEAD_TAB); a.ld(7, LUT); a.ld(2, 0x00200000)
    W(0x6853, 0xE900)                                                 # r8 = r5 · r9 = 0
    a.L('next'); W(0x6064, 0x2008); a.br('bt', 'done')                # r0 = *r6++ · 0 → 끝
    W(0x600C, 0x8820); a.br('bt', 'half')                             # 0x20 = 반 칸
    W(0x7080, 0x70FF, 0x4011); a.br('bf', 'nl')                       # r0 = 앞 − 0x81 · < 0 → 줄바꿈(원래처럼)
    W(0x6364, 0x633C, 0x8807); a.br('bfs', 'l1'); W(0x73C0); W(0x73B0)   # 뒤 바이트 − 0x40 (0x88 줄은 − 0x50 더)
    a.L('l1'); W(0x4000, 0x004D, 0x330C)                              # r3 = 글꼴 번호
    W(0x4308, 0x4308, 0x4300, 0x332C)                                 # r3 = 0x200000 + 번호×32
    W(0xEA20, 0x2998); a.br('bt', 'l2'); W(0xEA60)                    # r10 = r9 ? 96 : 32
    a.L('l2'); W(0x6153, 0xEB02)                                      # r1 = r5 · 반쪽 2개
    a.L('hh'); W(0xEC08)
    a.L('row')
    W(0x6034, 0x20DA, 0x600C, 0x4008, 0x007E, 0x2102)                 # 왼쪽 바이트 → @r1
    W(0x6034, 0x20DA, 0x600C, 0x4008, 0x007E, 0x31AC, 0x2102, 0x31A8) # 오른쪽 바이트 → @(r1+r10)
    W(0x4C10); a.br('bfs', 'row'); W(0x7104)
    W(0x7120, 0x4B10); a.br('bf', 'hh')                               # 아래 반: r1 = 자리+64
    W(0x7540, 0x7540); a.br('bra', 'next'); W(0x0009)                 # 다음 글자: +128
    a.L('half'); W(0x2998); a.br('bf', 'hodd')
    W(0xE901); a.br('bra', 'next'); W(0x7520)                         # 짝 → 홀: TR 셀(+32)
    a.L('hodd'); W(0xE900, 0x7540); a.br('bra', 'next'); W(0x7520)    # 홀 → 짝: 다음 타일 TL(+96)
    a.L('nl'); a.ld(0, 0x1000); W(0x380C, 0x6583, 0xE900); a.br('bra', 'next'); W(0x0009)
    a.L('done'); W(0x6CF6, 0x6BF6, 0x6AF6, 0x69F6, 0x61F6, 0x6DF6, 0x000B, 0x0009)
    code = a.build()
    return code, a.lab['norm'], a.lab['inv']


def jmp_stub(at, to):
    """at 에 mov.l @(lit),r0 · jmp @r0 · nop (+정렬) · lit"""
    lit = ((at + 4) & ~3) + 4                     # disp 1
    b = struct.pack('>HHH', 0xD001, 0x402B, 0x0009)
    b += b'\x00\x09' * ((lit - at - 6) // 2) + struct.pack('>I', to)
    return b


def width(row):
    return sum(1 if ch == ' ' else 2 for ch in row)


def glyph(ch):
    im = Image.new('L', (16, 16), 0); dr = ImageDraw.Draw(im); dr.fontmode = '1'
    dr.text((8, 8), ch, font=KFONT, fill=255, anchor='mm')
    a = np.array(im) > 0
    return b''.join(struct.pack('>H', int(''.join('1' if x else '0' for x in r), 2)) for r in a)


def fit(rows):
    """32자 넘는 줄: 앞 전각 공백(오른쪽 붙임)이면 공백을 줄이고, 아니면 띄어쓰기 자리에서 다음 줄로 넘김(번역은 안 깎음)"""
    out = []
    for r in rows:
        if width(r) <= MAXW: out.append(r); continue
        body = r.lstrip('　 ')
        if len(body) < len(r) and width(body) <= MAXW:
            out.append('　' * ((MAXW - width(body)) // 2) + body); continue
        r = body
        while width(r) > MAXW:
            n = 0; w = 0
            while w + width(r[n]) <= MAXW: w += width(r[n]); n += 1
            cut = r.rfind(' ', 0, n + 1)
            if cut <= 0: cut = n
            out.append(r[:cut].rstrip()); r = r[cut:].lstrip()
        out.append(r)
    return out


def build(test=False):
    o, ja, ko = load_ko(test)
    errs = [] if test else apply_fixes(ko) + restore_tokens(ja, ko)
    font = bytearray(prs.decompress(disc(FONT_LBA, FONT_SIZE))[0])
    syl = sorted({c for t in ko.values() for c in t if '가' <= c <= '힣'})
    slots = list(kanji_slots()); assert len(syl) <= len(slots), ('한글이 칸보다 많음', len(syl))
    code = {c: s for c, s in zip(syl, slots)}
    for c, s in code.items():
        i = fidx(s); font[i * 32:i * 32 + 32] = glyph(c)
    enc = {}
    for k in range(N):
        t = ko.get(k)
        if t is None: enc[k] = ja[k].encode('cp932'); continue
        t = re.sub('([,.!?…~:;)\\]}」』]) +', r'\1', t)        # 부호 뒤 공백 지움(전프로젝트 규칙)
        out = bytearray(); rows = fit(t.split('\\'))
        nrow = len(rows) - (rows[-1] == '')          # 끝 «\» 뒤 빈 줄은 줄로 안 셈(원문도 11줄 + 끝 «\»)
        if nrow > MAXROW: errs.append('%03d 줄 %d개(최대 %d)' % (k, nrow, MAXROW))
        for r, row in enumerate(rows):
            if width(row) > MAXW: errs.append('%03d %d번째 줄 반 칸 %d개(최대 %d): %s' % (k, r + 1, width(row), MAXW, row))
            if r: out.append(BS)
            for ch in row:
                if ch == ' ': out.append(0x20); continue
                cd = code.get(ch) or zen(ch)
                if cd is None or fidx(cd) is None: errs.append('%03d 글꼴에 없는 글자 %r' % (k, ch)); continue
                out += struct.pack('>H', cd)
        enc[k] = bytes(out)
    o = bytearray(o); pos = TXT0; spill = SPILL0; nsp = 0
    hc = (TXT1 - 0x200) & ~3; hcode, ent, ent_inv = half_code(BASE + hc)   # 새 그리기 = 본문 영역 끝
    assert hc + len(hcode) <= TXT1, len(hcode)
    o[hc:hc + len(hcode)] = hcode; txt_end = hc
    for at, to in ((DRAW, ent), (DRAWINV, ent_inv)):
        st = jmp_stub(at, to); o[at - BASE:at - BASE + len(st)] = st
    assert max(fidx(s) for s in code.values()) * 32 + 32 <= SPILL0, '한글 칸이 넘침 자리까지 옴'
    for k in range(N):
        b = enc[k] + b'\0'
        if pos + len(b) <= txt_end:
            struct.pack_into('>I', o, TAB + 4 * k, BASE + pos); o[pos:pos + len(b)] = b; pos += len(b)
        else:                                   # ★원래 영역에 안 들어가면 글꼴 끝 빈 칸(메일 화면에서 Low RAM 0x200000 에 실림)으로
            if spill + len(b) > len(font): errs.append('%03d 넘침 자리도 모자람' % k); continue
            struct.pack_into('>I', o, TAB + 4 * k, FONT_RAM + spill); font[spill:spill + len(b)] = b; spill += len(b); nsp += 1
    o[pos:txt_end] = bytes(txt_end - pos)
    print('  새 그리기 %d B @%08X · 본문 %d/%d B' % (len(hcode), BASE + hc, pos - TXT0, txt_end - TXT0))
    if nsp: print('  원래 영역에 못 넣은 메일 %d통 → 글꼴 끝 빈 칸(%d B)' % (nsp, spill - SPILL0))
    return bytes(o), bytes(font), enc, code, errs


def preview(o, font, k, out='mail_pv.png'):
    """메일 k 를 글꼴로 찍어 보기 → work/<out>"""
    t = struct.unpack_from('>I', o, TAB + 4 * k)[0] - BASE; b = o[t:o.index(b'\0', t)]
    im = np.zeros((16 * MAXROW, 16 * MAXCOL), np.uint8); x = y = 0; i = 0
    while i < len(b):                            # x = 반 칸(8px) 단위
        if b[i] == BS: y += 1; x = 0; i += 1; continue
        if b[i] == 0x20: x += 1; i += 1; continue
        c = b[i] << 8 | b[i + 1]; i += 2; g = fidx(c)
        if g is not None and y < MAXROW and x < MAXW - 1:
            rows = struct.unpack('>16H', font[g * 32:g * 32 + 32])
            for r, v in enumerate(rows):
                for cx in range(16):
                    if v >> (15 - cx) & 1: im[y * 16 + r, x * 8 + cx] = 255
        x += 2
    rgb = np.dstack([np.where(im, 0, 0), np.where(im, 0, 90), np.where(im, 0, 40)]).astype(np.uint8)
    rgb[im > 0] = (0, 0, 0)
    Image.fromarray(rgb).resize((im.shape[1] * 2, im.shape[0] * 2), Image.NEAREST).save(os.path.join(ROOT, 'work', out))


if __name__ == '__main__':
    test = '--test' in sys.argv
    o, font, enc, code, errs = build(test)
    print('번역 %d통 · 한글 %d자(한자 칸 %d개 중) · 본문 %d B' % (len([k for k in enc]), len(code), len(list(kanji_slots())), sum(len(v) + 1 for v in enc.values())))
    for e in errs[:30]: print('  ⚠' + e)
    preview(o, font, 0)
    if '--pack' in sys.argv and not errs:
        for nm, d, room in (('MAIL_kr.BIN', o, MAIL_SECS * 2048), ('ZENFONT_kr.FNT', font, FONT_SECS * 2048)):
            c = prs.compress(d); assert prs.decompress(c)[0] == d
            open(os.path.join(ROOT, 'work', nm), 'wb').write(c)
            print('%s 압축 %d B (자리 %d B)%s' % (nm, len(c), room, '  ⚠자리 넘침 → 디스크 끝으로 옮겨야 함' if len(c) > room else ''))
