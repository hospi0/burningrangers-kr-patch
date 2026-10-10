# 버닝 레인저 한글 패치 (Burning Rangers, 세가 새턴 일본판)

- 대상: Burning Rangers (Japan) — 트랙 1에 xdelta 패치 (트랙 2 오디오·cue 는 그대로)
- 내려받기: 릴리즈의 `BurningRangers_KR_v0.9.zip` — 안의 readme.txt 에 원본·패치 md5 와 적용 방법

| 트랙 | 원본 md5 | 패치 md5 |
|---|---|---|
| Track 1 | `D19A6646A5430A60FD84D5CEDBC2E5CA` | `E343D3ABA16A8EC9F3012F33F0100348` |

## 바뀌는 것 (v0.9)
- 음성 자막 1,268개 — 원래 자막이 없는 게임이라 새로 넣음(음성 재생에 맞춰 쪽이 넘어가고, 여러 사람이 주고받는 대사는 화자마다 나눔)
- 컷신 동영상 9편 자막(영상에 구워 넣음)
- 메일 183통(반각 띄어쓰기)
- 부팅 로딩 화면 안내문, 대원 소개 카드 이름

## 알려진 점
- 미션 하나(붉은 하늘 장면) 초반에 자막이 처음 뜰 때 배경 타일이 잠깐 깨져 보임
- 이리아 장면 일부는 화면 구성상 음성 자막이 보이지 않음
- 리드·빅 주인공 모드는 실기 미확인

## 저장소
- `tools/build.py` 빌더(자막 훅 SH-2 코드·ADX 머리에 자막 싣기·공용 글꼴) · `glyphpack.py` 자막 조판 · `mail.py` 메일 · `moviesub.py`/`movenc.py` 동영상 자막 · `make_dist.py` 배포
- `tools/test_*.py` SH-2 흉내기(`sh2sim.py`) 검산
- `work/text/voice_ko.tsv` 음성 번역(id·종류·길이·받아쓰기·번역) · `work/text/mail_ko.tsv` 메일 번역
- `work/fixes.tsv` 교정 · `work/turns.tsv` 화자별 쪽 나눔 · `work/mail_fixes.tsv` 메일 교정 · `work/movie/movie_subs.tsv` 동영상 자막
- `docs/` 조사·작업 기록
