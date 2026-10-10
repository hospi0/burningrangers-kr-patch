# -*- coding: utf-8 -*-
"""SUB4 묶음 — 클립별 글꼴 조각(갈무리11, 1비트 16×12) + 쪽마다 글자 위치. 게임 코드가 찍고 테두리 계산 (2026-10-10)
   묶음:  +0 'SUB4' · +4 u32 끝 샘플 · +8 u16 쪽 수 · +10 u16 묶음 길이 · +12 u16 글꼴 자리 · +14 0
          +16 쪽 표[쪽 수] (u32 시작 샘플, u32 쪽 자리)
   쪽:    u8 w8 · u8 nrow · u8 c0 · u8 글자 수 · 글자마다 3 B (글꼴 번호, x 하위 8비트, x 9번째 비트 | 줄<<1)
   글꼴:  글자마다 12행 × 12비트(두 행 = 3 B, 앞 행이 위 12비트, 비트 11 = 왼쪽 끝) = 18 B — 원래 글꼴의 1‥12행
   그림 규칙(게임 코드와 같아야 함): 쪽 버퍼 폭 48 B·높이 nrow*8, 줄 i 글꼴 r행 → y = i*16 + 3 + r, x = 글자 x.
     테두리 = 3×3 팽창 − 글자. 색 2 = 글자, 1 = 테두리, 0 = 투명."""
