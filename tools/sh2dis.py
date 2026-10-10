# -*- coding: utf-8 -*-
"""0.BIN SH-2(빅 엔디언) 역어셈블 — terra-kr-patch/tools/sh2_disasm.py 사용. 적재 0x06004000.
   python tools/sh2dis.py 파일오프셋(16진) [개수]"""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOAD = 0x06004000
EXE = os.path.join(ROOT, 'work', 'iso', '0.BIN')
_src = open(r'C:\claude\project\terra-kr-patch\tools\sh2_disasm.py', encoding='utf-8').read().split("if __name__")[0]
_ns = {}; exec(_src, _ns)


def dis(off, n=80, g=None):
    g = g or open(EXE, 'rb').read()
    return ['%06X %08X  %04X  %s' % (a - LOAD, a, w, t) for a, w, t in _ns['disasm_sh2'](g[off:off + n * 2], LOAD + off, n)]


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print('\n'.join(dis(int(sys.argv[1], 16), int(sys.argv[2]) if len(sys.argv) > 2 else 80)))
