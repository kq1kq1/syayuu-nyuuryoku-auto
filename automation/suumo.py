"""
SUUMO管理画面の自動化モジュール
"""
import os
import time
import unicodedata
from typing import Optional, Callable
from .base import AutomationBase


def _calc_monthly(price_man: int, kinri_pct: float, kikan_year: int) -> int:
    """月々返済額を計算（元利均等返済）"""
    principal = price_man * 10000
    r = kinri_pct / 100 / 12   # 月利
    n = kikan_year * 12         # 返済月数
    if r == 0:
        return round(principal / n)
    monthly = principal * r / (1 - (1 + r) ** (-n))
    return round(monthly)


class SuumoAutomation(AutomationBase):
    """SUUMO管理画面の自動化"""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        super().__init__(log_callback)

    # ==============================
    # 全タブ一括入力
    # ==============================
    def fill_all(self, config, kenchu_bangou: str, price_man: int,
                 photo_folder: str = "", photos: list = None,
                 baishuu_photos: list = None,
                 layout_rows: list = None,
                 video_path: str = "", logo_path: str = "",
                 sky_balcony: bool = False) -> bool:
        """基本情報 → 写真（内外観＋売主コメント） → 支払い例 を順番に入力する

        video_path / logo_path が指定されていれば、最後に動画・CMタブも処理する。
        sky_balcony=True のときだけ動画を入れる（ロゴは有無に関わらず入れる）。
        """
        self.log("=== SUUMO: 全タブ入力を開始します ===")

        # SUUMOの物件編集タブに切り替える
        if not self.switch_to_page_by_url("suumo"):
            self.log("  ✗ SUUMOのタブが見つかりません")
            self.log("  → manager.suumo.jp の物件編集ページを開いてください")
            return False
        self.log(f"  ✓ SUUMOタブに切り替えました: {self._page.url}")
        time.sleep(0.5)

        # ① 基本情報タブ
        self.log("--- ① 基本情報タブへ移動 ---")
        self._click_tab("基本情報")
        self.fill_basic_info(config, kenchu_bangou)
        self._save_tab()

        # ② 内外観・その他画像タブ（上段: 内外観 ＋ 下段: 売主コメント）
        self.log("--- ② 内外観・その他画像タブへ移動 ---")
        self._click_tab("内外観")
        if photos:
            self.fill_naigaikan(photos, photo_folder)
        else:
            self.log("  ※ 内外観写真データなし（スキップ）")
        if baishuu_photos:
            self.fill_baishuu_comment(baishuu_photos, photo_folder)
        else:
            self.log("  ※ 売主コメントデータなし（スキップ）")
        self._save_tab()

        # ③ 支払い例タブ
        self.log("--- ③ 支払い例タブへ移動 ---")
        self._click_tab("支払い例")
        self.fill_shiharai(config, price_man)
        self._save_tab()

        # ④ レイアウト指定タブ
        self.log("--- ④ レイアウト指定タブへ移動 ---")
        self._click_tab("レイアウト")
        self.fill_layout(layout_rows or [])

        # ⑤ 動画・CMタブ（ロゴ／スカイバルコニー動画）
        if video_path or logo_path:
            self.log("--- ⑤ 動画・CMタブへ移動 ---")
            self._click_tab("動画")
            self.fill_douga_cm(video_path, logo_path, sky_balcony)

        self.log("=== 全タブ入力完了 ===")
        return True

    # ==============================
    # ⑤ 動画・CMタブ
    # ==============================
    # 内外観・横画像で共通のカテゴリ選択ポップアップから項目を選ぶJS。
    # li の textContent は隠しspanを含んで「991その他その他」のようになるため、
    # span.jscSelectText / 非表示でないspan から表示名を取り出して比較する。
    SELECT_POPUP_JS = """
                (target) => {
                    function norm(s) {
                        return s.replace(/[\\uFF01-\\uFF5E]/g,
                            c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0)
                        ).replace(/\\u3000/g, ' ')
                         .replace(/^[★▲△■☆※◆◇●○]+/, '')
                         .trim();
                    }
                    const normTarget = norm(target);

                    // 表示中のポップアップを探す
                    const box = [
                        'div#jsiSelectPopBoxUC',
                        'div#jsiSelectPopBox',
                        'ul#jsiSelectContentsUc',
                        'ul#jsiSelectContents'
                    ].map(s => document.querySelector(s))
                     .find(el => el && getComputedStyle(el).display !== 'none');
                    if (!box) return 'nobox';

                    // li → span.jscSelectText → span:not(.dn) → li全体 の順でテキスト取得
                    const items = Array.from(box.querySelectorAll('li'));
                    const opts = [];
                    for (const li of items) {
                        const txtSpan = li.querySelector('span.jscSelectText')
                                     || Array.from(li.querySelectorAll('span'))
                                            .find(s => !s.classList.contains('dn') && s.textContent.trim());
                        const raw = (txtSpan ? txtSpan.textContent : li.textContent).trim();
                        opts.push(raw);
                        if (norm(raw) === normTarget) {
                            li.click();
                            return 'ok:' + raw;
                        }
                    }

                    // li が空なら a タグも試す
                    if (items.length === 0) {
                        for (const a of box.querySelectorAll('a')) {
                            const raw = a.textContent.trim();
                            opts.push(raw);
                            if (norm(raw) === normTarget) {
                                a.click();
                                return 'ok:' + raw;
                            }
                        }
                    }

                    if (opts.length === 0) return 'noitems';
                    return 'notfound:' + JSON.stringify(opts.slice(0, 20));
                }
            """

    # 動画登録の別ウィンドウ・横画像の保存ボタンは、画面によって実装が違う可能性がある。
    # 1つ目から順に試し、見つかったものを使う。
    DOUGA_SAVE_SELECTORS = (
        "a#linkSubBtn",
        "a[title='登録・保存']",
        "input[value='登録・保存']",
        "input[type='button'][value*='登録']",
        "a:has-text('登録・保存')",
    )

    def fill_douga_cm(self, video_path: str = "", logo_path: str = "",
                      sky_balcony: bool = False) -> bool:
        """動画・CMタブの一連の入力。

        ① 動画（スカイバルコニーありのときだけ）
           一覧の「動画」行の登録・修正 → 別ウィンドウ → ファイル選択 → 登録・保存 → 完了ダイアログOK
        ② 動画・コマーシャライザー横画像にロゴ → キャプション区分「その他」→ 説明文
        ③ 最後に登録・保存

        SUUMO側の変換処理でページ遷移が遅いので、各段階で明示的に待つ。
        """
        self.log("=== SUUMO: 動画・CM の入力を開始します ===")
        self.log(f"  スカイバルコニー: {'あり → 動画とロゴ' if sky_balcony else 'なし → ロゴのみ'}")

        ok = True
        douga_done = False   # 動画を実際に登録できたか（公開チェックの要否判定に使う）

        # ---- ① 動画 ----
        if sky_balcony:
            if not video_path:
                self.log("  ✗ 動画: ファイルパスが渡されていません")
                ok = False
            elif not os.path.exists(video_path):
                self.log(f"  ✗ 動画: ファイルが見つかりません → {video_path}")
                ok = False
            else:
                douga_done = self._upload_douga(video_path)
                ok = douga_done and ok
        else:
            self.log("  - 動画: スカイバルコニーなしのため入れません")

        # ---- ② 横画像（ロゴ）----
        if logo_path and os.path.exists(logo_path):
            ok = self._upload_yoko_gazo(logo_path, ensure_douga_public=douga_done) and ok
        elif logo_path:
            self.log(f"  ✗ ロゴ: ファイルが見つかりません → {logo_path}")
            ok = False
        else:
            self.log("  - ロゴ: 入れません")

        self.log("=== 動画・CM の入力完了（内容を確認して保存してください）===")
        return ok

    # ------------------------------------------------------------------
    # ①動画: 一覧の「動画」行 → 別ウィンドウ → アップロード → 登録・保存
    # ------------------------------------------------------------------
    def _upload_douga(self, video_path: str) -> bool:
        size_mb = os.path.getsize(video_path) / 1024 / 1024
        self.log(f"--- 動画を登録します（{os.path.basename(video_path)} / {size_mb:.2f} MB）---")

        # 一覧には「動画」行と「CM」行があり、どちらにも登録・修正ボタンがある。
        # 動画側は id="dogaBtnUpd" なので ID で確実に選ぶ。
        btn = "input#dogaBtnUpd"
        try:
            self._page.wait_for_selector(btn, timeout=10000, state="visible")
        except Exception:
            self.log("  ✗ 動画行の「登録・修正」ボタンが見つかりません（input#dogaBtnUpd）")
            self._dump_screen("動画・CMタブ")
            return False

        # ボタンを押すと別ウィンドウが開く
        win = None
        try:
            with self._page.expect_popup(timeout=20000) as popup:
                self._page.click(btn, timeout=8000)
            win = popup.value
            self.log("  ✓ 動画登録ウィンドウが開きました")
        except Exception as e:
            self.log(f"  ✗ 動画登録ウィンドウが開きませんでした: {e}")
            self.log("  → ポップアップがブロックされていないか確認してください")
            return False

        try:
            # 「登録完了しました。このまま画面を閉じます。」を自動でOKする。
            # クリックより先に登録しておかないと取りこぼす。
            win.on("dialog", self._accept_dialog)

            try:
                win.wait_for_load_state("load", timeout=20000)
            except Exception:
                pass
            time.sleep(1.0)

            # 動画ファイルを選択
            try:
                win.wait_for_selector("input#btnDogaFile", timeout=15000, state="attached")
                win.set_input_files("input#btnDogaFile", video_path, timeout=60000)
                self.log("  ✓ 動画ファイルを選択しました")
            except Exception as e:
                self.log(f"  ✗ 動画ファイルの選択に失敗: {e}")
                self._dump_screen("動画登録ウィンドウ", page=win)
                return False

            time.sleep(1.0)

            # 登録・保存
            clicked = self._click_first(win, self.DOUGA_SAVE_SELECTORS, "登録・保存")
            if not clicked:
                self.log("  ✗ 動画登録ウィンドウの「登録・保存」ボタンが見つかりません")
                self._dump_screen("動画登録ウィンドウ", page=win)
                return False

            # アップロードと変換処理があるので長めに待つ。
            # 完了ダイアログをOKすると、このウィンドウは自分で閉じる。
            self.log("  … アップロード中（サイズによっては時間がかかります）")
            try:
                win.wait_for_event("close", timeout=180000)
                self.log("  ✓ 動画の登録が完了しました（ウィンドウが閉じました）")
            except Exception:
                self.log("  ⚠ ウィンドウが閉じませんでした。画面を確認してください")
                self._dump_screen("動画登録ウィンドウ", page=win)
                return False
        finally:
            try:
                if win and not win.is_closed():
                    win.close()
            except Exception:
                pass

        # 先に一覧を読み直して「納品済」等の登録後の状態にする。
        # チェックを入れてからリロードすると、その操作が消えてしまうので順番が重要。
        try:
            self._page.reload(timeout=30000)
            self._page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(1.5)

        # 一覧の「公開する」にチェックを入れる。
        # 動画行のチェックボックスは id="jsiDogaRadio"（CM行とは別物）。
        # 反映はこのあと横画像側で押す「登録・保存」でまとめて行われる。
        self._check_if_unchecked("input#jsiDogaRadio", "公開する（動画）")
        return True

    # ------------------------------------------------------------------
    # ②横画像: ロゴ + キャプション区分 + 説明文
    # ------------------------------------------------------------------
    YOKO_CATEGORY = "その他"
    YOKO_CAPTION = "天空の家シリーズ"

    def _upload_yoko_gazo(self, logo_path: str, ensure_douga_public: bool = False) -> bool:
        """動画・コマーシャライザー横画像にロゴ・カテゴリ・説明文を入れて保存する。

        「登録・保存」ボタンは画像とカテゴリが揃うまで disabled のままなので、
        各入力が実際に反映されたことを確認しながら進める。
        """
        self.log(f"--- 横画像にロゴを入れます（{os.path.basename(logo_path)}）---")

        # ---- ① ロゴをアップロード ----
        if not self._set_yoko_file(logo_path):
            self._dump_yoko_state("ロゴのアップロードに失敗")
            return False

        # ---- ② キャプション区分 ----
        if not self._select_yoko_category(self.YOKO_CATEGORY):
            self._dump_yoko_state("キャプション区分を選べませんでした")
            return False

        # ---- ③ 説明文 ----
        if not self._fill_yoko_caption(self.YOKO_CAPTION):
            self._dump_yoko_state("説明文を入力できませんでした")
            return False

        # ---- ④ 公開チェックの再確認 ----
        # 横画像のアップロードで画面が描き直された場合、先に入れたチェックが
        # 外れている可能性があるため（入っていれば何もしない）。
        if ensure_douga_public:
            self._check_if_unchecked("input#jsiDogaRadio", "公開する（動画・保存前の再確認）")

        # ---- ⑤ 登録・保存 ----
        return self._save_yoko()

    def _set_yoko_file(self, logo_path: str, retries: int = 2) -> bool:
        """ロゴを input#a07 にセットし、実際にアップロードされたか確認する。

        SUUMO側は hidden iframe 経由でアップロードするため、
        set_input_files 直後はまだ反映されていない。サムネイルが出るまで待つ。
        """
        ext = os.path.splitext(logo_path)[1].lower()
        for attempt in range(1, retries + 1):
            try:
                self._page.wait_for_selector("input#a07", timeout=15000, state="attached")
                self._page.set_input_files("input#a07", logo_path, timeout=30000)
            except Exception as e:
                self.log(f"  ✗ ロゴの選択に失敗（{attempt}回目）: {e}")
                continue

            self.log(f"  … ロゴをアップロード中（{attempt}回目）")
            # 成否の判定はサムネイルの表示だけを見る。
            # input の files は、アップロードが「成功」してもSUUMO側のJSが
            # 送信後にクリアするため0件になる。これを失敗と誤判定していた。
            for _ in range(40):          # 最大20秒
                time.sleep(0.5)
                if self._yoko_state().get("has_image"):
                    self.log("  ✓ ロゴのアップロード完了（サムネイル表示を確認）")
                    return True

            # サムネイルが出ないまま input も空 ＝ 形式などで弾かれた可能性が高い
            if not self._yoko_state().get("file_selected"):
                self.log(f"  ✗ ファイルがSUUMO側に受け付けられませんでした（{os.path.basename(logo_path)}）")
                if ext not in (".jpg", ".jpeg"):
                    self.log(f"  → {ext} は動画・CMタブの横画像では使えません。JPGにしてください")
                    return False
                self.log("  → 形式・サイズを確認してください")
            else:
                self.log("  ⚠ サムネイルが出ませんでした。やり直します")

        self.log("  ✗ ロゴのアップロードが反映されませんでした")
        return False

    def _select_yoko_category(self, category: str) -> bool:
        """横画像のキャプション区分をポップアップから選ぶ。

        内外観と同じポップアップなので、実績のある SELECT_POPUP_JS を使う。
        li の textContent は隠しspanを含むため、単純な文字列一致では選べない。
        """
        cur = self._yoko_state().get("category", "")
        if cur == category:
            self.log(f"  ✓ キャプション区分: 既に「{cur}」")
            return True

        for attempt in range(1, 3):
            try:
                # ポップアップを開く
                self._page.evaluate("""
                    () => {
                        const inp = document.querySelector('input#jscSelectPop');
                        if (!inp) return;
                        inp.scrollIntoView({behavior: 'instant', block: 'center'});
                        inp.dispatchEvent(new MouseEvent('click',
                            {bubbles: true, cancelable: true, view: window}));
                    }
                """)
                time.sleep(0.5)
                result = self._page.evaluate(self.SELECT_POPUP_JS, category)
            except Exception as e:
                self.log(f"  ✗ キャプション区分の選択でエラー: {e}")
                return False

            if result and result.startswith("ok:"):
                time.sleep(0.5)
                cur = self._yoko_state().get("category", "")
                if cur == category:
                    self.log(f"  ✓ キャプション区分: {category}")
                    return True
                self.log(f"  ⚠ 選択したが反映されていません（現在: {cur or '空'}）")
            elif result == "nobox":
                self.log(f"  ⚠ キャプション区分のポップアップが開きませんでした（{attempt}回目）")
            elif result == "noitems":
                self.log("  ✗ ポップアップに選択肢がありません")
                return False
            elif result and result.startswith("notfound:"):
                self.log(f"  ✗ 「{category}」が選択肢にありません → {result[9:]}")
                return False
            time.sleep(0.5)

        return False

    def _fill_yoko_caption(self, text: str) -> bool:
        """説明文を入れる。

        この欄は空のとき「画像キャプションを入力してください。（100文字）」という
        プレースホルダーが value として入り class="jscTxtGray" になる作り。
        JSで value を差し替えるだけだと灰色表示のままでサイト側に空と見なされうるので、
        レイアウト指定のタイトル欄と同じく Playwright のネイティブ入力を先に試す。
        """
        sel = "textarea[name='yokoCaption']"
        try:
            self._page.wait_for_selector(sel, timeout=10000, state="attached")
        except Exception:
            self.log(f"  ✗ 説明文の入力欄が見つかりません（{sel}）")
            return False

        try:
            ta = self._page.locator(sel).first
            ta.click(timeout=5000)
            ta.fill("", timeout=5000)      # プレースホルダーを消す
            ta.fill(text, timeout=5000)
        except Exception as e:
            self.log(f"  [warn] ネイティブ入力に失敗、JSで再試行: {e}")
            self._fill_textarea(sel, text)

        time.sleep(0.3)
        cur = self._yoko_state().get("caption", "")
        if cur == text:
            self.log(f"  ✓ 説明文: {text}")
            return True

        # ネイティブが効かなかった場合の保険
        self._fill_textarea(sel, text)
        time.sleep(0.3)
        cur = self._yoko_state().get("caption", "")
        if cur == text:
            self.log(f"  ✓ 説明文: {text}（JSで入力）")
            return True

        self.log(f"  ✗ 説明文が反映されませんでした（現在: {cur[:30] or '空'}）")
        return False

    def _save_yoko(self) -> bool:
        """「登録・保存」を押す。disabled が外れるまで待ってから押す。"""
        # 画像とカテゴリが揃うまでボタンは disabled のまま（クリックしても無反応）
        for _ in range(20):              # 最大10秒
            if self._yoko_state().get("save_enabled"):
                break
            time.sleep(0.5)
        else:
            st = self._yoko_state()
            self.log("  ✗ 「登録・保存」ボタンが押せる状態になりません（disabled のまま）")
            self.log(f"      画像: {'あり' if st.get('has_image') else 'なし'} / "
                     f"カテゴリ: {st.get('category') or '未選択'} / "
                     f"説明文: {(st.get('caption') or '空')[:20]}")
            self._dump_yoko_state("保存できない状態")
            return False

        self._page.on("dialog", self._accept_dialog)
        if not self._click_first(self._page, self.DOUGA_SAVE_SELECTORS, "登録・保存"):
            self.log("  ✗ 「登録・保存」ボタンが見つかりません")
            self._dump_screen("動画・CMタブ")
            return False

        self.log("  … 保存中")
        try:
            self._page.wait_for_load_state("networkidle", timeout=60000)
        except Exception:
            pass
        time.sleep(2.0)
        self.log("  ✓ 横画像を保存しました")
        return True

    def _yoko_state(self) -> dict:
        """横画像まわりの入力状態を1回のJSでまとめて取る"""
        try:
            return self._page.evaluate("""
                () => {
                    const cat  = document.querySelector('input#jscSelectPop');
                    const cap  = document.querySelector("textarea[name='yokoCaption']");
                    const save = document.querySelector('a#linkSubBtn');
                    const file = document.querySelector('input#a07');
                    // 「画像が登録されていません」の枠が表示されていれば未登録
                    const noimg = document.querySelector('.jscNoImageBox');
                    const noimgShown = !!(noimg && getComputedStyle(noimg).display !== 'none');
                    // 空欄のときはプレースホルダー文言が value に入る作りなので、
                    // 「〜してください」を含む値は未選択・未入力として扱う
                    const ph = (v) => (v && /してください/.test(v)) ? '' : (v || '').trim();
                    return {
                        category: cat ? ph(cat.value) : '',
                        caption:  cap ? ph(cap.value) : '',
                        has_image: !noimgShown,
                        file_selected: !!(file && file.files && file.files.length > 0),
                        save_enabled: !!(save && !save.hasAttribute('disabled')
                                         && !save.classList.contains('btnImgGray')),
                    };
                }
            """) or {}
        except Exception:
            return {}

    def _dump_yoko_state(self, why: str):
        st = self._yoko_state()
        self.log(f"  [調査] {why}")
        self.log(f"      画像あり      : {st.get('has_image')}")
        self.log(f"      ファイル選択済: {st.get('file_selected')}")
        self.log(f"      カテゴリ      : {st.get('category') or '(空)'}")
        self.log(f"      説明文        : {(st.get('caption') or '(空)')[:30]}")
        self.log(f"      保存ボタン    : {'押せる' if st.get('save_enabled') else 'disabled'}")
        self._dump_screen("動画・CMタブ")

    # ------------------------------------------------------------------
    # 共通ヘルパー
    # ------------------------------------------------------------------
    def _accept_dialog(self, dialog):
        """「登録完了しました」等の確認ダイアログを自動でOKする"""
        self.log(f"  [ダイアログ] 自動OK: {dialog.message[:60]}")
        try:
            dialog.accept()
        except Exception:
            pass

    def _click_first(self, page, selectors, label: str, wait_enabled: float = 10.0) -> bool:
        """候補セレクタを順に試し、最初に押せたものでクリックする。

        SUUMOの保存ボタンは <a disabled="disabled" class="btnImgGray"> の形で
        無効化される。見た目は表示されているのでクリック自体は通ってしまい、
        押せたつもりで先に進む事故になる。無効の間は待ち、それでも
        有効にならなければ失敗として返す。
        """
        deadline = time.time() + wait_enabled
        while True:
            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    if loc.count() == 0 or not loc.is_visible(timeout=2000):
                        continue
                    disabled = page.evaluate("""
                        (s) => {
                            const el = document.querySelector(s);
                            if (!el) return true;
                            return el.hasAttribute('disabled')
                                || el.classList.contains('btnImgGray')
                                || el.getAttribute('aria-disabled') === 'true';
                        }
                    """, sel)
                    if disabled:
                        continue
                    loc.click(timeout=8000)
                    self.log(f"  ✓ 「{label}」をクリック（{sel}）")
                    return True
                except Exception:
                    continue
            if time.time() >= deadline:
                return False
            self.log(f"  … 「{label}」が押せる状態になるのを待っています")
            time.sleep(1.0)

    def _dump_screen(self, where: str, page=None):
        """セレクタが見つからないときに、画面の入力欄・ボタンをログに出す（原因調査用）"""
        page = page or self._page
        try:
            info = page.evaluate("""
                () => ({
                    url: location.href,
                    files: Array.from(document.querySelectorAll('input[type=file]'))
                        .map(e => ({name: e.name || '', id: e.id || ''})),
                    btns: Array.from(document.querySelectorAll('input[type=button],input[type=submit],button,a[title]'))
                        .map(e => ({tag: e.tagName.toLowerCase(), id: e.id || '',
                                    label: (e.value || e.title || e.textContent || '').trim().slice(0, 24)}))
                        .filter(b => b.label).slice(0, 20)
                })
            """)
        except Exception as e:
            self.log(f"  [調査] 画面情報を取得できません: {e}")
            return
        self.log(f"  [調査] {where}: {info.get('url', '')}")
        for f in info.get("files", []):
            self.log(f"      file: name={f['name']} id={f['id']}")
        for b in info.get("btns", []):
            self.log(f"      <{b['tag']}> id={b['id']} 「{b['label']}」")
    # ==============================
    # ② 内外観タブ
    # ==============================
    # カテゴリ名にこの語を「含む」スロットは飛ばす。
    # 完全一致だと「間取り図(1)」「1階間取り図」のような表記ゆれを拾えないため。
    SKIP_CATEGORIES = ("間取り図", "区画図")

    def fill_naigaikan(self, photos: list, photo_folder: str) -> bool:
        """内外観タブの画像・カテゴリ・説明文をExcel順に入力する。
        - photo.caption → カテゴリ（jsiSelectPopBox インラインドロップダウン）
        - photo.text    → 説明文（textarea）
        - photo.filename が空 or ファイル未存在でも caption/text は入力する
        - 間取り図・区画図スロットはスキップ（Excelの順番を消費しない）
        """
        self.log("=== SUUMO: 内外観の入力を開始します ===")

        slots = self._page.query_selector_all("li.jscImageBody")
        self.log(f"  スロット数: {len(slots)}  写真データ: {len(photos)}枚")

        photo_idx = 0
        for i, slot_el in enumerate(slots):
            if photo_idx >= len(photos):
                self.log(f"  写真データ終了（スロット{i + 1}以降は入力なし）")
                break

            # カテゴリ確認（間取り図・区画図スロットはスキップ）
            cat_input = slot_el.query_selector("input.jscSelectPop")
            cat_value = (cat_input.get_attribute("value") or "").strip() if cat_input else ""

            if any(kw in cat_value for kw in self.SKIP_CATEGORIES):
                self.log(f"  スキップ: スロット{i + 1}（{cat_value}）")
                continue  # photo_idx は消費しない

            photo = photos[photo_idx]
            photo_idx += 1

            # ① 画像アップロード（ファイル名がある場合のみ）
            if photo.filename:
                filepath = os.path.join(photo_folder, photo.filename)
                if os.path.exists(filepath):
                    file_input = slot_el.query_selector("input[type='file']")
                    if file_input:
                        try:
                            file_input.set_input_files(filepath)
                            time.sleep(0.5)
                        except Exception as e:
                            self.log(f"  ✗ アップロードエラー（スロット{i + 1}）: {e}")
                    else:
                        self.log(f"  ✗ スロット{i + 1}: input[type=file]が見つかりません")
                else:
                    self.log(f"  ✗ ファイルなし: {filepath}（カテゴリ・説明文は入力します）")

            # ② カテゴリ選択（photo.caption → jsiSelectPopBox インラインドロップダウン）
            #    slot_el は操作後に stale になる可能性があるため slot index で渡す
            if photo.caption:
                self._select_category_inline(i, photo.caption, i + 1)

            # ③ 説明文（photo.text → textarea を JS で書き込み・スクロールなし）
            #    slot index で毎回 DOM を再取得するので stale ElementHandle の問題なし
            if photo.text:
                done = self._page.evaluate("""
                    ([slotIdx, val]) => {
                        const slot = document.querySelectorAll('li.jscImageBody')[slotIdx];
                        if (!slot) return false;
                        const ta = slot.querySelector('textarea');
                        if (!ta) return false;
                        ta.value = val;
                        ta.dispatchEvent(new Event('focus',  {bubbles: true}));
                        ta.dispatchEvent(new Event('input',  {bubbles: true}));
                        ta.dispatchEvent(new Event('change', {bubbles: true}));
                        ta.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));
                        return true;
                    }
                """, [i, photo.text])
                if not done:
                    self.log(f"  ✗ 説明文: textarea が見つかりません（スロット{i + 1}）")

        self.log(f"=== 内外観入力完了: {photo_idx}枚 ===")
        return True

    def _select_category_inline(self, slot_idx: int, category: str, slot_num: int,
                                slot_sel: str = "li.jscImageBody") -> bool:
        """①JS dispatchEvent でドロップダウンを開き ②Playwright click で項目を選択する。
        - 開く: JS（Playwright clickはスクロールが絡むと不安定なため）
        - 選ぶ: Playwright（ドロップダウン表示後は画面内に出るので安定）
        """
        import re as _re

        def norm_text(s: str) -> str:
            s = unicodedata.normalize("NFKC", s)
            s = _re.sub(r'^[★▲△■☆※◆◇●○]+', '', s)
            return s.strip()

        target = norm_text(category)

        try:
            # ① scrollIntoView で input を画面中央に入れてから JS dispatchEvent でポップアップを開く
            self._page.evaluate("""
                ([slotSel, slotIdx]) => {
                    const slot = document.querySelectorAll(slotSel)[slotIdx];
                    if (!slot) return;
                    const inp = slot.querySelector('input.jscSelectPop');
                    if (!inp) return;
                    inp.scrollIntoView({behavior: 'instant', block: 'center'});
                    inp.dispatchEvent(
                        new MouseEvent('click', {bubbles: true, cancelable: true, view: window})
                    );
                }
            """, [slot_sel, slot_idx])

            # ② ポップアップの描画を待つ
            time.sleep(0.3)

            # ③ JS でポップアップ内の一致する項目を探してクリック
            #    Playwright の visibility チェックを使わず JS で完結させることで確実に動作
            result = self._page.evaluate(self.SELECT_POPUP_JS, target)

            if result and result.startswith('ok:'):
                time.sleep(0.2)
                return True
            elif result == 'nobox':
                self.log(f"  ✗ カテゴリドロップダウンが開きませんでした（スロット{slot_num}）")
                return False
            elif result == 'noitems':
                self.log(f"  ✗ カテゴリドロップダウンが空でした（スロット{slot_num}）")
                return False
            else:
                opts_str = result[9:] if result.startswith('notfound:') else result
                self.log(f"  ✗ カテゴリ未発見（スロット{slot_num}）: '{category}' / 選択肢: {opts_str}")
                return False

        except Exception as e:
            self.log(f"  ✗ カテゴリ選択エラー（スロット{slot_num}）: {e}")
            return False

    def fill_baishuu_comment(self, photos: list, photo_folder: str) -> bool:
        """売主コメントセクション（dd.jscSwitchImage）の画像・カテゴリ・説明文を入力する。
        - スロット20番目（0-indexed: 19）以降から順に入力
        - 既に画像があるスロット（jscNoImageBox が非表示）はスキップ
        - photo.caption → カテゴリ（jsiSelectPopBoxUC ドロップダウン）
        - photo.text    → 説明文（textarea）
        """
        self.log("=== SUUMO: 売主コメントの入力を開始します ===")

        # スロット21番目（0-indexed=20）から開始
        START_FROM = 20

        SLOT_SEL = "dd.jscSwitchImage"
        slots = self._page.query_selector_all(SLOT_SEL)
        self.log(f"  スロット数: {len(slots)}  写真データ: {len(photos)}枚  開始: スロット{START_FROM + 1}〜")

        photo_idx = 0
        for i, slot_el in enumerate(slots):
            if photo_idx >= len(photos):
                self.log(f"  写真データ終了（スロット{i + 1}以降は入力なし）")
                break

            # スロット20番目より前はスキップ
            if i < START_FROM:
                continue

            # 既に画像があるスロットはスキップ
            # jscNoImageBox が visible = 空スロット / 非表示 or 存在しない = 画像あり
            no_img_box = slot_el.query_selector("div.jscNoImageBox")
            has_image = (no_img_box is None) or (not no_img_box.is_visible())
            if has_image:
                continue

            photo = photos[photo_idx]
            photo_idx += 1

            # ① 画像アップロード（ファイル名がある場合のみ）
            if photo.filename:
                filepath = os.path.join(photo_folder, photo.filename)
                if os.path.exists(filepath):
                    file_input = slot_el.query_selector("input[type='file']")
                    if file_input:
                        try:
                            file_input.set_input_files(filepath)
                        except Exception as e:
                            self.log(f"  ✗ アップロードエラー（スロット{i + 1}）: {e}")
                    else:
                        self.log(f"  ✗ スロット{i + 1}: input[type=file]が見つかりません")
                else:
                    self.log(f"  ✗ ファイルなし: {filepath}（カテゴリ・説明文は入力します）")

            # ② カテゴリ選択（JS dispatchEvent でドロップダウンを開くので jscTxtGray は気にしない）
            if photo.caption:
                self._select_category_inline(i, photo.caption, i + 1, slot_sel=SLOT_SEL)

            # ③ 説明文（slot index で DOM 再取得・スクロールなし）
            if photo.text:
                done = self._page.evaluate("""
                    ([slotSel, slotIdx, val]) => {
                        const slot = document.querySelectorAll(slotSel)[slotIdx];
                        if (!slot) return false;
                        const ta = slot.querySelector('textarea');
                        if (!ta) return false;
                        ta.value = val;
                        ta.dispatchEvent(new Event('focus',  {bubbles: true}));
                        ta.dispatchEvent(new Event('input',  {bubbles: true}));
                        ta.dispatchEvent(new Event('change', {bubbles: true}));
                        ta.dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));
                        return true;
                    }
                """, [SLOT_SEL, i, photo.text])
                if not done:
                    self.log(f"  ✗ 説明文: textarea が見つかりません（スロット{i + 1}）")

        self.log(f"=== 売主コメント入力完了: {photo_idx}枚 ===")
        return True

    def fill_layout(self, layout_rows: list) -> bool:
        """レイアウト指定タブ：ネットレポート選択 → 企画選択 → パターン・タイトル入力 → 確定"""
        self.log("=== SUUMO: レイアウト指定の入力を開始します ===")

        PATTERN_VALUES = {
            "A": "01", "B": "02", "C": "03",
            "D": "04", "E": "05", "F": "06",
        }

        # ① ネットレポートを選択
        # value は物件種別によって変わる（一戸建て: N010002 / 土地: N010003）ため、
        # 値の直書きでは土地物件で querySelector が null になり選択できなかった。
        # label の文字は種別によらず「ネットレポート」なので、そちらで探す。
        result = self._page.evaluate("""
            () => {
                const radios = Array.from(
                    document.querySelectorAll('input[name="kkkKoseiCd"]')
                );
                const labelOf = (r) => {
                    const l = r.id ? document.querySelector('label[for="' + r.id + '"]') : null;
                    return (l ? l.textContent : '').trim();
                };
                const options = radios.map(r => ({
                    value: r.value, id: r.id, label: labelOf(r)
                }));
                const target = radios.find(r => labelOf(r).includes('ネットレポート'));
                if (!target) return {ok: false, options: options};
                target.checked = true;
                target.dispatchEvent(new Event('change', {bubbles: true}));
                target.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                return {ok: true, value: target.value, label: labelOf(target)};
            }
        """)

        if not result.get("ok"):
            # 選べないまま「企画選択」に進むと画面が固まるので、ここで必ず止める。
            self.log("  ✗ ネットレポートのラジオボタンが見つかりません")
            options = result.get("options") or []
            if options:
                self.log("  → 画面上の企画の選択肢:")
                for o in options:
                    self.log(f"      value={o.get('value')} id={o.get('id')} label={o.get('label')}")
            else:
                self.log("  → 企画のラジオボタンが1つもありません。レイアウト指定タブが開いているか確認してください")
            self.log("  → レイアウト指定の入力を中止しました")
            return False

        self.log(f"  ✓ ネットレポートを選択（value={result.get('value')}）")
        time.sleep(0.3)

        # ② 企画選択ボタンをクリック → グリッド表示を待つ
        btn = self._page.locator("input#jsiPlanSelectChange")
        btn.click(timeout=5000)
        self.log("  ✓ 企画選択ボタンをクリック")
        try:
            self._page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        time.sleep(2.0)

        # ③ 各段のパターンとタイトルを入力
        for idx, row in enumerate(layout_rows, 1):
            pattern = row.pattern if hasattr(row, 'pattern') else row[0]
            title   = row.title   if hasattr(row, 'title')   else row[1]
            pat_val = PATTERN_VALUES.get(str(pattern).strip().upper(), "01")

            # パターンラジオボタン（JS dispatchEvent）
            done = self._page.evaluate("""
                ([rowNum, patVal]) => {
                    const sel = `input[name="rptPtn${rowNum}"][value="${patVal}"]`;
                    const radio = document.querySelector(sel);
                    if (!radio) return false;
                    radio.checked = true;
                    radio.dispatchEvent(new Event('change', {bubbles: true}));
                    radio.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                    return true;
                }
            """, [idx, pat_val])
            self.log(f"  {'✓' if done else '✗'} {idx}段目 パターン{pattern}")

            # タイトル入力（Playwrightネイティブ: jscTxtGray/jscTxtFocusのプレースホルダーを正しく扱うため）
            if title:
                try:
                    inp = self._page.locator(f"input[name='rptTitle{idx}']")
                    inp.click(timeout=3000)
                    inp.fill(title, timeout=3000)
                    self.log(f"  ✓ {idx}段目 タイトル: {title[:30]}")
                except Exception as e:
                    self.log(f"  ✗ {idx}段目 タイトル入力エラー: {e}")

        # ④ レイアウト受変確定ボタンをクリック
        confirmed = self._page.evaluate("""
            () => {
                const candidates = [
                    ...document.querySelectorAll('input[type="button"]'),
                    ...document.querySelectorAll('button'),
                    ...document.querySelectorAll('a'),
                ];
                const btn = candidates.find(el =>
                    (el.value || el.textContent || '').includes('確定')
                );
                if (btn) { btn.click(); return btn.value || btn.textContent.trim(); }
                return null;
            }
        """)
        if confirmed:
            self.log(f"  ✓ 確定ボタンをクリック: {confirmed}")
            try:
                self._page.wait_for_load_state("load", timeout=10000)
            except Exception:
                pass
            time.sleep(1.0)
        else:
            self.log("  ✗ 確定ボタンが見つかりませんでした")

        self.log("=== レイアウト指定入力完了 ===")
        return True

    def test_naigaikan_only(self, photos: list, photo_folder: str) -> bool:
        """内外観タブのみテスト実行（登録保存しない）"""
        self.log("=== [テスト] 内外観タブのみ実行 ===")
        if not self.switch_to_page_by_url("suumo"):
            self.log("  ✗ SUUMOのタブが見つかりません")
            return False
        self._click_tab("内外観")
        self.fill_naigaikan(photos, photo_folder)
        self.log("=== [テスト] 完了（登録保存はしていません）===")
        return True

    # ==============================
    # ① 基本情報タブ
    # ==============================
    def fill_basic_info(self, config, kenchu_bangou: str) -> bool:
        """基本情報タブを入力する"""
        self.log("=== SUUMO: 基本情報の入力を開始します ===")


        # 担当者選択
        self._select_tantosha(config.tantosha_name)

        # リンク表示名称 / URL 1〜5（DevTools確認済み: name="hpLinkNm1", id="linkNm1"）
        for i, (name, url) in enumerate(zip(config.link_names, config.link_urls), 1):
            if name:
                if not self._fill(f"input[name='hpLinkNm{i}']", name):
                    self.log(f"  ✗ リンク表示名称{i}: 入力欄が見つかりません")
            if url:
                if not self._fill(f"input[name='hpLinkUrl{i}']", url):
                    self.log(f"  ✗ リンク先URL{i}: 入力欄が見つかりません")

        # 建築確認番号（DevTools確認済み: name="kenchikuKakuninNo", id="jscKenchikuKakuninNo"）
        # 土地や中古では番号自体が無く、土地の画面には入力欄も存在しない。
        # 空のまま探すと「入力欄が見つかりません」と誤ったエラーを出すのでスキップする。
        if not kenchu_bangou:
            self.log("  - 建築確認番号: スキップ（未入力）")
        elif self._fill("input[name='kenchikuKakuninNo']", kenchu_bangou):
            self.log(f"  ✓ 建築確認番号: {kenchu_bangou}")
        else:
            self.log("  ✗ 建築確認番号: 入力欄が見つかりません")

        self.log("=== 基本情報の入力完了 ===")
        return True

    def _select_tantosha(self, name: str) -> bool:
        """担当者をポップアップウィンドウから選択する"""
        self.log(f"  担当者選択: {name}")
        try:
            context = self._page.context

            # 「選択する」ラジオボタンを先に押さないとボタンが disabled のまま
            try:
                self._page.wait_for_selector("input#jsiSenTaku1", timeout=5000, state="attached")
                self._page.evaluate("""
                    () => {
                        const el = document.querySelector('input#jsiSenTaku1');
                        if (el) {
                            el.checked = true;
                            el.dispatchEvent(new Event('change', {bubbles: true}));
                            el.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                        }
                    }
                """)
                self.log("  ✓ 「選択する」ラジオボタンを押しました")
                time.sleep(0.5)
            except Exception as e:
                self.log(f"  [warn] ラジオボタン操作: {e}")

            # ポップアップが開くのを待ちながらボタンをクリック
            # no_wait_after=True: ポップアップを開いた後、メインページの完了を待たない
            with context.expect_page(timeout=10000) as new_page_info:
                self._page.click("input#jsiPopupPerson",
                                 no_wait_after=True, timeout=5000)

            popup = new_page_info.value
            popup.wait_for_load_state("domcontentloaded")
            time.sleep(1.0)  # ポップアップの読み込みを待つ

            # 名前照合。SUUMO側は姓名の間が全角/半角どちらもありえるうえ、
            # スペースが2つ以上入っていることもあるので、正規化して1つに詰める。
            from excel_reader import normalize_name as norm
            target = norm(name)

            links = popup.query_selector_all("a.jscPopFloorKnj")
            for link in links:
                title     = norm(link.get_attribute("title") or "")
                name_attr = norm(link.get_attribute("name") or "")
                if target in title or target in name_attr:
                    try:
                        # no_wait_after=True: 選択後ポップアップが閉じても待たない
                        link.click(no_wait_after=True, timeout=5000)
                    except Exception as e:
                        # ポップアップが閉じることによる例外は無視
                        if "closed" in str(e).lower() or "Target page" in str(e):
                            pass
                        else:
                            raise
                    self.log(f"  ✓ 担当者選択完了: {name}")

                    # メインページを前面に戻して反映を待つ
                    self._page.bring_to_front()
                    time.sleep(1.0)
                    return True

            self.log(f"  ✗ 担当者が見つかりません: {name}（ポップアップを確認してください）")
            try:
                popup.close()
            except Exception:
                pass
            return False

        except Exception as e:
            self.log(f"  ✗ 担当者選択エラー: {e}")
            return False

    # ==============================
    # ③ 支払い例タブ
    # ==============================
    def fill_shiharai(self, config, price_man: int) -> bool:
        """支払い例タブを入力する"""
        self.log("=== SUUMO: 支払い例の入力を開始します ===")

        monthly = _calc_monthly(price_man, config.kinri, config.kikan)

        kingaku_text = f"価格{price_man}万円、頭金0万円、借入額{price_man}万円"
        kinri_text   = f"年利{config.kinri:.3f}% 変動金利 返済期間{config.kikan}年"
        monthly_str  = f"{monthly:,}".replace(",", "，")   # 全角カンマ（半角不可）
        gakubu_text  = f"毎月{monthly_str}円 ボーナス時加算 0円 →団体信用生命保険付き"

        self.log(f"  物件価格: {price_man:,}万円")
        self.log(f"  月々返済額: {monthly:,}円（年利{config.kinri}%・{config.kikan}年）")

        # 支払い例ページの読み込み完了を確認（最大10秒待機）
        try:
            self._page.wait_for_selector("input#d02", timeout=10000, state="attached")
        except Exception:
            self.log(f"  [診断] 支払い例URL: {self._page.url}")
            cb = self._page.query_selector("input#d02")
            self.log(f"  [診断] input#d02: {'あり' if cb else 'なし（ページが読み込まれていない可能性）'}")

        # ① 「支払い例」チェックボックスをONにする（フォームが hidden になっているため）
        self._check_if_unchecked("input#d02", "支払い例チェックボックス")
        time.sleep(0.5)

        # ② 「フラット35S」ラジオボタンを選択
        self._click_radio("input[name='flatKbn'][value='2']", "フラット35S")
        time.sleep(0.5)

        # ③ フォームが表示されるまで少し待つ
        time.sleep(1.0)

        fields = [
            ("textarea[name='shriBknJoho']", "物件(住戸)情報",        config.shri_bkn_joho),
            ("textarea[name='shriKingaku']", "金額",                   kingaku_text),
            ("textarea[name='shriKinri']",   "金利",                   kinri_text),
            ("textarea[name='shriGakubu']",  "支払額",                 gakubu_text),
            ("textarea[name='shriLoan']",    "住宅ローンのご案内",     config.shri_loan),
            ("textarea[name='loanAnnai']",   "フラット35ローンご案内", config.loan_annai),
        ]

        for selector, label, value in fields:
            if not value:
                self.log(f"  - {label}: スキップ（値が空）")
                continue
            if self._fill_textarea(selector, value):
                preview = value[:30].replace("\n", " ")
                self.log(f"  ✓ {label}: {preview}...")
            else:
                self.log(f"  ✗ {label}: 入力欄が見つかりません")

        self.log("=== 支払い例の入力完了 ===")
        return True

    def _check_if_unchecked(self, selector: str, label: str) -> bool:
        """チェックボックスがOFFならONにする（Playwrightクリック経由）"""
        try:
            self._page.wait_for_selector(selector, timeout=5000, state="attached")
            loc = self._page.locator(selector).first
            # 既にチェック済みなら何もしない
            is_checked = self._page.evaluate(
                "(sel) => { const el = document.querySelector(sel); return el ? el.checked : false; }",
                selector
            )
            if is_checked:
                self.log(f"  ✓ {label}: 既にON")
                return True
            # Playwrightのネイティブクリックで押す（ページのJSイベントリスナーが動く）
            try:
                loc.click(timeout=5000)
            except Exception:
                # 非表示の場合は force=True で強制クリック
                loc.click(force=True, timeout=5000)
            time.sleep(0.3)
            self.log(f"  ✓ {label}: チェックをONにしました")
            return True
        except Exception as e:
            self.log(f"  ✗ {label}: {e}")
            return False

    def _click_radio(self, selector: str, label: str) -> bool:
        """ラジオボタンを選択する（JS経由）"""
        try:
            self._page.wait_for_selector(selector, timeout=5000, state="attached")
            result = self._page.evaluate("""
                (sel) => {
                    const el = document.querySelector(sel);
                    if (!el) return false;
                    el.checked = true;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    el.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                    return true;
                }
            """, selector)
            if result:
                self.log(f"  ✓ {label}: 選択しました")
            else:
                self.log(f"  ✗ {label}: 要素が見つかりません")
            return bool(result)
        except Exception as e:
            self.log(f"  ✗ {label}: {e}")
            return False

    # ==============================
    # タブ移動・保存
    # ==============================
    # SUUMO タブのIDマップ（DevToolsで確認済み）
    TAB_ID_MAP = {
        "基本情報":   "kihonTabSubmit",
        "内外観":     "nagaiId",
        "支払い例":   "kyotsuId",
        "レイアウト": "layoutId",
        "動画":       "cmId",
    }

    def _click_tab(self, tab_text: str, max_retry: int = 2) -> bool:
        """タブをクリックする（IDマップ優先 → title属性 → テキスト検索）。失敗時はリトライ。"""
        try:
            selectors = []

            # IDが分かっているタブはID指定（最確実）
            for key, tab_id in self.TAB_ID_MAP.items():
                if key in tab_text and tab_id:
                    selectors.append(f"a#{tab_id}")

            # title属性・テキスト系（汎用フォールバック）
            selectors += [
                f"a[title='{tab_text}']",
                f"a[title*='{tab_text}']",
                f"a:has-text('{tab_text}')",
                f"li:has-text('{tab_text}') > a",
            ]

            # 未保存確認ダイアログが出たら自動的にOKする
            def _accept_dialog(dialog):
                self.log(f"  [ダイアログ] 自動承認: {dialog.message[:60]}")
                try:
                    dialog.accept()
                except Exception:
                    pass

            self._page.on("dialog", _accept_dialog)

            def _try_click_once() -> bool:
                for sel in selectors:
                    try:
                        loc = self._page.locator(sel).first
                        if loc.count() > 0 and loc.is_visible(timeout=2000):
                            old_url = self._page.url
                            loc.click(timeout=3000)
                            # ページ遷移完了を待つ（load → networkidle → 追加待機）
                            try:
                                self._page.wait_for_load_state("load", timeout=10000)
                            except Exception:
                                pass
                            try:
                                self._page.wait_for_load_state("networkidle", timeout=8000)
                            except Exception:
                                pass
                            time.sleep(1.0)  # 追加待機（DOM描画・JS初期化完了を確実に待つ）
                            new_url = self._page.url
                            self.log(f"  [URL] {old_url.split('/')[-1]} → {new_url.split('/')[-1]}")
                            # #Disabled はタブが正常にロードされていないサイン → リトライ対象
                            if new_url.endswith("#Disabled"):
                                return False
                            return True
                    except Exception:
                        continue
                return False

            try:
                for attempt in range(max_retry):
                    ok = _try_click_once()
                    if ok:
                        self.log(f"  ✓ タブ移動: {tab_text}")
                        return True
                    if attempt < max_retry - 1:
                        self.log(f"  [retry] タブ移動失敗（{attempt + 1}回目）、再試行します...")
                        time.sleep(2.0)

                self.log(f"  ✗ タブが見つかりません: {tab_text}（手動でタブを開いてください）")
                return False
            finally:
                self._page.remove_listener("dialog", _accept_dialog)

        except Exception as e:
            self.log(f"  ✗ タブクリックエラー: {e}")
            return False

    def _check_save_error(self, retries: int = 3) -> bool:
        """保存後のページにエラーがあればダイアログを出して True を返す。

        保存ボタンを押した直後はページ遷移が始まっており、
        調べている途中で古いDOMが破棄されて
        「Execution context was destroyed」になることがある。
        これは失敗ではなく遷移が起きたというだけなので、
        新しいページが落ち着くのを待ってから調べ直す。
        """
        for attempt in range(1, retries + 1):
            hit = self._check_save_error_once(attempt, retries)
            if hit is not None:
                return hit
        self.log("  ※ ページ遷移中のためエラーチェックは省略しました（保存自体は完了）")
        return False

    def _check_save_error_once(self, attempt: int, retries: int):
        """エラー有無を返す。遷移中で判定できなかった場合は None。"""
        try:
            # 遷移が落ち着くのを待ってから調べる
            try:
                self._page.wait_for_load_state("domcontentloaded", timeout=10000)
            except Exception:
                pass
            error_el = self._page.query_selector("text=登録不可エラー")
            if not error_el:
                return False  # エラーなし

            # エラー詳細を取得
            details = self._page.evaluate("""
                () => {
                    const items = document.querySelectorAll('.errList li, .errList p, li.errItem');
                    if (items.length > 0) {
                        return Array.from(items).map(e => e.innerText.trim()).join('\\n');
                    }
                    // フォールバック: エラー一覧セクション全体のテキスト
                    const section = document.querySelector('.secTitleOuterR, .bdRed, [class*="err"]');
                    return section ? section.innerText.trim().slice(0, 300) : '（詳細取得失敗）';
                }
            """)
            msg = f"登録エラーが発生しました。\n\n{details}"
            self.log(f"  ✗ 登録エラー: {details}")

            import tkinter.messagebox as mb
            mb.showerror("SUUMO 登録エラー", msg)
            return True
        except Exception as e:
            text = str(e)
            navigating = ("context was destroyed" in text
                          or "Execution context" in text
                          or "navigation" in text.lower())
            if navigating and attempt < retries:
                time.sleep(1.5)   # 新しいページの描画を待って調べ直す
                return None
            if navigating:
                return None
            self.log(f"  [warn] エラーチェック失敗: {e}")
            return False

    def _save_tab(self) -> bool:
        """現在タブを登録保存する"""
        try:
            # 広めのセレクタリスト（登録保存・一時保存・保存 いずれも対象）
            selectors = [
                "a.btnImgRecord",                            # 実際のHTML確認済み
                "a:has-text('登録・保存')",                  # 中点あり
                "a:has-text('登録保存')",
                "input[type='submit'][value='登録保存']",
                "input[type='button'][value='登録保存']",
                "input[value='登録保存']",
                "input[type='submit'][value*='一時保存']",
                "input[type='submit'][value*='登録']",
                "input[type='submit'][value*='保存']",
                "button:has-text('登録保存')",
                "button:has-text('一時保存')",
                "button:has-text('保存')",
                "a:has-text('一時保存')",
            ]
            time.sleep(1.5)  # 保存前：入力・画像処理の完了を待つ
            for sel in selectors:
                try:
                    loc = self._page.locator(sel).first
                    if loc.count() == 0:
                        continue
                    # クリック → ページロード完了まで待つ
                    try:
                        loc.click(timeout=5000)
                    except Exception:
                        loc.click(force=True, timeout=5000)
                    try:
                        self._page.wait_for_load_state("load", timeout=15000)
                    except Exception:
                        time.sleep(3.0)
                    # 遷移が完全に終わるまで待つ（直後だとDOMが差し替わる途中で読めない）
                    try:
                        self._page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                    time.sleep(0.8)
                    # 登録エラーチェック
                    if self._check_save_error():
                        return False
                    self.log(f"  ✓ 登録保存完了（{sel}）")
                    return True
                except Exception:
                    continue

            # 見つからなかった場合は全 submit 要素をダンプして診断
            dump = self._page.evaluate("""
                () => {
                    const els = document.querySelectorAll(
                        'input[type=submit], input[type=button], button, a[href]'
                    );
                    return Array.from(els).map(e => ({
                        tag: e.tagName,
                        type: e.type || '',
                        value: e.value || '',
                        text: e.innerText ? e.innerText.trim().slice(0, 40) : '',
                        id: e.id || '',
                        name: e.name || ''
                    })).filter(e =>
                        e.value || (e.text && e.text.length < 20)
                    ).slice(0, 20);
                }
            """)
            self.log(f"  ✗ 保存ボタンが見つかりません。検出ボタン一覧: {dump}")
            return False
        except Exception as e:
            self.log(f"  ✗ 保存エラー: {e}")
            return False

    # ==============================
    # 内部ユーティリティ
    # ==============================
    def _fill(self, selector: str, value: str, timeout: int = 5000) -> bool:
        """input要素にJavaScript経由でテキストを入力する（可視性・スクロール不要）"""
        try:
            # DOMに存在するまで待つ
            self._page.wait_for_selector(selector, timeout=timeout, state="attached")
            result = self._page.evaluate("""
                ([sel, val]) => {
                    const el = document.querySelector(sel);
                    if (!el) return false;
                    el.value = val;
                    el.dispatchEvent(new Event('input',  {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                }
            """, [selector, str(value)])
            return bool(result)
        except Exception as e:
            self.log(f"    [fill err] {selector}: {e}")
            return False

    def _fill_textarea(self, selector: str, value: str, timeout: int = 5000) -> bool:
        """textarea要素にJavaScript経由でテキストを入力する"""
        try:
            self._page.wait_for_selector(selector, timeout=timeout, state="attached")
            result = self._page.evaluate("""
                ([sel, val]) => {
                    const el = document.querySelector(sel);
                    if (!el) return false;
                    el.value = val;
                    el.dispatchEvent(new Event('input',  {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                }
            """, [selector, str(value)])
            return bool(result)
        except Exception as e:
            self.log(f"    [fill_ta err] {selector}: {e}")
            return False
