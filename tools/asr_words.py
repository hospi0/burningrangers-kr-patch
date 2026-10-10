# -*- coding: utf-8 -*-
"""클립마다 위스퍼 낱말 시각 → work/asr_words.json  {번호: [[글자들, 시작초], …]} (2026-10-10, 쪽 시각 맞추기용)
   whisper-venv 로: C:\\claude\\utils\\whisper-venv\\Scripts\\python.exe tools/asr_words.py"""
import json, os, subprocess, sys
import numpy as np
from faster_whisper import WhisperModel
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FF = r'C:\claude\utils\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe'
OUT = os.path.join(ROOT, 'work', 'asr_words.json')
m = WhisperModel('large-v3', device='cuda', compute_type='float16')
P = 'バーニングレンジャー。ショウ、ティリス、クリス、リード、ビッグ。転送、要救助者、隔壁。'
res = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
for k in range(1269):
    if str(k) in res: continue
    raw = subprocess.run([FF, '-v', 'error', '-f', 'adx', '-i', os.path.join(ROOT, 'work', 'adx', '%04d.adx' % k), '-ac', '1', '-ar', '16000',
                          '-f', 's16le', '-'], capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    seg, _ = m.transcribe(a, language='ja', beam_size=5, condition_on_previous_text=False, word_timestamps=True, initial_prompt=P)
    res[str(k)] = [[w.word, round(w.start, 3)] for s in seg for w in (s.words or [])]
    if k % 50 == 0:
        json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False); print(k, flush=True)
json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False); print('끝', len(res))
