# 기술 문서 — Castlevania Advance Collection 아카이브 분석 및 한글 ROM 주입

이 문서는 Steam판 **Castlevania Advance Collection**(App ID `1552550`, 2021-09-23,
Konami 발매 / M2 에뮬레이션)의 `windata\alldata.bin` + `alldata.psb.m` 아카이브를
분석하고, 내부 게임 ROM을 한글패치본으로 교체하는 전 과정을 기록한다.

---

## 1. 파일 포맷: M2 MArchive

`alldata.psb.m`(매니페스트) + `alldata.bin`(본문) 쌍은 **M2 Co., Ltd.** 엔진이 쓰는
**MArchive** 포맷이다. 두 파일 모두 `mdf\0` 매직으로 시작한다.

```
alldata.psb.m : 6D 64 66 00 | 82 92 00 00 | C2 D4 E5 CF ...
alldata.bin   : 6D 64 66 00 | 81 07 00 00 | 59 2A 1E DA ...
                └ "mdf\0"    └ 원본크기(LE) └ 암호화된 zlib 스트림
```

- **MDF 래퍼:** `mdf\0` + uint32(압축 해제 크기) + 본문.
- 본문은 **MT19937 키스트림으로 XOR 스크램블된 뒤 zlib 압축**돼 있다.
  offset 8의 바이트가 zlib 헤더 `0x78`이 아니라(`0xC2`/`0x59` 등) 암호화됐음을 알 수 있다.
- `alldata.bin`은 하나의 큰 스트림이 아니라, **개별 엔트리(각자 독립 MDF 파일)들이
  0x800 정렬로 이어 붙은 컨테이너**다. (파일 선두의 `mdf\0`는 첫 엔트리의 헤더일 뿐)

## 2. 암호화 키

MArchive의 MDF 스크램블 **시드 = 키 문자열 + 파일명**. 키는:

```
KEY    = "25G/xpvTbsb+6"     (13바이트)
LENGTH = 64
COMP   = zlib
```

- 이 키는 `game.exe`의 오프셋 **`0x224FA4`** 에 null 종료 문자열로 박혀 있다.
- 예: `alldata.psb.m`의 실제 시드 문자열은 `"25G/xpvTbsb+6alldata.psb.m"`.
  (FreeMote가 추출 시 남기는 `alldata.psb.m.resx.json`의 `MdfKey` 값과 일치)
- 각 엔트리는 자신의 **엔트리 파일명**을 붙인 시드로 암호화되므로, 하나의 키로
  매니페스트와 모든 엔트리를 풀 수 있다.

## 3. 매니페스트 구조

`alldata.psb.m`을 복호화하면 `ArchiveInfo` 타입 PSB가 나오고, 핵심은 `file_info`:

```json
"file_info": {
  "system/roms/01_Circle_JP.patch_210623m.bin.m": [298874880, 3959078],
  ...
}
```

즉 `엔트리경로 → [alldata.bin 내 오프셋, 압축 저장 길이]`. 총 **474개 엔트리**.
카테고리는 `022/`, `090`~`093/`, `system/` (config·image·motion·script·sound·font·roms).

### 게임 ROM 엔트리 (`system/roms/`)

추출하면 raw(비압축) ROM으로 풀린다. 저장 시에는 zlib 압축된다.

| 엔트리 | 게임 | 원본크기 | GBA 코드 |
|---|---|---|---|
| `01_Circle_{JP,US,EU}.patch_210623m.bin.m` | 서클 오브 더 문 | 8 MB | AAMJ/E/P |
| `02_Byakuya_{JP,US,EU}.patch_210520m.bin.m` | 백야의 협주곡 | 8 MB | ACHJ/E/P |
| `03_Akatsuki_{JP,US,EU}.patch_210623m.bin.m` | 효월의 원무곡 | 8 MB | A2CJ/E/P |
| `AkumajouDraculaXX_0408.SFC.m` | 악마성 드라큘라 XX (JP) | 2 MB | — |
| `CastlevaniaDraculaX_0409.SFC.m` | Dracula X (US) | 2 MB | — |
| `CastlevaniaVampiresKiss_0409.SFC.m` | Vampire's Kiss (EU) | 2 MB | — |

