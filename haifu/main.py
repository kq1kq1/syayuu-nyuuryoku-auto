"""
社有入力Bot v2.0
メインGUI（tkinter）
"""
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

if getattr(sys, "frozen", False):
    base_dir = os.path.dirname(sys.executable)
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, base_dir)

EXCEL_FILENAME              = "社有入力テンプレート.xlsx"
PARENT_PHOTO_DIR            = os.path.join(base_dir, "物件写真")
DEFAULT_PHOTO_FOLDER        = os.path.join(PARENT_PHOTO_DIR, "同仕様モデルハウス")
HOMES_DEFAULT_PHOTO_FOLDER  = os.path.join(PARENT_PHOTO_DIR, "ホームズ写真")
IMAGE_EXTS                  = {".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"}


def _zen_to_han(s: str) -> str:
    """全角数字を半角に変換"""
    return s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))


# ==============================
# 起動時ダイアログ（建築確認番号 + 物件価格）
# ==============================
class SelectDialog(tk.Toplevel):
    """汎用リスト選択ダイアログ（物件選択・タブ選択で共用）"""

    def __init__(self, parent, options: list,
                 dialog_title: str = "選択",
                 dialog_label: str = "選んでください",
                 ok_label: str = "決定"):
        super().__init__(parent)
        self.result = None  # 選択されたインデックス（キャンセル時は None）

        self.title(dialog_title)
        self.geometry("620x320")
        self.resizable(False, False)
        self.grab_set()
        self.focus_set()
        self.transient(parent)

        tk.Label(self, text=dialog_label,
                 font=("Yu Gothic UI", 11, "bold")).pack(
                 pady=(16, 6), padx=16, anchor="w")
        tk.Label(self, text=f"※ {len(options)}件見つかりました",
                 font=("Yu Gothic UI", 9), fg="#888").pack(
                 padx=16, anchor="w")

        list_frame = tk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=16, pady=8)

        sb = ttk.Scrollbar(list_frame)
        sb.pack(side="right", fill="y")

        self._lb = tk.Listbox(list_frame, font=("Yu Gothic UI", 10),
                              yscrollcommand=sb.set, selectmode="single",
                              activestyle="dotbox", height=8)
        self._lb.pack(side="left", fill="both", expand=True)
        sb.config(command=self._lb.yview)

        for opt in options:
            self._lb.insert("end", f"  {opt}")
        self._lb.selection_set(0)  # 先頭を初期選択

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=(0, 14))
        ttk.Button(btn_frame, text=ok_label,
                   command=self._ok, width=18).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="キャンセル",
                   command=self._cancel, width=12).pack(side="left")

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.wait_window()

    def _ok(self):
        sel = self._lb.curselection()
        if sel:
            self.result = sel[0]
        self.destroy()

    def _cancel(self):
        self.destroy()


# 後方互換エイリアス（既存コードへの影響なし）
BukkenSelectDialog = SelectDialog


