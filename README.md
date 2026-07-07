# Castlevania Advance Collection — 한글 ROM 주입 도구

Steam판 **Castlevania Advance Collection**(캐슬바니아 어드밴스 컬렉션)의
`windata\alldata.bin` 아카이브 안에 들어 있는 일본판 게임 ROM들을,
**기존 팬 한글패치 ROM으로 교체**해 주는 오픈소스 패처입니다.

> ⚠️ **이 저장소에는 게임 ROM이나 번역 데이터가 포함되어 있지 않습니다.**
> 이 도구는 *리패킹만* 합니다. 사용자는
> ① Steam에서 정식 소유한 게임의 `alldata.bin`/`alldata.psb.m`,
> ② 각 원작 번역팀의 패치를 자기 ROM에 적용해 만든 한글 ROM
> 을 직접 준비해야 합니다. (아래 [출처](#한글패치-출처크레딧) 참고)

---

## 대상 게임 (Steam)

| 항목 | 내용 |
|---|---|
| 제목 | Castlevania Advance Collection |
| Steam App ID | **1552550** |
| 출시 | 2021-09-23 |
| 발매 | Konami Digital Entertainment |
| 에뮬레이션 | **M2 Co., Ltd.** |
| 수록작 | 서클 오브 더 문(GBA) · 백야의 협주곡(GBA) · 효월의 원무곡(GBA) · **드라큘라 XX**(SNES, 보너스) |

교체 대상은 각 게임의 **일본판(`_JP`) ROM**입니다. 한글패치가 일본판 기반이라,
게임 내 **언어를 "일본어"로 설정**해야 한글이 표시됩니다.

## 동작 원리 (요약)

`alldata.psb.m`+`alldata.bin`은 M2 엔진의 **MArchive** 포맷(암호화+zlib)입니다.
[FreeMote](https://github.com/UlyssesWu/FreeMote)로 언팩/리팩하며, 키는 게임
실행 파일에 들어 있는 `25G/xpvTbsb+6`(length 64)입니다.

⚠️ **핵심:** 원본은 모든 엔트리가 **0x800(2048B) 정렬**돼 있는데, 일반 리팩은
정렬을 깨뜨려 **부팅 직후 크래시**합니다. 이 도구는 리팩 후 **0x800 정렬로
재배치**해 이 문제를 해결합니다. 자세한 내용은 **[TECHNICAL.md](TECHNICAL.md)**.

## 간편 설치 (GUI 설치기, 권장)

[**Releases**](https://github.com/snake7594/castlevania-advance-collection-korean-patch/releases)에서
`CastlevaniaAdvanceKR-Installer.exe`를 받아 실행하면 클릭 몇 번으로 끝납니다.

1. **게임 폴더** — `자동 감지`를 누르면 Steam 설치 경로를 찾아줍니다(안 되면 `찾아보기`).
2. **FreeMote 폴더** — `자동 설치` 버튼 한 번이면 [공식 GitHub 릴리즈](https://github.com/UlyssesWu/FreeMote/releases)에서
   내려받아 `%LOCALAPPDATA%`에 설치하고 경로까지 자동 지정합니다.
   (이미 있으면 `자동 감지`가 찾고, 수동으로 받아 `찾아보기`로 지정해도 됩니다.)
3. **한글패치 ROM 선택** — 교체할 게임의 한글 ROM을 고릅니다(원하는 게임만 골라도 됩니다).
4. **패치 설치하기** — 원본을 자동 백업한 뒤 교체·리팩·검증까지 자동으로 수행합니다.

> exe는 **도구 자체**일 뿐 ROM·번역 데이터·FreeMote를 포함하지 않습니다.
> ROM과 FreeMote는 사용자가 직접 준비해야 합니다.

## 명령줄(CLI) 사용 (고급)

**필요:**
- Python 3.9+
- [FreeMote v4.6.1](https://github.com/UlyssesWu/FreeMote/releases) (`PsbDecompile.exe`, `PsBuild.exe`)
- Steam판 Castlevania Advance Collection 설치본
- 한글패치를 적용한 ROM 파일 (아래 출처에서 패치를 받아 각자 ROM에 적용)

```bat
python tools/patch_advance_collection.py ^
  --windata  "C:\Program Files (x86)\Steam\steamapps\common\Castlevania Advance Collection\windata" ^
  --freemote "C:\경로\FreeMote-v4.6.1" ^
  --circle    "서클 오브 더 문 (Korean).gba" ^
  --byakuya   "백야의 협주곡 (Korean).gba" ^
  --akatsuki  "효월의 원무곡 (Korean).gba" ^
  --draculaxx "악마성 드라큘라 XX (Korean).smc" ^
  --install
```

- `--install`을 빼면 게임에 설치하지 않고 결과 파일만 만듭니다.
- `--install` 시 `windata\_backup-<시각>\`에 원본을 자동 백업합니다.
- 4개 중 원하는 게임만 지정해도 됩니다.
- 도구가 리팩 후 자동으로 **재추출 검증**(교체 ROM 바이트 일치, 0x800 정렬 474/474)을
  수행합니다.

## 게임에서 확인

1. Steam에서 **Castlevania Advance Collection** 실행.
2. **게임 내 언어를 "일본어(Japanese)"로 설정**.
3. 각 게임에 진입하면 한글 표시.

## 주의사항

- **Steam "게임 파일 무결성 검사"를 돌리면 패치가 원복**됩니다(변경된 `alldata.bin`을
  다시 내려받음).
- 원본 복구: 백업 폴더의 `alldata.bin`/`alldata.psb.m`을 `windata`에 되돌리면 됩니다.

## 한글패치 출처/크레딧

이 도구는 아래 팀/제작자분들의 **한글패치 결과물을 교체용으로 사용**합니다.
번역 저작권은 각 제작자에게 있으며, 패치 파일은 각 원 배포처에서 받으시기 바랍니다.

| 게임 | 제작 | 버전/배포 | 출처 |
|---|---|---|---|
| 백야의 협주곡 (Harmony of Dissonance) | **ARCHE**(총괄), 알렉스, 묘목, 엑소버드, 알 | v1.4 / 2022-01-29 | [한글로게임](https://www.hangulogame.com/post/patch/gba/950/) · [원배포(한시구 카페)](https://cafe.naver.com/hansicgu/28039) |
| 효월의 원무곡 (Aria of Sorrow) | **ARCHE**(총괄), 알렉스, 엑소버드, 의문의솜털, DEVA | v2.2 / 2022-01-29 | [한글로게임](https://www.hangulogame.com/post/patch/gba/399/) · [원배포(한시구 카페)](https://cafe.naver.com/hansicgu/28039) |
| 악마성 드라큘라 XX (SNES) | **팀무풍(TEAM MUPUNG)** — passion_pay(프로그래밍), 한마루(번역/그래픽), 하루(MSU1), Conn(영문) | 2017-11-06 (MSU1 2022-08-26) | [팀무풍](https://teammp.diskstation.me/043.php) |
| 서클 오브 더 문 (Circle of the Moon) | **강민석 (rainbovv)** | 2004-03-27 | [한글로게임](https://www.hangulogame.com/patch/gba/128) |

### 도구/기술 크레딧
- **FreeMote** — Ulysses ([UlyssesWu/FreeMote](https://github.com/UlyssesWu/FreeMote))
- **M2 MArchive 포맷** 분석 — GMWare.M2 / MArchiveBatchTool 커뮤니티

## 라이선스

이 저장소의 **도구 코드와 문서**는 MIT 라이선스입니다([LICENSE](LICENSE)).
게임 ROM·번역 데이터는 포함하지 않으며, 각 저작권자의 권리를 존중합니다.