- **한글패치는 일본판 기반**이라 `_JP` / `AkumajouDraculaXX` 엔트리가 교체 대상이다.
  게임 내 언어를 **일본어**로 설정하면 이 ROM들이 로드된다.
- `03_Akatsuki_JP`는 실제 내용 7,351,826B 뒤를 **0x00으로 8MB까지 패딩**한 구조다.
  한글본도 동일하게 0x00 패딩해 8MB로 맞춘다.

## 4. 도구 (FreeMote)

[FreeMote v4.6.1](https://github.com/UlyssesWu/FreeMote) (by Ulysses) 로 언팩/리팩.

```bat
:: 언팩 — 474개 파일 추출
PsbDecompile.exe info-psb -k 25G/xpvTbsb+6 -l 64 -b alldata.bin -o out alldata.psb.m

:: 리팩 — 폴더+매니페스트 json → 새 alldata.psb.m + alldata.bin
PsBuild.exe    info-psb -k 25G/xpvTbsb+6 -l 64 alldata.psb.m.json
```

`MArchiveBatchTool`(GMWare.M2 기반)로도 같은 작업이 가능하다.
키/length/압축을 `zlib 25G/xpvTbsb+6 64`로 지정한다.

## 5. ★핵심 함정: 0x800 정렬

**원본 아카이브는 474개 엔트리 전부가 0x800(2048B) 경계에서 시작**한다.
그런데 FreeMote의 `PsBuild info-psb` 리팩은 엔트리를 **정렬 없이 조밀하게** 이어
붙인다(474개 중 2개만 우연히 정렬). 이 상태로 게임을 실행하면 **부팅 직후(주의
화면 다음) 크래시**한다 — M2 엔진이 섹터 정렬을 전제로 오프셋을 읽기 때문이다.

### 해결 방법

FreeMote 리팩 결과의 **엔트리 블롭은 이미 올바르게 MDF 암호화돼 있으므로**, 그
블롭들을 그대로 재활용하되 **0x800 정렬로 재배치**하고 매니페스트만 다시 만든다.

1. `PsBuild info-psb`로 1차 리팩 (블롭이 파일명 시드로 올바르게 암호화됨).
2. 그 결과를 재추출해 각 엔트리 블롭의 (오프셋, 길이)를 얻는다.
3. **원본 엔트리 순서대로**, 각 블롭을 0x800 정렬해 새 `alldata.bin`에 이어 붙이고
   새 오프셋을 기록한다.
4. 매니페스트 json의 `file_info`를 새 오프셋/길이로 갱신한 뒤,
   `PsBuild alldata.psb.m.json` (plain 컴파일, `info-psb` 아님)으로 `alldata.psb.m`만
   다시 만든다. (키/length는 `resx.json`에서 읽음)

결과: 474/474 엔트리 0x800 정렬 → 엔진이 정상 로드.

### 왜 "슬롯 내 끼워넣기"는 안 되나

원본 슬롯에 그대로 덮어쓰려면 한글 ROM의 압축 크기가 원본 슬롯보다 작아야 하는데,
한글 데이터는 원본 일본어보다 덜 압축돼 4개 중 3개가 슬롯을 초과한다
(Byakuya +436B, Akatsuki +58KB, XX +2.4KB 초과). 그래서 전체 재배치가 필요하다.

## 6. 검증 절차

- **무변경 왕복:** 언팩→리팩→재언팩 후 474개 파일 SHA1 전량 동일 = 툴체인 무손실.
- **패치 검증:** 정렬 리팩본을 재추출해 4개 ROM이 한글 소스와 바이트 일치, 나머지
  470개가 원본과 일치, 474/474 오프셋 0x800 정렬임을 확인.
- **런타임:** 게임 언어를 일본어로 두고 4개 게임 진입까지 정상 동작 확인.

## 7. 주의사항

- **Steam '게임 파일 무결성 검사'** 를 돌리면 변경된 `alldata.bin`을 다시 받아
  패치가 원복된다.
- 한글은 **게임 내 언어 = 일본어** 설정에서만 나온다(패치가 일본판 ROM에 들어감).
- 원본 백업을 반드시 보관할 것 (이 도구의 `--install`은 자동 백업 폴더를 만든다).