class StartupDialog(tk.Toplevel):
    """物件情報入力ダイアログ（起動時・次の物件へ）"""

    def __init__(self, parent, kenchu_default="", price_default=""):
        super().__init__(parent)
        self.result_kenchu = None
        self.result_price  = None

        self.title("物件情報の入力")
        self.geometry("420x220")
        self.resizable(False, False)
        self.grab_set()
        self.focus_set()
        self.transient(parent)

        frame = tk.Frame(self, padx=24, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text="物件情報を入力してください",
                 font=("Yu Gothic UI", 11, "bold")).grid(
                 row=0, column=0, columnspan=2, pady=(0, 12), sticky="w")

        # 建築確認番号
        tk.Label(frame, text="建築確認番号",
                 font=("Yu Gothic UI", 10)).grid(row=1, column=0, sticky="w", pady=4)
        self._kenchu_entry = ttk.Entry(frame, font=("Yu Gothic UI", 11), width=22)
        self._kenchu_entry.grid(row=1, column=1, sticky="ew", padx=(10,0), pady=4)
        self._kenchu_entry.insert(0, kenchu_default)

        tk.Label(frame, text="※ 中古物件など不要な場合は空欄でOK",
                 font=("Yu Gothic UI", 8), fg="#888").grid(
                 row=2, column=0, columnspan=2, sticky="w", padx=(0, 0))

        # 物件価格
        tk.Label(frame, text="物件価格（万円）",
                 font=("Yu Gothic UI", 10)).grid(row=3, column=0, sticky="w", pady=4)
        self._price_entry = ttk.Entry(frame, font=("Yu Gothic UI", 11), width=22)
        self._price_entry.grid(row=3, column=1, sticky="ew", padx=(10,0), pady=4)
        self._price_entry.insert(0, price_default)

        tk.Label(frame, text="※ 金利・返済期間はExcelで変更できます",
                 font=("Yu Gothic UI", 8), fg="#888").grid(
                 row=4, column=0, columnspan=2, sticky="w", pady=(0, 12))

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2)
        ttk.Button(btn_frame, text="OK", command=self._ok, width=12).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="キャンセル", command=self._cancel, width=12).pack(side="left")

        frame.columnconfigure(1, weight=1)
        self._kenchu_entry.focus()
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())
        self.wait_window()

    def _ok(self):
        kenchu = self._kenchu_entry.get().strip()
        price  = _zen_to_han(self._price_entry.get().strip())
        if not price:
            messagebox.showwarning("確認", "物件価格を入力してください", parent=self)
            return
        if not price.isdigit():
            messagebox.showwarning("確認", "物件価格は数字のみで入力してください（例: 4798）", parent=self)
            return
        self.result_kenchu = kenchu        # 空文字列も正常値（中古物件）
        self.result_price  = int(price)
        self.destroy()

    def _cancel(self):
        self.destroy()


