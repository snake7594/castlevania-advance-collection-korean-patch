# -*- coding: utf-8 -*-
"""
캐슬바니아 어드밴스 컬렉션 한글패치 설치기 (GUI)

구성: ① 게임 폴더 설정 → ② 한글패치 ROM 선택 → ③ 패치 설치
FreeMote(PsbDecompile/PsBuild)에 의존하며 번들하지 않는다(CC BY-NC-SA).
"""
import sys
import threading
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marchive_core as core

FREEMOTE_URL = "https://github.com/UlyssesWu/FreeMote/releases"
PAD = 8


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("캐슬바니아 어드밴스 컬렉션 한글패치 설치기")
        self.geometry("760x640")
        self.minsize(680, 560)
        self._build()
        self.after(200, self._autodetect)

    # ---------------------------------------------------------------- UI
    def _build(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except Exception:
            pass
        main = ttk.Frame(self, padding=PAD)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="캐슬바니아 어드밴스 컬렉션 한글패치 설치기",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(main, text="Steam 게임의 ROM을 한글패치본으로 교체합니다. "
                             "게임 내 언어를 '일본어'로 설정해야 한글이 표시됩니다.",
                  foreground="#555").pack(anchor="w", pady=(0, PAD))

        # ① 게임 폴더
        f1 = ttk.LabelFrame(main, text="① 게임 폴더 (Steam …\\Castlevania Advance Collection\\windata)",
                            padding=PAD)
        f1.pack(fill="x", pady=4)
        self.var_windata = tk.StringVar()
        self.lbl_windata = self._path_row(f1, self.var_windata, self._pick_windata,
                                          self._detect_windata)

        # ② FreeMote
        f2 = ttk.LabelFrame(main, text="② FreeMote 폴더 (PsbDecompile.exe / PsBuild.exe 포함)",
                            padding=PAD)
        f2.pack(fill="x", pady=4)
        self.var_fm = tk.StringVar()
        self.lbl_fm = self._path_row(f2, self.var_fm, self._pick_fm, self._detect_fm,
                                     extra=("FreeMote 받기", lambda: webbrowser.open(FREEMOTE_URL)))

        # ③ 한글 ROM 선택
        f3 = ttk.LabelFrame(main, text="③ 한글패치 ROM 선택 (교체할 게임만 선택하면 됩니다)",
                            padding=PAD)
        f3.pack(fill="x", pady=4)
        self.rom_vars = {}
        for key in ("circle", "byakuya", "akatsuki", "draculaxx"):
            self.rom_vars[key] = self._rom_row(f3, key)

        # 실행
        f4 = ttk.Frame(main)
        f4.pack(fill="x", pady=(PAD, 4))
        self.var_install = tk.BooleanVar(value=True)
        ttk.Checkbutton(f4, text="게임에 바로 설치 (원본 자동 백업)",
                        variable=self.var_install).pack(side="left")
        self.btn = ttk.Button(f4, text="패치 설치하기", command=self._start)
        self.btn.pack(side="right", ipadx=12, ipady=2)

        # 로그
        self.log = scrolledtext.ScrolledText(main, height=12, state="disabled",
                                             font=("Consolas", 9), background="#111",
                                             foreground="#ddd")
        self.log.pack(fill="both", expand=True, pady=(4, 0))
        self.status = ttk.Label(main, text="준비됨", relief="sunken", anchor="w")
        self.status.pack(fill="x", pady=(4, 0))

    def _path_row(self, parent, var, pick, detect, extra=None):
        row = ttk.Frame(parent); row.pack(fill="x")
        ent = ttk.Entry(row, textvariable=var)
        ent.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="자동 감지", command=detect, width=9).pack(side="left", padx=3)
        ttk.Button(row, text="찾아보기", command=pick, width=9).pack(side="left")
        if extra:
            ttk.Button(row, text=extra[0], command=extra[1], width=12).pack(side="left", padx=3)
        lbl = ttk.Label(parent, text="", foreground="#c00")
        lbl.pack(anchor="w", pady=(2, 0))
        var.trace_add("write", lambda *_: self._revalidate())
        return lbl

    def _rom_row(self, parent, key):
        row = ttk.Frame(parent); row.pack(fill="x", pady=1)
        ttk.Label(row, text=core.LABELS[key], width=34).pack(side="left")
        var = tk.StringVar()
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="찾아보기", width=9,
                   command=lambda: self._pick_rom(key, var)).pack(side="left", padx=3)
        return var

    # ---------------------------------------------------------------- 동작
    def _log(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", str(msg) + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.update_idletasks()

    def _autodetect(self):
        self._detect_windata(silent=True)
        self._detect_fm(silent=True)

    def _detect_windata(self, silent=False):
        p = core.autodetect_windata()
        if p:
            self.var_windata.set(p)
        elif not silent:
            messagebox.showinfo("자동 감지", "게임 폴더를 찾지 못했습니다. '찾아보기'로 지정하세요.")

    def _detect_fm(self, silent=False):
        p = core.autodetect_freemote()
        if p:
            self.var_fm.set(p)
        elif not silent:
            messagebox.showinfo("자동 감지",
                                "FreeMote 폴더를 찾지 못했습니다.\n"
                                "'FreeMote 받기'로 내려받아 압축을 푼 뒤 '찾아보기'로 지정하세요.")

    def _pick_windata(self):
        d = filedialog.askdirectory(title="windata 폴더 선택")
        if d:
            self.var_windata.set(d)

    def _pick_fm(self):
        d = filedialog.askdirectory(title="FreeMote 폴더 선택")
        if d:
            self.var_fm.set(d)

    def _pick_rom(self, key, var):
        types = [("ROM", "*.gba *.smc *.sfc"), ("모든 파일", "*.*")]
        f = filedialog.askopenfilename(title=f"{core.LABELS[key]} 한글 ROM 선택", filetypes=types)
        if f:
            var.set(f)

    def _revalidate(self):
        wd = self.var_windata.get().strip()
        self.lbl_windata.configure(
            text="" if (wd and core.valid_windata(wd)) else
            ("alldata.bin / alldata.psb.m 를 찾을 수 없습니다." if wd else ""))
        fm = self.var_fm.get().strip()
        self.lbl_fm.configure(
            text="" if (fm and core.valid_freemote(fm)) else
            ("PsbDecompile.exe / PsBuild.exe 를 찾을 수 없습니다." if fm else ""))

    def _start(self):
        wd, fm = self.var_windata.get().strip(), self.var_fm.get().strip()
        if not core.valid_windata(wd):
            messagebox.showerror("오류", "올바른 게임 폴더(windata)를 지정하세요."); return
        if not core.valid_freemote(fm):
            messagebox.showerror("오류", "올바른 FreeMote 폴더를 지정하세요."); return
        roms = {k: v.get().strip() for k, v in self.rom_vars.items() if v.get().strip()}
        if not roms:
            messagebox.showerror("오류", "교체할 한글 ROM을 하나 이상 선택하세요."); return
        install = self.var_install.get()
        if install and not messagebox.askyesno(
                "확인", "게임의 alldata.bin 을 교체합니다.\n원본은 자동 백업됩니다. 진행할까요?"):
            return
        self.btn.configure(state="disabled")
        self.status.configure(text="패치 진행 중 ...")
        threading.Thread(target=self._worker, args=(wd, fm, roms, install), daemon=True).start()

    def _worker(self, wd, fm, roms, install):
        try:
            res = core.patch_collection(wd, fm, roms, install=install, log=self._log_safe)
            msg = "패치가 완료되었습니다!\n\n"
            if res["installed"]:
                msg += "게임을 실행하고 언어를 '일본어(Japanese)'로 설정하세요.\n"
                msg += f"원본 백업: {res['backup']}\n\n"
                msg += "※ Steam '게임 파일 무결성 검사'를 돌리면 패치가 원복됩니다."
            else:
                msg += f"생성된 파일:\n{res['output_bin']}\n{res['output_psb']}"
            self.after(0, lambda: self._done(True, msg))
        except Exception as e:
            self.after(0, lambda: self._done(False, str(e)))

    def _log_safe(self, msg):
        self.after(0, lambda: self._log(msg))

    def _done(self, ok, msg):
        self.btn.configure(state="normal")
        self.status.configure(text="완료" if ok else "실패")
        (messagebox.showinfo if ok else messagebox.showerror)(
            "완료" if ok else "오류", msg)


def main():
    if "--selftest" in sys.argv:
        app = App()
        app.after(300, app.destroy)
        app.mainloop()
        print("selftest OK")
        return
    App().mainloop()


if __name__ == "__main__":
    main()
