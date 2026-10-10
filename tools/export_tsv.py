# -*- coding: utf-8 -*-
"""번역표 내보내기 — work/asr.tsv(받아쓰기) → work/trans/br_NN.tsv (UTF-8, 머리줄 포함 29 KB 이하로 나눔)
   열: id(ADX 번호) · kind(분류) · sec(길이) · ja(위스퍼 받아쓰기 — 틀릴 수 있음) · ko(번역 — 비우면 자막 없음)
   ko 안에서 « | » = 쪽 나눔(안 쓰면 빌더가 2줄씩 알아서 나눔). python tools/export_tsv.py"""
import os, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = [(0, 15, '메일알림'), (16, 20, '브리핑'), (21, 36, '비밀번호'), (37, 88, '결과화면'), (89, 157, '길안내'),
         (158, 454, '미션무전_쇼'), (455, 558, '보스·외침'), (559, 642, '요구조자'), (643, 862, '공용'),
         (863, 954, '튜토리얼_쇼'), (955, 1238, '미션무전_티리스'), (1239, 1268, '튜토리얼_티리스')]
LIMIT = 29 * 1024


def kind(i):
    for a, b, k in KINDS:
        if a <= i <= b:
            return k
    return ''


rows = []
for ln in open(os.path.join(ROOT, 'work', 'asr.tsv'), encoding='utf-8'):
    k, sec, ja = ln.rstrip('\n').split('\t')
    if 'ご視聴ありがとう' in ja or not ja.strip():
        ja = '(받아쓰기 실패 — 들어 보고 채울 것)'
    rows.append('%s\t%s\t%s\t%s\t' % (k, kind(int(k)), sec, ja.replace('\t', ' ')))
head = 'id\tkind\tsec\tja\tko'
out = os.path.join(ROOT, 'work', 'trans'); os.makedirs(out, exist_ok=True)
for f in os.listdir(out):
    if f.startswith('br_') and f.endswith('.tsv'):
        os.remove(os.path.join(out, f))
parts = []; cur = [head]; size = len(head.encode('utf-8')) + 1
for r in rows:
    n = len(r.encode('utf-8')) + 1
    if size + n > LIMIT:
        parts.append(cur); cur = [head]; size = len(head.encode('utf-8')) + 1
    cur.append(r); size += n
parts.append(cur)
for k, p in enumerate(parts, 1):
    fn = os.path.join(out, 'br_%02d.tsv' % k)
    open(fn, 'w', encoding='utf-8', newline='\n').write('\n'.join(p) + '\n')
    print('%s  %4d줄  %5d B  %s‥%s' % (os.path.basename(fn), len(p) - 1, os.path.getsize(fn), p[1].split('\t')[0], p[-1].split('\t')[0]))