import struct
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = ImageFont.truetype(r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.ttf', 12)
MAXW = 320; COLS = 44; STRIDE = 48
_d = ImageDraw.Draw(Image.new('L', (1, 1)))
_cache = {}


def adv(ch):
    return int(round(_d.textlength(ch, font=FONT)))


def glyph(ch):
    if ch not in _cache:
        im = Image.new('L', (16, 16), 0); dr = ImageDraw.Draw(im); dr.fontmode = '1'; dr.text((0, 0), ch, font=FONT, fill=255)
        a = np.array(im) > 0
        rows = [int(''.join('1' if a[y, x] else '0' for x in range(16)), 2) for y in range(1, 13)]
        _cache[ch] = rows
    return _cache[ch]


def width(s):
    return sum(adv(c) for c in s)


END = '.!?…~」』)'


def tokens(t):
    """줄을 끊을 수 있는 조각: 공백 자리(공백은 버림) + 부호 뒤(공백을 지운 자리) — [(조각, 앞 구분자)]"""
    out = []; cur = ''; sep = ''
    for i, ch in enumerate(t):
        if ch == ' ':
            if cur: out.append((cur, sep)); cur = ''
            sep = ' '; continue
        cur += ch
        if ch in END + ',' and i + 1 < len(t) and t[i + 1] not in ' ' + END + ',':
            out.append((cur, sep)); cur = ''; sep = ''
    if cur: out.append((cur, sep))
    return out


def join(tk):
    return ''.join((s if i else '') + w for i, (w, s) in enumerate(tk))


def lines_tk(tk):
    """조각 목록 → 줄마다 조각 목록(320 px)"""
    out = []; cur = []
    for w, sp in tk:
        if width(join(cur + [(w, sp)])) + 4 <= MAXW:
            cur.append((w, sp)); continue
        if cur: out.append(cur)
        while width(w) + 4 > MAXW:
            k = len(w)
            while width(w[:k]) + 4 > MAXW: k -= 1
            out.append([(w[:k], sp)]); w = w[k:]; sp = ''
        cur = [(w, sp)]
    if cur: out.append(cur)
    return out


def lines_of(t):
    return [join(l) for l in lines_tk(tokens(t))]


def balance_tk(ls):
    """두 줄이면 폭을 고르게 — 조각 경계에서, 원래 구분자(공백 유무) 그대로"""
    if len(ls) != 2: return [join(l) for l in ls]
    tk = ls[0] + ls[1]; best = (abs(width(join(ls[0])) - width(join(ls[1]))), ls[0], ls[1])
    for k in range(1, len(tk)):
        a, b = tk[:k], tk[k:]
        wa, wb = width(join(a)), width(join(b))
        if wa + 4 <= MAXW and wb + 4 <= MAXW and abs(wa - wb) < best[0]:
            best = (abs(wa - wb), a, b)
    return [join(best[1]), join(best[2])]


def balance(two):
    return balance_tk([tokens(x) for x in two]) if len(two) == 2 else two


def sentences(t):
    """문장 끝 부호(.!?…~ 와 닫는 괄호 묶음) 뒤에서 자름 — 공백이 지워져 있어도"""
    out = []; cur = ''
    for i, ch in enumerate(t):
        cur += ch
        if ch in END and (i + 1 == len(t) or t[i + 1] not in END):
            out.append(cur.strip()); cur = ''
    if cur.strip(): out.append(cur.strip())
    return [s for s in out if s]


def pages_of(ko):
    """★쪽은 문장 단위로 채운다 — 한 문장이 두 쪽에 걸치는 건 그 문장이 두 줄보다 길 때만
       (사용자 «마지막에 칠 아웃!의 칠만 남는 건 너무하다 · 최소한 문장 단위로» 2026-10-10)"""
    pages = []
    for part in [p.strip() for p in ko.split('|') if p.strip()]:
        tk = tokens(part); sents = []; cur = []
        for w, sp in tk:                           # 조각을 문장으로 묶음(문장 끝 = 끝 부호로 끝나는 조각)
            cur.append((w, sp))
            if w[-1:] in END: sents.append(cur); cur = []
        if cur: sents.append(cur)
        page = []
        for st in sents:
            cand = page + st
            if len(lines_tk(cand)) <= 2:
                page = cand; continue
            if page: pages.append(balance_tk(lines_tk(page)))
            ls = lines_tk(st)
            if len(ls) <= 2:
                page = st; continue
            while ls:                              # 두 줄보다 긴 문장만 쪽을 걸침
                pages.append(balance_tk(ls[:2])); ls = ls[2:]
            page = []
        if page: pages.append(balance_tk(lines_tk(page)))
    return pages


def layout(lines):
    """→ w8, nrow, 글자 목록[(문자, x, 줄)]"""
    w8 = (max(width(s) for s in lines) + 4 + 7) // 8
    chars = []
    for i, s in enumerate(lines):
        x = (w8 * 8 - width(s)) // 2
        for c in s:
            if c != ' ': chars.append((c, x, i))
            x += adv(c)
    return w8, 2 * len(lines), chars


TEXT_C = 15        # 글자 색 번호 — 팔레트 15(→보충 7 = 127)의 흰색 자리. 1 = 테두리 검정 (2026-10-10 미션 제목이 팔레트 15 를 써서 2→15)


def reference(w8, nrow, chars):
    """게임 코드와 같은 규칙으로 쪽 그림(색 번호 배열 H×W)"""
    H = nrow * 8; F = np.zeros((H + 2, STRIDE * 8), np.uint8)       # 위아래 한 줄씩 여유
    for c, x, ln in chars:
        for r, bits in enumerate(glyph(c)):
            y = ln * 16 + 3 + r
            if y >= H: continue
            for b in range(16):
                if bits >> (15 - b) & 1 and x + b < STRIDE * 8: F[y + 1, x + b] = 1
    D = F.copy()
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            D |= np.roll(np.roll(F, dy, 0), dx, 1)
    F = F[1:H + 1, :w8 * 8]; D = D[1:H + 1, :w8 * 8]
    return np.where(F == 1, TEXT_C, np.where(D == 1, 1, 0)).astype(np.uint8)


def cells_4bpp(px, w8, nrow):
    out = bytearray()
    for cy in range(nrow):
        for cx in range(w8):
            for y in range(8):
                v = 0
                for x in range(8):
                    v = v << 4 | int(px[cy * 8 + y, cx * 8 + x])
                out += struct.pack('>I', v)
    return bytes(out)


def gbytes(c):
    """글자 하나 = 12×12 1비트 → 18 B(두 행씩 3 B)"""
    g = [v >> 4 for v in glyph(c)]; out = b''
    for a, b in zip(g[0::2], g[1::2]):
        out += bytes([a >> 4, (a & 15) << 4 | b >> 8, b & 0xFF])
    return out


def bank_bytes(chars):
    """공용 글꼴(VRAM 상주) — 글자마다 18 B, 16 B 단위로 채움"""
    f = b''.join(gbytes(c) for c in chars)
    return f + bytes(-len(f) % 16)


def pack(ko, samples, starts=None, bank=None, bank_off=0, carry=0):
    """bank = 이 클립이 «쓰는» 공용 글꼴 글자 목록(머리 훅이 공용 글꼴을 묶음 바로 뒤로 복사 → 번호 L.. 로 이어짐)
       carry = 이 클립 머리에 «싣는» 공용 글꼴 16 B 단위 수(묶음 뒤에 붙임 — 호출자가 bank_bytes 를 덧붙임)
       머리 14번 바이트 = 단위 수 | 0x80(쓰기) · 15번 = 공용 글꼴 위치(256 B 단위)"""
    pages = pages_of(ko)
    if starts is None:
        lens = [len(''.join(p).replace(' ', '')) for p in pages]; tot = max(1, sum(lens)); acc = 0; starts = []
        for L in lens: starts.append(int(samples * acc / tot)); acc += L
    bidx = {c: i for i, c in enumerate(bank or [])}
    lay = [layout(p) for p in pages]
    gl = []; gidx = {}
    for _, _, chars in lay:
        for c, _, _ in chars:
            if c not in bidx and c not in gidx: gidx[c] = len(gl); gl.append(c)
    if bank and len(gl) % 2: gl.append(None)            # 글꼴 길이 18×L 이 4 의 배수(공용 글꼴이 바로 뒤에 붙게)
    L = len(gl); recs = []
    for w8, nrow, chars in lay:
        rec = bytearray([w8, nrow, (COLS - w8) // 2, len(chars)])
        for c, x, ln in chars:
            rec += bytes([gidx[c] if c in gidx else L + bidx[c], x & 0xFF, (x >> 8) | (ln << 1)])
        rec += bytes(-len(rec) % 4); recs.append((w8, nrow, chars, bytes(rec)))
    assert L + len(bidx) <= 256
    off = 16 + 8 * len(pages); tab = b''; body = b''
    for i, (_, _, _, rec) in enumerate(recs):
        tab += struct.pack('>II', starts[i], off); body += rec; off += len(rec)
    goff = off
    font = b''.join(gbytes(c) if c else bytes(18) for c in gl)
    font += bytes(-len(font) % 4)
    total = goff + len(font)
    if bank: field = (0x80 | len(bank_bytes(bank)) // 16) << 8 | bank_off
    elif carry: field = carry << 8 | bank_off
    else: field = 0
    blob = b'SUB4' + struct.pack('>IHHHH', samples, len(pages), total, goff, field) + tab + body + font
    assert len(blob) == total
    return blob, pages, recs
