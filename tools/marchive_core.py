# -*- coding: utf-8 -*-
"""
Castlevania Advance Collection — Korean ROM 주입 코어 로직 (GUI/CLI 공용)

M2 MArchive(alldata.psb.m + alldata.bin) 언팩 → ROM 교체 → 0x800 정렬 리팩.
FreeMote(PsbDecompile.exe / PsBuild.exe)에 의존한다. (번들하지 않음: CC BY-NC-SA)

핵심(../TECHNICAL.md):
  - 키 "25G/xpvTbsb+6", length 64, zlib (game.exe 0x224FA4)
  - 엔진은 엔트리 0x800 정렬을 요구 → 리팩 후 반드시 정렬 재배치
"""
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

KEY = "25G/xpvTbsb+6"
KEYLEN = 64
ALIGN = 0x800
GBA_LOGO = bytes.fromhex("24FFAE51")

# name -> (아카이브 엔트리 경로, 슬롯/패딩 크기, GBA 게임코드 검증값 or None)
TARGETS = {
    "circle":    ("system/roms/01_Circle_JP.patch_210623m.bin.m",   8 * 1024 * 1024, b"AAMJ"),
    "byakuya":   ("system/roms/02_Byakuya_JP.patch_210520m.bin.m",  8 * 1024 * 1024, b"ACHJ"),
    "akatsuki":  ("system/roms/03_Akatsuki_JP.patch_210623m.bin.m", 8 * 1024 * 1024, b"A2CJ"),
    "draculaxx": ("system/roms/AkumajouDraculaXX_0408.SFC.m",       2 * 1024 * 1024, None),
}
LABELS = {
    "circle": "서클 오브 더 문 (Circle of the Moon)",
    "byakuya": "백야의 협주곡 (Harmony of Dissonance)",
    "akatsuki": "효월의 원무곡 (Aria of Sorrow)",
    "draculaxx": "악마성 드라큘라 XX (SNES)",
}


class PatchError(Exception):
    pass


# ---------------------------------------------------------------- 자동 감지

def autodetect_windata():
    """Steam 라이브러리에서 Castlevania Advance Collection\\windata 를 찾는다."""
    candidates = []
    steam_roots = []
    # 기본 Steam 위치
    for base in [r"C:\Program Files (x86)\Steam", r"C:\Program Files\Steam",
                 r"D:\Steam", r"E:\Steam", r"D:\SteamLibrary", r"E:\SteamLibrary"]:
        p = Path(base)
        if p.exists():
            steam_roots.append(p)
    # libraryfolders.vdf 파싱 (추가 라이브러리)
    for sr in list(steam_roots):
        vdf = sr / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            try:
                import re
                txt = vdf.read_text(encoding="utf-8", errors="ignore")
                for m in re.finditer(r'"path"\s*"([^"]+)"', txt):
                    lp = Path(m.group(1).replace("\\\\", "\\"))
                    if lp.exists():
                        steam_roots.append(lp)
            except Exception:
                pass
    seen = set()
    for sr in steam_roots:
        cand = sr / "steamapps" / "common" / "Castlevania Advance Collection" / "windata"
        key = str(cand).lower()
        if key in seen:
            continue
        seen.add(key)
        if (cand / "alldata.bin").exists() and (cand / "alldata.psb.m").exists():
            candidates.append(cand)
    return str(candidates[0]) if candidates else ""


