# -*- coding: utf-8 -*-
"""
Castlevania Advance Collection (Steam) — Korean ROM injector
============================================================

Steam판 `windata/alldata.bin` + `alldata.psb.m` (M2 엔진 MArchive 아카이브) 안의
게임 ROM들을, 사용자가 직접 준비한 한글패치 ROM으로 교체한다.

이 도구는 ROM 자체를 포함하지 않는다. 사용자가
  1) Steam에서 정식 소유한 게임의 alldata.bin / alldata.psb.m
  2) 각 원作 번역팀의 패치를 자기 ROM에 적용해 만든 한글 ROM 파일
을 준비해야 하며, 이 도구는 그것을 아카이브에 끼워 넣어 리패킹만 한다.

핵심 발견(자세한 내용은 ../TECHNICAL.md):
  - MArchive 암호화 키 = "25G/xpvTbsb+6", key length 64, zlib.
    (game.exe 오프셋 0x224FA4에 평문으로 존재. 시드 = 키 + 파일명)
  - ★엔진은 모든 엔트리가 0x800(2048B) 정렬돼 있어야 한다. FreeMote 기본
    리팩은 조밀 패킹이라 정렬이 깨져 부팅 직후 크래시한다. 따라서 리팩 후
    0x800 정렬로 재배치하고 매니페스트를 다시 컴파일해야 한다.

의존성: FreeMote v4.6.1 (PsbDecompile.exe / PsBuild.exe)
  https://github.com/UlyssesWu/FreeMote  (Ulysses)

사용 예:
  python patch_advance_collection.py \
      --windata "C:/Program Files (x86)/Steam/steamapps/common/Castlevania Advance Collection/windata" \
      --freemote "C:/path/to/FreeMote-v4.6.1" \
      --circle   "Circle (Korean).gba" \
      --byakuya  "Byakuya (Korean).gba" \
      --akatsuki "Akatsuki (Korean).gba" \
      --draculaxx "Dracula XX (Korean).smc" \
      --install            # 생략하면 output 폴더에만 생성(설치 안 함)
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

KEY = "25G/xpvTbsb+6"
KEYLEN = 64
ALIGN = 0x800

# 한글패치가 일본판 기반이므로 각 게임의 _JP 엔트리를 교체한다.
# (게임 내 언어를 '일본어'로 설정해야 해당 ROM이 로드된다.)
# name -> (아카이브 내 엔트리 파일명, 슬롯 크기(패딩 대상), GBA 게임코드 검증값 or None)
TARGETS = {
    "circle":    ("system/roms/01_Circle_JP.patch_210623m.bin.m",  8 * 1024 * 1024, b"AAMJ"),
    "byakuya":   ("system/roms/02_Byakuya_JP.patch_210520m.bin.m", 8 * 1024 * 1024, b"ACHJ"),
    "akatsuki":  ("system/roms/03_Akatsuki_JP.patch_210623m.bin.m", 8 * 1024 * 1024, b"A2CJ"),
    "draculaxx": ("system/roms/AkumajouDraculaXX_0408.SFC.m",       2 * 1024 * 1024, None),
}
GBA_LOGO = bytes.fromhex("24FFAE51")  # 닌텐도 로고(ROM offset 0x04)


def run(cmd, cwd=None):
    print("  $", " ".join(f'"{c}"' if " " in str(c) else str(c) for c in cmd))
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       cwd=str(cwd) if cwd else None)
    if r.returncode != 0:
        print(r.stdout[-2000:]); print(r.stderr[-2000:])
        raise SystemExit(f"명령 실패 (exit {r.returncode})")
    return r.stdout


def sha1(p: Path) -> str:
    h = hashlib.sha1()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_rom(src: Path, slot: int, code):
    """한글 ROM 로드 + 슬롯 크기에 맞춰 0x00 패딩 + (GBA면) 게임코드 검증."""
    data = src.read_bytes()
    if len(data) > slot:
        raise SystemExit(f"{src.name}: {len(data)}B 는 슬롯 {slot}B 보다 큼 (지원 안 함)")
    if code is not None:
        if data[4:8] != GBA_LOGO:
            raise SystemExit(f"{src.name}: GBA 닌텐도 로고 없음 — 올바른 ROM인지 확인")
        if data[0xAC:0xB0] != code:
            raise SystemExit(f"{src.name}: 게임코드 {data[0xAC:0xB0]!r} != 기대값 {code!r}")
    if len(data) < slot:
        data = data + b"\x00" * (slot - len(data))  # 원본과 동일하게 0x00 패딩
    return data


def main():
    ap = argparse.ArgumentParser(description="Castlevania Advance Collection 한글 ROM 주입기")
    ap.add_argument("--windata", required=True, help="Steam .../Castlevania Advance Collection/windata 경로")
    ap.add_argument("--freemote", required=True, help="FreeMote-v4.6.1 폴더 경로")
    ap.add_argument("--circle", help="서클 오브 더 문 한글 ROM (.gba)")
    ap.add_argument("--byakuya", help="백야의 협주곡 한글 ROM (.gba)")
    ap.add_argument("--akatsuki", help="효월의 원무곡 한글 ROM (.gba)")
    ap.add_argument("--draculaxx", help="악마성 드라큘라 XX 한글 ROM (.smc/.sfc)")
    ap.add_argument("--work", default=None, help="작업 폴더 (기본: <windata>/_krpatch_work)")
    ap.add_argument("--install", action="store_true", help="windata에 직접 설치(백업 후 덮어쓰기)")
    args = ap.parse_args()

    windata = Path(args.windata)
    fm = Path(args.freemote)
    psbdec = fm / "PsbDecompile.exe"
    psbuild = fm / "PsBuild.exe"
    for p in (windata / "alldata.bin", windata / "alldata.psb.m", psbdec, psbuild):
        if not p.exists():
            raise SystemExit(f"파일 없음: {p}")

    roms = {}
    for name, cli in (("circle", args.circle), ("byakuya", args.byakuya),
                      ("akatsuki", args.akatsuki), ("draculaxx", args.draculaxx)):
        if cli:
            roms[name] = Path(cli)
    if not roms:
        raise SystemExit("교체할 한글 ROM을 하나 이상 지정하세요 (--circle 등).")

    work = Path(args.work) if args.work else windata / "_krpatch_work"
    ext = work / "extract"      # 1차 추출(원본)
    aligned = work / "aligned"  # 최종 정렬본
    for d in (ext, aligned):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    print("[1/6] 원본 아카이브 추출 ...")
    run([psbdec, "info-psb", "-k", KEY, "-l", KEYLEN,
         "-b", windata / "alldata.bin", "-o", ext, windata / "alldata.psb.m"])
    orig_manifest = json.load(open(ext / "alldata.psb.m.json", encoding="utf-8"))
    order = list(orig_manifest["file_info"].keys())  # 원본 엔트리 순서(정렬 시 보존)

    print("[2/6] ROM 교체 ...")
    romdir = ext / "alldata"
    for name, src in roms.items():
        entry, slot, code = TARGETS[name]
        data = load_rom(src, slot, code)
        # Windows 대소문자 무시 파일 찾기
        target = romdir / entry
        if not target.exists():
            cands = [p for p in (romdir / "system/roms").glob("*")
                     if p.name.lower() == entry.split("/")[-1].lower()]
            if not cands:
                raise SystemExit(f"아카이브에 엔트리 없음: {entry}")
            target = cands[0]
        target.write_bytes(data)
        print(f"    OK {entry.split('/')[-1]:44} <- {src.name} ({len(data)}B)")

    print("[3/6] 1차 리팩(FreeMote, 조밀 패킹) ...")
    # PsBuild info-psb 는 출력물을 CWD에 쓰고 소스 폴더도 CWD 기준으로 찾으므로 cwd=ext
    run([psbuild, "info-psb", "-k", KEY, "-l", KEYLEN, "alldata.psb.m.json"], cwd=ext)
    tight_bin = ext / "alldata.bin"
    tight_m = ext / "alldata.psb.m"

    print("[4/6] 리팩본 재추출로 올바른 암호화 블롭 위치 획득 ...")
    rex = work / "reextract"
    if rex.exists():
        shutil.rmtree(rex)
    run([psbdec, "info-psb", "-k", KEY, "-l", KEYLEN, "-b", tight_bin, "-o", rex, tight_m])
    rep = json.load(open(rex / "alldata.psb.m.json", encoding="utf-8"))["file_info"]
    repci = {k.lower(): v for k, v in rep.items()}
    body_src = tight_bin.read_bytes()

    print("[5/6] 0x800 정렬 재배치 + 매니페스트 재컴파일 ...")
    new_body = bytearray()
    new_fi = {}
    for key in order:
        off, ln = repci[key.lower()]
        blob = body_src[off:off + ln]
        pad = (-len(new_body)) % ALIGN
        if pad:
            new_body += b"\x00" * pad
        new_fi[key] = [len(new_body), ln]
        new_body += blob
    pad = (-len(new_body)) % ALIGN
    if pad:
        new_body += b"\x00" * pad
    manifest = json.load(open(ext / "alldata.psb.m.json", encoding="utf-8"))
    manifest["file_info"] = new_fi
    json.dump(manifest, open(aligned / "alldata.psb.m.json", "w", encoding="utf-8"), ensure_ascii=False)
    shutil.copyfile(ext / "alldata.psb.m.resx.json", aligned / "alldata.psb.m.resx.json")
    (aligned / "alldata.bin").write_bytes(new_body)
    run([psbuild, "alldata.psb.m.json"], cwd=aligned)  # plain compile → aligned/alldata.psb.m
    assert all(v[0] % ALIGN == 0 for v in new_fi.values()), "정렬 실패"
    print(f"    aligned: {len(new_fi)}/{len(new_fi)} 엔트리 0x800 정렬, body {len(new_body)}B")

    print("[6/6] 검증(재추출 후 교체 ROM 바이트 확인) ...")
    vfy = work / "verify"
    if vfy.exists():
        shutil.rmtree(vfy)
    run([psbdec, "info-psb", "-k", KEY, "-l", KEYLEN,
         "-b", aligned / "alldata.bin", "-o", vfy, aligned / "alldata.psb.m"])
    for name, src in roms.items():
        entry, slot, code = TARGETS[name]
        want = load_rom(src, slot, code)
        cands = [p for p in (vfy / "alldata/system/roms").glob("*")
                 if p.name.lower() == entry.split("/")[-1].lower()]
        got = cands[0].read_bytes()
        assert got == want, f"검증 실패: {entry}"
        print(f"    OK {entry.split('/')[-1]:44} 일치")

    out_bin = aligned / "alldata.bin"
    out_m = aligned / "alldata.psb.m"
    print(f"\n완료: {out_bin} ({out_bin.stat().st_size}B)\n      {out_m}")

    if args.install:
        ts = time.strftime("%Y%m%d-%H%M%S")
        bak = windata / f"_backup-{ts}"
        bak.mkdir(exist_ok=True)
        shutil.copyfile(windata / "alldata.bin", bak / "alldata.bin")
        shutil.copyfile(windata / "alldata.psb.m", bak / "alldata.psb.m")
        print(f"\n백업: {bak}")
        shutil.copyfile(out_bin, windata / "alldata.bin")
        shutil.copyfile(out_m, windata / "alldata.psb.m")
        print("설치 완료. 게임 내 언어를 '일본어'로 설정해 플레이하세요.")
    else:
        print("\n(--install 미지정: 게임에 설치하지 않음. 위 두 파일을 windata에 복사하면 됨)")


if __name__ == "__main__":
    main()
