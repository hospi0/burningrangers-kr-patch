# -*- coding: utf-8 -*-
"""flycast 세이브스테이트(`#RZIPv1#`) 해제.

헤더: char[8] magic | u32 maxChunkSize | u64 size
이후 (u32 압축크기 + zlib 덩어리) 반복.
"""
import struct, zlib, sys

MAGIC = b'#RZIPv#'   # 버전 바이트가 ASCII '1' 이 아니라 0x01 이다


def unrzip(raw):
    if not raw.startswith(MAGIC):
        return raw                       # 압축 안 된 스테이트
    maxc, total = struct.unpack_from('<IQ', raw, 8)
    p, out = 20, []
    while p + 4 <= len(raw) and sum(len(x) for x in out) < total:
        (n,) = struct.unpack_from('<I', raw, p); p += 4
        if n == 0 or p + n > len(raw):
            break
        out.append(zlib.decompress(raw[p:p + n])); p += n
    return b''.join(out)


if __name__ == '__main__':
    b = unrzip(open(sys.argv[1], 'rb').read())
    open(sys.argv[2], 'wb').write(b)
    print('%d bytes' % len(b))
