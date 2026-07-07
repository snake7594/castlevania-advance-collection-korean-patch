# -*- coding: utf-8 -*-
"""
Castlevania Advance Collection (Steam) — Korean ROM injector (CLI)

marchive_core 의 로직을 명령줄에서 실행하는 얇은 래퍼.
GUI 버전은 gui.py 참고. 기술 상세는 ../TECHNICAL.md.

사용 예:
  python patch_advance_collection.py \
      --windata "C:/.../Castlevania Advance Collection/windata" \
      --freemote "C:/path/to/FreeMote-v4.6.1" \
      --circle "Circle (Korean).gba" --byakuya "Byakuya (Korean).gba" \
      --akatsuki "Akatsuki (Korean).gba" --draculaxx "DraculaXX (Korean).smc" \
      --install
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marchive_core as core


def main():
    ap = argparse.ArgumentParser(description="Castlevania Advance Collection 한글 ROM 주입기 (CLI)")
    ap.add_argument("--windata", help="Steam .../windata 경로 (미지정 시 자동 감지)")
    ap.add_argument("--freemote", help="FreeMote 폴더 경로 (미지정 시 자동 감지)")
    ap.add_argument("--circle", help="서클 오브 더 문 한글 ROM (.gba)")
    ap.add_argument("--byakuya", help="백야의 협주곡 한글 ROM (.gba)")
    ap.add_argument("--akatsuki", help="효월의 원무곡 한글 ROM (.gba)")
    ap.add_argument("--draculaxx", help="악마성 드라큘라 XX 한글 ROM (.smc/.sfc)")
    ap.add_argument("--work", help="작업 폴더 (기본: <windata>/_krpatch_work)")
    ap.add_argument("--install", action="store_true", help="windata에 설치(백업 후 덮어쓰기)")
    args = ap.parse_args()

    windata = args.windata or core.autodetect_windata()
    freemote = args.freemote or core.autodetect_freemote()
    if not windata:
        raise SystemExit("게임 폴더(windata)를 찾지 못했습니다. --windata 로 지정하세요.")
    if not freemote:
        raise SystemExit("FreeMote 폴더를 찾지 못했습니다. --freemote 로 지정하세요.")
    print(f"windata : {windata}")
    print(f"freemote: {freemote}")

    roms = {k: getattr(args, k) for k in ("circle", "byakuya", "akatsuki", "draculaxx")
            if getattr(args, k)}
    if not roms:
        raise SystemExit("교체할 한글 ROM을 하나 이상 지정하세요 (--circle 등).")

    res = core.patch_collection(windata, freemote, roms, install=args.install,
                                work=args.work, log=print)
    print(f"\n완료: {res['output_bin']}")
    if res["installed"]:
        print(f"백업: {res['backup']}")
        print("게임 내 언어를 '일본어'로 설정해 플레이하세요.")
    else:
        print("(--install 미지정: 위 파일을 windata에 복사하면 설치됩니다)")


if __name__ == "__main__":
    main()
