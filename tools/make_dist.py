# -*- coding: utf-8 -*-
r"""버닝 레인저 배포 묶음 — dist/BurningRangers_KR_<VER>/ : 트랙 1 xdelta + xdelta.exe + readme.txt(CP949) + 한글패치_적용.bat(CP949)
  바뀌는 트랙: 트랙 1 만(트랙 2 = 오디오, cue 도 그대로)
  검증: 원본 트랙 1 → xdelta 적용 → md5 = 설치본(F:) 트랙 1 md5.
  python tools/make_dist.py   (먼저 python tools/build.py --write --movie)
"""
import hashlib, os, shutil, subprocess, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)

VER = 'v0.9'
XDELTA = r'C:\claude\utils\xdelta.exe'
SRC = r'C:\claude\roms\ss\Burning Rangers (Japan)\Burning Rangers (Japan)'
OUT = r'F:\hospi\roms\ss roms\Burning Rangers (Japan)'
ROM = 'Burning Rangers (Japan)'
NAME = 'BurningRangers_KR_' + VER
TITLE = '버닝 레인저 (Burning Rangers, 세가 새턴 일본판) 한글 패치 ' + VER


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


README = """{title}
{line}

2개의 트랙으로 이루어진 {rom} 의
트랙 1번에 패치하시면 됩니다.

원본md5 : {o}
패치md5 : {d}

입니다.


[ 적용 방법 ]

  1) 원본 트랙 1 파일을 이 폴더에 복사
       "{bin}"
  2) 한글패치_적용.bat 실행 → 이름 끝에 [KR] 이 붙은 파일이 만들어집니다
  3) 만든 파일 이름을 원본 트랙 1 이름으로 바꿔 넣고, 트랙 2(오디오)와 cue 는 원본 그대로 쓰세요
     (패치한 트랙 1 은 원본보다 큽니다 - 정상입니다)

  직접 적용:
    xdelta.exe -d -s "원본 트랙 1" "{patch}" "결과 파일"
  (Delta Patcher 같은 xdelta3 GUI 도구로 적용해도 됩니다. 원본이 다르면 xdelta 가 적용을 거부합니다.)


[ 바뀌는 것 ]

  - 음성 자막 1,268개(무전·튜토리얼·브리핑·결과 화면·구조 대사) - 원래 자막이 없는 게임이라 새로 넣었습니다
      여러 사람이 주고받는 대사는 화자마다 쪽을 나눠 음성에 맞춰 넘어갑니다
  - 컷신 동영상 9편 자막(영상에 구워 넣음)
  - 메일 183통(띄어쓰기는 반각 폭)
  - 부팅 로딩 화면 안내문, 대원 소개 카드 이름


[ 알려진 점 ]

  - 미션 하나(붉은 하늘 장면)의 초반에 자막이 처음 뜰 때 배경 타일이 잠깐 깨져 보입니다.
  - 이리아(신비한 목소리) 장면 일부는 화면 구성상 음성 자막이 보이지 않습니다.
  - 리드·빅으로 플레이하는 모드는 실기로 확인하지 못했습니다.
  - 일부 장면은 원본에서도 다음 연출이 시작되면 대사가 도중에 끊깁니다(돌고래 장면 등).
"""

BAT = r"""@echo off
chcp 949 >nul
set "XD=%~dp0xdelta.exe"
if not exist "%~dp0{bin}" (
  echo   [오류] 원본 트랙 1 파일을 이 폴더에 넣어 주세요 - readme 참고.
  pause & exit /b 1
)
"%XD%" -d -f -s "%~dp0{bin}" "%~dp0{patch}" "%~dp0{kbin}"
if errorlevel 1 (
  echo   [오류] 패치 실패 - 원본이 다를 수 있습니다 - readme 의 원본md5 확인.
  pause & exit /b 1
)
echo   완료: "{kbin}"
pause
"""


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = os.path.join(ROOT, 'dist', NAME)
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d)
    b = '%s (Track 1).bin' % ROM
    src, out = os.path.join(SRC, b), os.path.join(OUT, b)
    patch = NAME + '_Track1.xdelta'; pp = os.path.join(d, patch)
    subprocess.run([XDELTA, '-e', '-9', '-B', '536870912', '-f', '-s', src, out, pp], check=True)   # 원본 전체를 탐색 창에(ADX.ACX 를 디스크 끝으로 옮겨서)
    chk = os.path.join(d, '_check.bin')
    subprocess.run([XDELTA, '-d', '-f', '-s', src, pp, chk], check=True)
    o, want, got = md5(src), md5(out), md5(chk)
    os.remove(chk)
    assert got == want, ('패치 적용 결과가 빌드와 다름', got, want)
    print('트랙 1 원본md5 %s → 패치md5 %s · %s %d B' % (o, want, patch, os.path.getsize(pp)))
    shutil.copy2(XDELTA, os.path.join(d, 'xdelta.exe'))
    kbin = '%s (Track 1) [KR].bin' % ROM
    readme = README.format(title=TITLE, line='=' * 60, rom=ROM, o=o, d=want, bin=b, patch=patch)
    open(os.path.join(d, 'readme.txt'), 'wb').write(readme.replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(d, '한글패치_적용.bat'), 'wb').write(BAT.format(bin=b, patch=patch, kbin=kbin).replace('\n', '\r\n').encode('cp949'))
    z = os.path.join(ROOT, 'dist', NAME + '.zip')
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(d)):
            zf.write(os.path.join(d, f), NAME + '/' + f)
    print('✅', d)
    for f in sorted(os.listdir(d)):
        print('  %-56s %12d' % (f, os.path.getsize(os.path.join(d, f))))
    print('  zip %s %d B · md5 %s' % (os.path.basename(z), os.path.getsize(z), md5(z)))


if __name__ == '__main__':
    main()