def autodetect_freemote():
    """PsbDecompile.exe / PsBuild.exe 를 가진 FreeMote 폴더를 찾는다."""
    import os
    search = []
    here = Path(__file__).resolve().parent
    search += [here, here / "FreeMote", here.parent / "FreeMote"]
    # 실행 파일(동결된 exe) 기준 위치
    import sys
    if getattr(sys, "frozen", False):
        exed = Path(sys.executable).resolve().parent
        search += [exed, exed / "FreeMote"]
    up = os.environ.get("USERPROFILE")
    if up:
        for name in ("Downloads", "Desktop", "Documents", ""):
            search.append(Path(up) / name if name else Path(up))
    for env in ("LOCALAPPDATA", "APPDATA"):
        v = os.environ.get(env)
        if v:
            search.append(Path(v))
    hits = []
    for base in search:
        try:
            if not base.exists():
                continue
            # 직접 폴더
            if (base / "PsbDecompile.exe").exists() and (base / "PsBuild.exe").exists():
                hits.append(base)
            # 한 단계 하위에서 FreeMote* 폴더 검색 (예: Downloads\FreeMote-v4.6.1)
            for sub in base.glob("FreeMote*"):
                if (sub / "PsbDecompile.exe").exists():
                    hits.append(sub)
                # 압축 해제 시 한 겹 더 들어가는 경우 (FreeMote-v4.6.1\FreeMote-v4.6.1)
                for sub2 in sub.glob("FreeMote*"):
                    if (sub2 / "PsbDecompile.exe").exists():
                        hits.append(sub2)
        except Exception:
            continue
    return str(hits[0]) if hits else ""


def valid_windata(path):
    p = Path(path)
    return (p / "alldata.bin").exists() and (p / "alldata.psb.m").exists()


def valid_freemote(path):
    p = Path(path)
    return (p / "PsbDecompile.exe").exists() and (p / "PsBuild.exe").exists()


# ---------------------------------------------------------------- 헬퍼

def _run(cmd, cwd=None, log=print):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       cwd=str(cwd) if cwd else None,
                       creationflags=0x08000000)  # CREATE_NO_WINDOW
    if r.returncode != 0:
        log((r.stdout or "")[-1500:])
        log((r.stderr or "")[-1500:])
        raise PatchError(f"FreeMote 명령 실패 (exit {r.returncode})")
    return r.stdout


def _load_rom(src: Path, slot: int, code):
    data = src.read_bytes()
    if len(data) > slot:
        raise PatchError(f"{src.name}: {len(data):,}B 는 슬롯 {slot:,}B 보다 큽니다.")
    if code is not None:
        if data[4:8] != GBA_LOGO:
            raise PatchError(f"{src.name}: GBA 닌텐도 로고가 없습니다. 올바른 ROM인지 확인하세요.")
        if data[0xAC:0xB0] != code:
            raise PatchError(f"{src.name}: 게임코드 {data[0xAC:0xB0]!r} 가 기대값 {code.decode()} 와 다릅니다.\n"
                             f"(일본판 기반 한글 ROM이 맞는지 확인하세요)")
    if len(data) < slot:
        data += b"\x00" * (slot - len(data))
    return data


# ---------------------------------------------------------------- 메인

