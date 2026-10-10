# -*- coding: utf-8 -*-
"""work/adx/*.adx 전부 받아쓰기(위스퍼 large-v3) → work/asr.tsv (번호·길이·문장)
   C:\\claude\\utils\\whisper-venv\\Scripts\\python.exe tools/asr_all.py"""
import glob, os, subprocess, sys
import numpy as np
from faster_whisper import WhisperModel
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
m = WhisperModel('large-v3', device='cuda', compute_type='float16')
out = os.path.join(ROOT, 'work', 'asr.tsv')
done = set()
if os.path.exists(out):
    done = {l.split('\t')[0] for l in open(out, encoding='utf-8')}
fo = open(out, 'a', encoding='utf-8')
for p in sorted(glob.glob(os.path.join(ROOT, 'work', 'adx', '*.adx'))):
    k = os.path.basename(p)[:4]
    if k in done:
        continue
    raw = subprocess.run([FF, '-v', 'error', '-f', 'adx', '-i', p, '-ac', '1', '-ar', '16000', '-f', 's16le', '-'],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    seg, _ = m.transcribe(a, language='ja', beam_size=5, condition_on_previous_text=False)
    t = ''.join(s.text.strip() for s in seg)
    fo.write('%s\t%.2f\t%s\n' % (k, len(a) / 16000, t)); fo.flush()
print('끝')