# ==============================
# メインウィンドウ
# ==============================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()

        self.title("社有入力Bot v2.0")
        self.geometry("720x560")
        self.resizable(True, True)
        self.configure(bg="#f5f5f5")

        # フォルダ構成を作成しておく
        os.makedirs(DEFAULT_PHOTO_FOLDER, exist_ok=True)
        os.makedirs(HOMES_DEFAULT_PHOTO_FOLDER, exist_ok=True)

        self._photo_folder  = tk.StringVar(value=DEFAULT_PHOTO_FOLDER)
        self._kenchu_bangou = tk.StringVar(value="未入力")
        self._bukken_kakaku = tk.StringVar(value="未入力")
        self._bukken_type   = tk.StringVar(value="新築")  # "新築" or "中古"
        self._running       = False

        self._build_ui()
        self.deiconify()

        # mainloop開始後にダイアログを表示（200ms後）
        self.after(200, lambda: self._ask_bukken_info(first_time=True))

    # -------- Excel パス --------

    def _get_excel_path(self) -> str:
        return os.path.join(base_dir, EXCEL_FILENAME)

    # -------- ダイアログ --------

    def _ask_bukken_info(self, first_time=False):
        dlg = StartupDialog(self)
        if dlg.result_kenchu is not None:
            self._kenchu_bangou.set(dlg.result_kenchu if dlg.result_kenchu else "なし（中古）")
            self._bukken_kakaku.set(str(dlg.result_price))
            if not first_time:
                self._log("=== 次の物件へ ===")
                self._log(f"建築確認番号: {dlg.result_kenchu}")
                self._log(f"物件価格: {dlg.result_price:,}万円")
                self._write_price_to_excel(dlg.result_price)
        elif first_time:
            self._kenchu_bangou.set("未入力")
            self._bukken_kakaku.set("未入力")

    def _write_price_to_excel(self, price: int):
        """物件価格をExcelの支払い例シートB2に書き込む（記録用）"""
        path = self._get_excel_path()
        if not os.path.exists(path):
            return
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path)
            if "支払い例" in wb.sheetnames:
                wb["支払い例"]["B2"] = price
                wb.save(path)
                self._log(f"Excel更新: 物件価格 {price:,}万円")
        except Exception as e:
            self._log(f"Excel書き込みエラー: {e}（Excelを閉じてから再試行してください）")

    # -------- UI構築 --------

    def _build_ui(self):
        # ヘッダー
        header = tk.Frame(self, bg="#1a5276", pady=10)
        header.pack(fill="x")
        tk.Label(header, text="社有入力Bot  v2.0",
                 font=("Yu Gothic UI", 16, "bold"),
                 fg="white", bg="#1a5276").pack()

        main = tk.Frame(self, bg="#f5f5f5", padx=20, pady=12)
        main.pack(fill="both", expand=True)

        # 物件情報表示
        info_frame = ttk.LabelFrame(main, text=" 現在の物件情報 ", padding=10)
        info_frame.pack(fill="x", pady=(0, 8))
        info_grid = tk.Frame(info_frame)
        info_grid.pack(fill="x")

        tk.Label(info_grid, text="建築確認番号:",
                 font=("Yu Gothic UI", 10)).grid(row=0, column=0, sticky="w", padx=(0,6))
        tk.Label(info_grid, textvariable=self._kenchu_bangou,
                 font=("Yu Gothic UI", 11, "bold"), fg="#1a5276",
                 width=20, anchor="w").grid(row=0, column=1, sticky="w")

        tk.Label(info_grid, text="物件価格:",
                 font=("Yu Gothic UI", 10)).grid(row=1, column=0, sticky="w", padx=(0,6), pady=(4,0))
        price_row = tk.Frame(info_grid)
        price_row.grid(row=1, column=1, sticky="w", pady=(4,0))
        tk.Label(price_row, textvariable=self._bukken_kakaku,
                 font=("Yu Gothic UI", 11, "bold"), fg="#1a5276",
                 width=10, anchor="w").pack(side="left")
        tk.Label(price_row, text="万円",
                 font=("Yu Gothic UI", 10)).pack(side="left")

        ttk.Button(info_grid, text="次の物件へ（情報をリセット）",
                   command=lambda: self._ask_bukken_info()).grid(
            row=0, column=2, rowspan=2, padx=(20,0), ipadx=6, ipady=4)

        # 物件タイプ（新築 / 中古）
        tk.Label(info_grid, text="物件タイプ:",
                 font=("Yu Gothic UI", 10)).grid(row=2, column=0, sticky="w", padx=(0,6), pady=(6,0))
        type_frame = tk.Frame(info_grid)
        type_frame.grid(row=2, column=1, sticky="w", pady=(6,0))
        ttk.Radiobutton(type_frame, text="新築", variable=self._bukken_type,
                        value="新築").pack(side="left", padx=(0,12))
        ttk.Radiobutton(type_frame, text="中古", variable=self._bukken_type,
                        value="中古").pack(side="left")

        # 写真フォルダ選択
        photo_frame = ttk.LabelFrame(main, text=" 写真フォルダ ", padding=8)
        photo_frame.pack(fill="x", pady=(0, 8))

        pi = tk.Frame(photo_frame)
        pi.pack(fill="x")
        ttk.Entry(pi, textvariable=self._photo_folder,
                  font=("Yu Gothic UI", 9)).pack(side="left", fill="x", expand=True, padx=(0,6))
        ttk.Button(pi, text="参照...", command=self._browse_photo).pack(side="right")

        pi2 = tk.Frame(photo_frame)
        pi2.pack(fill="x", pady=(6, 0))
        ttk.Button(pi2, text="連番リネーム（撮影順）",
                   command=self._rename_photos).pack(side="left", ipadx=6, ipady=2)
        tk.Label(pi2,
                 text="※ 中古物件など撮影写真を使う場合：フォルダを選んでボタンを押すだけ。Excelのファイル名列は空白でOK",
                 font=("Yu Gothic UI", 8), fg="#888").pack(side="left", padx=(8, 0))

        # 自動入力ボタン群
        ops_frame = ttk.LabelFrame(main, text=" 自動入力 ", padding=12)
        ops_frame.pack(fill="x", pady=(0, 8))

        ttk.Button(ops_frame,
                   text="スーモに入力する（基本情報 → 内外観・その他画像 → 支払い例他 → レイアウト指定）",
                   command=lambda: self._run(self._fill_all_suumo)).pack(
                   fill="x", ipadx=4, ipady=8)

        ttk.Button(ops_frame,
                   text="ホームズに入力する（物件編集 → 基本画像 → 外観・分譲地 → 内観）",
                   command=lambda: self._run(self._fill_all_homes)).pack(
                   fill="x", ipadx=4, ipady=8, pady=(6, 0))

        ttk.Button(ops_frame,
                   text="ピタクラに入力する（建築確認番号 → 外観内観写真 → キャプション → 文言）",
                   command=lambda: self._run(self._fill_all_pitakura)).pack(
                   fill="x", ipadx=4, ipady=8, pady=(6, 0))

        ttk.Button(ops_frame,
                   text="スカイヤーズに入力する（担当者選択 → おすすめチェック → 建確番号 → 画像 → 文言）",
                   command=lambda: self._run(self._fill_all_skyyers)).pack(
                   fill="x", ipadx=4, ipady=8, pady=(6, 0))

        # Excel存在確認表示
        tpl_frame = tk.Frame(main, bg="#f5f5f5")
        tpl_frame.pack(fill="x", pady=(0, 8))
        excel_path = self._get_excel_path()
        exists_mark = "✓" if os.path.exists(excel_path) else "✗ (未作成)"
        tk.Label(tpl_frame, text=f"Excel: {exists_mark}  {EXCEL_FILENAME}",
                 font=("Yu Gothic UI", 8), fg="#555", bg="#f5f5f5").pack(side="left")

        # ログ
        log_frame = ttk.LabelFrame(main, text=" ログ ", padding=5)
        log_frame.pack(fill="both", expand=True)
        self._log_text = tk.Text(log_frame, font=("Consolas", 9),
                                 state="disabled", bg="#1e1e1e", fg="#d4d4d4",
                                 relief="flat", wrap="word")
        sb = ttk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=sb.set)
        self._log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        # フッター
        footer = tk.Frame(self, bg="#e0e0e0", pady=3)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer,
                 text="使い方: ①start_chrome.batでChrome起動 → ②SUUMOの物件編集ページを開く → ③入力ボタンをクリック",
                 font=("Yu Gothic UI", 8), fg="#555", bg="#e0e0e0").pack()

    # -------- 物件タイプ --------

    def _is_chuko(self) -> bool:
        return self._bukken_type.get() == "中古"

    # -------- ブラウズ --------

    def _browse_photo(self):
        path = filedialog.askdirectory(title="写真フォルダを選択")
        if path:
            self._photo_folder.set(path)

    # -------- 連番リネーム --------

    def _rename_photos(self):
        folder = self._photo_folder.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("確認", "写真フォルダを選択してください")
            return

        # 同仕様モデルハウスフォルダは保護
        if os.path.abspath(folder) == os.path.abspath(DEFAULT_PHOTO_FOLDER):
            messagebox.showwarning("確認",
                "同仕様モデルハウスのファイルはリネームできません。\n"
                "中古物件の場合は「参照...」で別フォルダを選択してください。")
            return

        # 画像ファイルを更新日時順に取得
        files = [
            f for f in os.listdir(folder)
            if os.path.splitext(f)[1] in IMAGE_EXTS
        ]
        if not files:
            messagebox.showinfo("確認", "フォルダ内に画像ファイルが見つかりません")
            return

        files.sort(key=lambda f: os.path.getmtime(os.path.join(folder, f)))

        # 確認ダイアログ
        preview = "\n".join(
            f"  {f}  →  {str(i+1).zfill(2)}.jpg"
            for i, f in enumerate(files[:5])
        )
        if len(files) > 5:
            preview += f"\n  ...（全{len(files)}枚）"

        if not messagebox.askyesno("連番リネームの確認",
                f"以下の順でリネームします（撮影日時順）:\n\n{preview}\n\n実行しますか？"):
            return

        # リネーム実行
        errors = []
        # 一時名でリネーム（既存ファイル名との衝突を避ける）
        tmp_names = []
        for i, fname in enumerate(files):
            src = os.path.join(folder, fname)
            tmp = os.path.join(folder, f"__tmp_{i}__.jpg")
            try:
                os.rename(src, tmp)
                tmp_names.append(tmp)
            except Exception as e:
                errors.append(f"{fname}: {e}")

        # 最終名でリネーム
        for i, tmp in enumerate(tmp_names):
            dst = os.path.join(folder, f"{str(i+1).zfill(2)}.jpg")
            try:
                os.rename(tmp, dst)
            except Exception as e:
                errors.append(f"tmp→{i+1:02d}.jpg: {e}")

        if errors:
            self._log("リネームエラー:\n" + "\n".join(errors))
        else:
            self._log(f"連番リネーム完了: {len(files)}枚 → 01.jpg〜{len(files):02d}.jpg")
            messagebox.showinfo("完了",
                f"{len(files)}枚を連番リネームしました\n01.jpg〜{len(files):02d}.jpg")

    # -------- スレッド実行 --------

    def _run(self, func):
        if self._running:
            messagebox.showinfo("確認", "処理中です。完了をお待ちください。")
            return
        threading.Thread(target=func, daemon=True).start()

    # -------- 共通チェック --------

    def _check_inputs(self):
        if self._bukken_kakaku.get() in ("未入力", ""):
            self._log("エラー: 物件価格が入力されていません")
            self.after(0, self._ask_bukken_info)
            return False
        excel_path = self._get_excel_path()
        if not os.path.exists(excel_path):
            self._log(f"エラー: Excelテンプレートが見つかりません → {excel_path}")
            self._log("「Excelテンプレート作成」ボタンで先に作成してください")
            return False
        return True

    def _load_config(self):
        from excel_reader import read_site_config
        self._log("Excel読み込み中...")
        config = read_site_config(self._get_excel_path())
        self._log(f"担当者: {config.tantosha_name} / 金利: {config.kinri}% / 返済期間: {config.kikan}年")
        return config

    # -------- SUUMO 一括入力 --------

    def _fill_all_suumo(self):
        self._running = True
        try:
            if not self._check_inputs():
                return
            from excel_reader import read_site_config, read_photos, read_layout
            config = self._load_config()
            excel_path = self._get_excel_path()
            chuko = self._is_chuko()
            photo_sheet    = "写真（中古）"    if chuko else "写真"
            baishuu_sheet  = "売主コメント（中古）" if chuko else "売主コメント"
            photos         = read_photos(excel_path, sheet_name=photo_sheet)
            baishuu_photos = read_photos(excel_path, sheet_name=baishuu_sheet)
            layout_rows    = read_layout(excel_path)
            self._log(f"[{'中古' if chuko else '新築'}] 写真: {len(photos)}枚 / 売主コメント: {len(baishuu_photos)}枚 / レイアウト: {len(layout_rows)}行")
            kenchu = self._kenchu_bangou.get()
            price  = int(self._bukken_kakaku.get())
            photo_folder = self._photo_folder.get()

            self._log("Chromeに接続中...")
            from automation.suumo import SuumoAutomation
            bot = SuumoAutomation(log_callback=self._log)
            if not bot.connect():
                return

            bot.fill_all(config, kenchu, price, photo_folder, photos, baishuu_photos, layout_rows)
            bot.disconnect()
            self._log("✅ 全タブの入力完了（内容を確認して保存してください）")
        except Exception as e:
            self._log(f"エラー: {e}")
            import traceback; self._log(traceback.format_exc())
        finally:
            self._running = False

    # -------- ホームズ 物件選択コールバック --------

    def _select_bukken(self, options: list):
        """
        automation スレッドから呼ばれる。
        メインスレッドで選択ダイアログを表示し、選択インデックスを返す。
        キャンセル時は None。
        """
        import threading
        result = [None]
        event  = threading.Event()

        def show_dialog():
            dlg = SelectDialog(
                self, options,
                dialog_title="入力する物件を選択",
                dialog_label="入力する物件を選んでください",
                ok_label="この物件を入力する",
            )
            result[0] = dlg.result
            event.set()

        self.after(0, show_dialog)
        event.wait()          # automation スレッドはここで止まって待つ
        return result[0]

    # -------- ホームズ 一括入力 --------

    def _fill_all_homes(self):
        self._running = True
        try:
            if not self._check_inputs():
                return
            from excel_reader import read_photos
            chuko      = self._is_chuko()
            kenchu     = self._kenchu_bangou.get()
            excel_path = self._get_excel_path()
            if chuko:
                photos        = []  # 中古は基本画像なし
                gaigai_photos = read_photos(excel_path, sheet_name="ホームズ_外観（中古）")
                naikan_photos = read_photos(excel_path, sheet_name="ホームズ_内観（中古）")
                photo_folder  = self._photo_folder.get()
            else:
                photos        = read_photos(excel_path, sheet_name="ホームズ用")
                gaigai_photos = read_photos(excel_path, sheet_name="ホームズ_外観分譲地")
                naikan_photos = read_photos(excel_path, sheet_name="ホームズ_内観")
                photo_folder  = HOMES_DEFAULT_PHOTO_FOLDER
            self._log(f"[{'中古' if chuko else '新築'}] ホームズ 基本画像: {len(photos)}枚 / 外観: {len(gaigai_photos)}枚 / 内観: {len(naikan_photos)}枚")

            from automation.homes import HomesAutomation
            bot = HomesAutomation(log_callback=self._log,
                                  select_callback=self._select_bukken)

            self._log("Chromeに接続中...")
            if not bot.connect():
                self._log("  ✗ Chrome接続失敗")
                return

            bot.fill_all(kenchu, photos, photo_folder, gaigai_photos, naikan_photos)
            bot.disconnect()
            self._log("✅ ホームズ: 入力完了")
        except Exception as e:
            self._log(f"エラー: {e}")
            import traceback; self._log(traceback.format_exc())
        finally:
            self._running = False

    # -------- ピタクラ タブ選択コールバック --------

    def _select_pitakura_tab(self, urls: list):
        """
        複数のピタクラタブがある場合にautomationスレッドから呼ばれる。
        メインスレッドで選択ダイアログを表示し、選択インデックスを返す。
        """
        result = [None]
        event  = threading.Event()

        def show_dialog():
            dlg = SelectDialog(
                self, urls,
                dialog_title="ピタクラ タブ選択",
                dialog_label="入力するタブのURLを選んでください",
                ok_label="このタブを使う",
            )
            result[0] = dlg.result
            event.set()

        self.after(0, show_dialog)
        event.wait()
        return result[0]

    # -------- ピタクラ 一括入力 --------

    def _fill_all_pitakura(self):
        self._running = True
        try:
            if not self._check_inputs():
                return
            from excel_reader import read_photos
            kenchu       = self._kenchu_bangou.get()
            # 表示用の「なし（中古）」は空文字として渡す
            if kenchu in ("未入力", "なし（中古）"):
                kenchu = ""
            chuko        = self._is_chuko()
            excel_path   = self._get_excel_path()
            photos       = read_photos(excel_path, sheet_name="ピタクラ（中古）" if chuko else "ピタクラ")
            photo_folder = self._photo_folder.get() if chuko else DEFAULT_PHOTO_FOLDER
            self._log(f"[{'中古' if chuko else '新築'}] ピタクラ: {len(photos)}行")

            from automation.pitakura import PitakuraAutomation
            bot = PitakuraAutomation(log_callback=self._log,
                                     select_callback=self._select_pitakura_tab)

            self._log("Chromeに接続中...")
            if not bot.connect():
                self._log("  ✗ Chrome接続失敗")
                return

            bot.fill_all(kenchu, photos, photo_folder)
            bot.disconnect()
            self._log("✅ ピタクラ: 入力完了")
        except Exception as e:
            self._log(f"エラー: {e}")
            import traceback; self._log(traceback.format_exc())
        finally:
            self._running = False

    # -------- スカイヤーズ 一括入力 --------

    def _fill_all_skyyers(self):
        self._running = True
        try:
            if not self._check_inputs():
                return
            from excel_reader import read_site_config, read_photos
            chuko        = self._is_chuko()
            excel_path   = self._get_excel_path()
            config       = self._load_config()
            kenchu       = self._kenchu_bangou.get()
            if kenchu in ("未入力", "なし（中古）"):
                kenchu = ""
            photos       = read_photos(excel_path, sheet_name="スカイヤーズ（中古）" if chuko else "スカイヤーズ")
            photo_folder = self._photo_folder.get() if chuko else DEFAULT_PHOTO_FOLDER
            self._log(f"[{'中古' if chuko else '新築'}] スカイヤーズ: {len(photos)}行")

            from automation.skyyers import SkyeyersAutomation
            bot = SkyeyersAutomation(log_callback=self._log)

            self._log("Chromeに接続中...")
            if not bot.connect():
                self._log("  ✗ Chrome接続失敗")
                return

            bot.fill_all(
                tantosha_name=config.tantosha_name,
                kenchu_bangou=kenchu,
                photos=photos,
                photo_folder=photo_folder,
            )
            bot.disconnect()
            self._log("✅ スカイヤーズ: 入力完了")
        except Exception as e:
            self._log(f"エラー: {e}")
            import traceback; self._log(traceback.format_exc())
        finally:
            self._running = False

    # -------- テンプレート作成 / シート追加 --------

    def _create_template(self):
        save_path = self._get_excel_path()

        if os.path.exists(save_path):
            # ファイルあり → 中古シートだけ追加（既存データは保持）
            try:
                from add_chuko_sheets import add_chuko_sheets
                added = add_chuko_sheets(save_path)
                if added:
                    msg = f"以下のシートを追加しました:\n" + "\n".join(f"  ・{s}" for s in added)
                    self._log(msg)
                    messagebox.showinfo("完了", msg)
                else:
                    messagebox.showinfo("確認", "追加するシートはありませんでした\n（中古シートはすでにすべて存在します）")
            except Exception as e:
                messagebox.showerror("エラー", f"シート追加エラー: {e}")
        else:
            # ファイルなし → 新規作成（make_template.py）
            try:
                import subprocess
                script = os.path.join(base_dir, "make_template.py")
                result = subprocess.run([sys.executable, script, save_path],
                                        capture_output=True, text=True)
                if result.returncode == 0:
                    self._log(f"テンプレートを新規作成しました: {save_path}")
                    messagebox.showinfo("完了", f"テンプレートを新規作成しました:\n{save_path}")
                else:
                    self._log(f"テンプレート作成エラー: {result.stderr}")
            except Exception as e:
                messagebox.showerror("エラー", f"テンプレート作成エラー: {e}")

    # -------- ログ --------

    def _log(self, msg: str):
        def _append():
            self._log_text.config(state="normal")
            self._log_text.insert("end", msg + "\n")
            self._log_text.see("end")
            self._log_text.config(state="disabled")
        self.after(0, _append)


if __name__ == "__main__":
    try:
        app = App()
        app.mainloop()
    except Exception:
        import traceback
        with open(os.path.join(base_dir, "error.log"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