def patch_collection(windata, freemote, roms: dict, install=True, work=None, log=print):
    """
    windata : Steam .../windata 폴더
    freemote: FreeMote 폴더
    roms    : {"circle": path, "byakuya": path, "akatsuki": path, "draculaxx": path} (부분 가능)
    반환    : {"output_bin":..., "output_psb":..., "backup":..., "installed":bool}
    """
    windata = Path(windata)
    fm = Path(freemote)
    if not valid_windata(windata):
        raise PatchError("게임 폴더에 alldata.bin / alldata.psb.m 가 없습니다.")
    if not valid_freemote(fm):
        raise PatchError("FreeMote 폴더에 PsbDecompile.exe / PsBuild.exe 가 없습니다.")
    roms = {k: Path(v) for k, v in roms.items() if v}
    if not roms:
        raise PatchError("교체할 한글 ROM을 하나 이상 선택하세요.")
    for k, v in roms.items():
        if not v.exists():
            raise PatchError(f"파일 없음: {v}")

    psbdec = fm / "PsbDecompile.exe"
    psbuild = fm / "PsBuild.exe"
    work = Path(work) if work else windata / "_krpatch_work"
    ext = work / "extract"
    aligned = work / "aligned"
    rex = work / "reextract"
    for d in (ext, aligned, rex):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    log("[1/6] 원본 아카이브 추출 중 ...")
    _run([psbdec, "info-psb", "-k", KEY, "-l", KEYLEN,
          "-b", windata / "alldata.bin", "-o", ext, windata / "alldata.psb.m"], log=log)
    order = list(json.load(open(ext / "alldata.psb.m.json", encoding="utf-8"))["file_info"].keys())

    log("[2/6] 한글 ROM 교체 중 ...")
    romdir = ext / "alldata"
    for name, src in roms.items():
        entry, slot, code = TARGETS[name]
        data = _load_rom(src, slot, code)
        target = romdir / entry
        if not target.exists():
            cands = [p for p in (romdir / "system/roms").glob("*")
                     if p.name.lower() == entry.split("/")[-1].lower()]
            if not cands:
                raise PatchError(f"아카이브에 엔트리 없음: {entry}")
            target = cands[0]
        target.write_bytes(data)
        log(f"    OK  {LABELS[name]}  ({len(data):,}B)")

    log("[3/6] 1차 리팩(FreeMote) ...")
    _run([psbuild, "info-psb", "-k", KEY, "-l", KEYLEN, "alldata.psb.m.json"], cwd=ext, log=log)

    log("[4/6] 암호화 블롭 위치 획득(재추출) ...")
    _run([psbdec, "info-psb", "-k", KEY, "-l", KEYLEN,
          "-b", ext / "alldata.bin", "-o", rex, ext / "alldata.psb.m"], log=log)
    rep = json.load(open(rex / "alldata.psb.m.json", encoding="utf-8"))["file_info"]
    repci = {k.lower(): v for k, v in rep.items()}
    body_src = (ext / "alldata.bin").read_bytes()

    log("[5/6] 0x800 정렬 재배치 + 매니페스트 재컴파일 ...")
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
    _run([psbuild, "alldata.psb.m.json"], cwd=aligned, log=log)
    if not all(v[0] % ALIGN == 0 for v in new_fi.values()):
        raise PatchError("정렬 실패(내부 오류)")

    log("[6/6] 검증(재추출 후 ROM 바이트 확인) ...")
    vfy = work / "verify"
    if vfy.exists():
        shutil.rmtree(vfy)
    _run([psbdec, "info-psb", "-k", KEY, "-l", KEYLEN,
          "-b", aligned / "alldata.bin", "-o", vfy, aligned / "alldata.psb.m"], log=log)
    for name, src in roms.items():
        entry, slot, code = TARGETS[name]
        want = _load_rom(src, slot, code)
        cands = [p for p in (vfy / "alldata/system/roms").glob("*")
                 if p.name.lower() == entry.split("/")[-1].lower()]
        if not cands or cands[0].read_bytes() != want:
            raise PatchError(f"검증 실패: {LABELS[name]}")
    log(f"    검증 완료: {len(new_fi)}/{len(new_fi)} 엔트리 0x800 정렬, {len(new_body):,}B")

    out_bin = aligned / "alldata.bin"
    out_psb = aligned / "alldata.psb.m"
    result = {"output_bin": str(out_bin), "output_psb": str(out_psb),
              "backup": None, "installed": False}

    if install:
        ts = time.strftime("%Y%m%d-%H%M%S")
        bak = windata / f"_backup-{ts}"
        bak.mkdir(exist_ok=True)
        shutil.copyfile(windata / "alldata.bin", bak / "alldata.bin")
        shutil.copyfile(windata / "alldata.psb.m", bak / "alldata.psb.m")
        shutil.copyfile(out_bin, windata / "alldata.bin")
        shutil.copyfile(out_psb, windata / "alldata.psb.m")
        result["backup"] = str(bak)
        result["installed"] = True
        log(f"    백업: {bak}")
        log("    설치 완료.")
    return result
