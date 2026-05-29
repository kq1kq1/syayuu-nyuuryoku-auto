"""
HOMES (LIFULL HOME'S) 管理画面の自動化モジュール
"""
import time
import os
from typing import Optional, Callable
from .base import AutomationBase


class HomesAutomation(AutomationBase):
    """HOMES管理画面の自動化"""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None,
                 select_callback: Optional[Callable[[list], Optional[int]]] = None):
        super().__init__(log_callback)
        # 複数物件があるとき呼ばれるコールバック: (options: list[str]) -> int | None
        # None を返すとキャンセル扱い
        self._select_callback = select_callback

    # ==============================
    # 一括入力メインフロー
    # ==============================

    def fill_all(self, kenchu_bangou: str, photos: list = None,
                 photo_folder: str = "",
                 gaigai_photos: list = None,
                 naikan_photos: list = None) -> bool:
        """
        ① 物件一覧の「物件編集」クリック → 新タブへ切り替え
        ② 建築確認番号を入力して更新
        ③ 登録完了ページの「画像の編集」クリック
        ④ 基本画像: 画像アップロード + 説明文入力 → 保存
        ⑤ 外観・分譲地: タイトル（キャプション）+ コメント（文言）→ 保存
        ⑥ 内観: タイトル（キャプション）+ コメント（文言）→ 保存
        """
        self.log("=== ホームズ: 入力を開始します ===")

        if not self._connect_to_homes():
            return False

        # ① 物件編集 → 新タブ
        if not self._click_bukken_henshu():
            return False

        # ② 建築確認番号 → 更新（空欄の場合はスキップ）
        if kenchu_bangou:
            if not self._fill_kenchiku_bangou(kenchu_bangou):
                return False
            if not self._click_update():
                return False
        else:
            self.log("  — 建築確認番号なし（スキップ）")

        # ③ 画像の編集ページへ
        if not self._click_gazo_henshu():
            return False

        # ④ 基本画像: アップロード + 説明文 → 保存
        if photos:
            self._fill_photos_and_texts(photos, photo_folder)
        self._click_save()

        # ⑤ 外観・分譲地へ移動 → 画像 + タイトル + コメント → 保存
        if gaigai_photos:
            if self._click_gaigai_bunjo():
                self._fill_gaigai_bunjo(gaigai_photos, photo_folder)
                self._click_save()

        # ⑥ 内観へ移動 → 画像 + タイトル + コメント → 保存
        if naikan_photos:
            if self._click_naikan():
                self._fill_naikan(naikan_photos, photo_folder)
                self._click_save()

        self.log("=== ホームズ: 入力完了 ===")
        return True

    # ==============================
    # 接続
    # ==============================

    def _connect_to_homes(self) -> bool:
        """homes.co.jp のタブに切り替える"""
        if self.switch_to_page_by_url("homes.co.jp"):
            self.log(f"  ✓ ホームズタブに接続: {self._page.url}")
            return True
        self.log("  ✗ ホームズのタブが見つかりません")
        self.log("  → homes.co.jp の物件一覧ページを開いてください")
        return False

    # ==============================
    # ステップ①: 物件編集リンク
    # ==============================

    def _click_bukken_henshu(self) -> bool:
        """「物件編集」リンクをクリック（新タブで開き、そちらへ切り替え）
        複数物件がある場合は select_callback でユーザーに選択させる。
        """
        try:
            links = self._page.locator("a:has-text('物件編集')")
            count = links.count()

            if count == 0:
                self.log("  ✗ 物件編集リンクが見つかりません")
                return False

            if count == 1:
                target_idx = 0
                self.log("  ✓ 物件編集リンクを1件検出しました")
            else:
                # 各行の物件情報（名前・価格）を取得してユーザーに選ばせる
                self.log(f"  ⚠ 物件編集リンクが{count}件見つかりました → 選択ダイアログを表示します")
                options = []
                for i in range(count):
                    try:
                        label = self._page.evaluate("""
                            (i) => {
                                const all = Array.from(document.querySelectorAll('a'))
                                    .filter(a => a.textContent.trim() === '物件編集');
                                const link = all[i];
                                if (!link) return '';
                                const row = link.closest('tr') || link.closest('li')
                                          || link.closest('.item') || link.parentElement;
                                if (!row) return '物件 ' + (i + 1);
                                return row.innerText.replace(/\\s+/g, ' ').trim().slice(0, 120);
                            }
                        """, i)
                        options.append(label.strip() if label else f"物件 {i + 1}")
                    except Exception:
                        options.append(f"物件 {i + 1}")

                if self._select_callback:
                    selected = self._select_callback(options)
                    if selected is None:
                        self.log("  ✗ 物件選択がキャンセルされました")
                        return False
                    target_idx = selected
                else:
                    # コールバックなし → 先頭を自動選択
                    target_idx = 0
                    self.log("  ⚠ 選択コールバックなし → 先頭の物件を自動選択します")

            # 選択された物件編集リンクをクリック
            with self._page.context.expect_page(timeout=10000) as new_page_info:
                links.nth(target_idx).click(timeout=5000)
            new_page = new_page_info.value
            new_page.wait_for_load_state("load", timeout=15000)
            try:
                new_page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            time.sleep(1.0)
            self._page = new_page
            self.log("  ✓ 物件編集ページを開きました")
            return True
        except Exception as e:
            self.log(f"  ✗ 物件編集リンクのクリックエラー: {e}")
            return False

    # ==============================
    # ステップ②: 建築確認番号 → 更新
    # ==============================

    def _fill_kenchiku_bangou(self, bangou: str) -> bool:
        """建築確認番号（input#kenchikuNum）を入力する"""
        try:
            inp = self._page.locator("input#kenchikuNum")
            inp.click(timeout=3000)
            inp.fill(bangou, timeout=3000)
            self.log(f"  ✓ 建築確認番号: {bangou}")
            return True
        except Exception as e:
            self.log(f"  ✗ 建築確認番号入力エラー: {e}")
            return False

    def _click_update(self) -> bool:
        """「この内容で更新する」ボタンをクリックして完了まで待つ"""
        try:
            btn = self._page.locator("input[type='submit'][value='この内容で更新する']")
            btn.click(timeout=5000)
            self._page.wait_for_load_state("load", timeout=15000)
            try:
                self._page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            time.sleep(1.5)
            self.log("  ✓ 更新完了")
            return True
        except Exception as e:
            self.log(f"  ✗ 更新ボタンクリックエラー: {e}")
            return False

    # ==============================
    # ステップ③: 画像の編集へ
    # ==============================

    def _click_gazo_henshu(self) -> bool:
        """登録完了ページの「画像の編集」リンクをクリック"""
        try:
            self._page.locator("a:has-text('画像の編集')").click(timeout=5000)
            self._page.wait_for_load_state("load", timeout=15000)
            try:
                self._page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            time.sleep(1.0)
            self.log("  ✓ 画像の編集ページへ移動しました")
            return True
        except Exception as e:
            self.log(f"  ✗ 画像の編集リンクのクリックエラー: {e}")
            return False

    # ==============================
    # ステップ④: 画像 + 説明文
    # ==============================

    def _fill_photos_and_texts(self, photos: list, photo_folder: str) -> bool:
        """
        各スロット（data-index=1〜）へ画像アップロードと説明文を入力する。
        - ファイル名なし＋文言あり → 説明文のみ入力
        - ファイル名あり           → 画像アップロード＋説明文入力
        キャプション（ホームズでは不使用）は無視する。
        """
        self.log("=== ホームズ: 画像・説明文の入力を開始します ===")
        uploaded = 0

        for idx, photo in enumerate(photos, 1):
            has_file = bool(photo.filename)
            has_text = bool(photo.text)

            if not has_file and not has_text:
                continue

            # ① 画像アップロード
            if has_file:
                filepath = os.path.join(photo_folder, photo.filename)
                if os.path.exists(filepath):
                    try:
                        drop_area = self._page.locator(
                            f"div.dropArea[data-index='{idx}']"
                        )
                        # data-name="Image" で画像用のみを指定（マップ用mapPicと区別）
                        file_input = drop_area.locator(
                            "input[type='file'][data-name='Image']"
                        )
                        if file_input.count() > 0:
                            file_input.set_input_files(filepath)
                        else:
                            # なければ「画像を参照」ボタン経由のファイルチューザー
                            with self._page.expect_file_chooser(timeout=5000) as fc:
                                drop_area.locator(
                                    "a:has-text('参照'), button:has-text('参照')"
                                ).first.click(timeout=3000)
                            fc.value.set_files(filepath)
                        uploaded += 1
                        time.sleep(0.8)  # アップロード後、textarea が活性化するまで待つ
                    except Exception as e:
                        self.log(f"  ✗ 画像アップロードエラー（スロット{idx}）: {e}")
                else:
                    self.log(f"  ✗ ファイルなし: {filepath}")

            # ② 説明文入力（JS経由: 非表示・未活性スロットも強制入力）
            if has_text:
                done = self._page.evaluate("""
                    ([n, val]) => {
                        const ta = document.querySelector(
                            `textarea[name='pict_comment${n}']`
                        );
                        if (!ta) return false;
                        ta.value = val;
                        ta.dispatchEvent(new Event('input',  {bubbles: true}));
                        ta.dispatchEvent(new Event('change', {bubbles: true}));
                        return true;
                    }
                """, [idx, photo.text])
                if not done:
                    self.log(f"  ✗ 説明文: textarea[name='pict_comment{idx}'] が見つかりません")

        self.log(f"=== ホームズ: 画像・説明文入力完了（{uploaded}枚アップロード） ===")
        return True

    # ==============================
    # ステップ⑤: 外観・分譲地へ移動
    # ==============================

    def _click_gaigai_bunjo(self) -> bool:
        """保存後モーダルの「外観・分譲地」リンクをクリックしてページ移動"""
        try:
            # 完了モーダルが出るまで待つ
            self._page.wait_for_selector("div.modalImageComplete", timeout=10000)
            self._page.locator("a.itemConfirm.exterior").click(timeout=5000)
            self._page.wait_for_load_state("load", timeout=15000)
            try:
                self._page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            time.sleep(1.0)
            self.log("  ✓ 外観・分譲地ページへ移動しました")
            return True
        except Exception as e:
            self.log(f"  ✗ 外観・分譲地リンクのクリックエラー: {e}")
            return False

    def _fill_gaigai_bunjo(self, photos: list, photo_folder: str = "") -> bool:
        """
        外観・分譲地: 画像アップロード → タイトル（キャプション）+ コメント（文言）をJS入力。
        - ファイル名あり → 画像アップロード後にフィールドが表示されるのを待ってテキスト入力
        - ファイル名なし → テキストのみJS入力（既存画像あり想定）
        - キャプション → input[name="images[n][title]"]
        - 文言         → textarea[name="images[n][comment]"]
        """
        self.log("=== ホームズ: 外観・分譲地の入力を開始します ===")
        uploaded = 0

        for idx, photo in enumerate(photos, 1):
            has_file    = bool(photo.filename)
            has_caption = bool(photo.caption)
            has_text    = bool(photo.text)

            if not has_file and not has_caption and not has_text:
                continue

            # ① 画像アップロード
            if has_file:
                filepath = os.path.join(photo_folder, photo.filename)
                if os.path.exists(filepath):
                    try:
                        drop_area = self._page.locator(
                            f"div.dropArea[data-index='{idx}']"
                        )
                        # 外観・分譲地は data-name="SpecialImage"
                        file_input = drop_area.locator(
                            "input[type='file'][data-name='SpecialImage']"
                        )
                        if file_input.count() == 0:
                            file_input = drop_area.locator(
                                "input[type='file']"
                            ).first
                        file_input.set_input_files(filepath)
                        uploaded += 1
                        time.sleep(1.0)  # フィールド表示を待つ
                    except Exception as e:
                        self.log(f"  ✗ 画像アップロードエラー（スロット{idx}）: {e}")
                else:
                    self.log(f"  ✗ ファイルなし: {filepath}")

            # ② タイトル（キャプション）
            if has_caption:
                done = self._page.evaluate("""
                    ([n, val]) => {
                        const inp = document.querySelector(
                            `input[name="images[${n}][title]"]`
                        );
                        if (!inp) return false;
                        inp.value = val;
                        inp.dispatchEvent(new Event('input',  {bubbles: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                        return true;
                    }
                """, [idx, photo.caption])
                if not done:
                    self.log(f"  ✗ タイトル: images[{idx}][title] が見つかりません")

            # ③ コメント（文言）
            if has_text:
                done = self._page.evaluate("""
                    ([n, val]) => {
                        const ta = document.querySelector(
                            `textarea[name="images[${n}][comment]"]`
                        );
                        if (!ta) return false;
                        ta.value = val;
                        ta.dispatchEvent(new Event('input',  {bubbles: true}));
                        ta.dispatchEvent(new Event('change', {bubbles: true}));
                        return true;
                    }
                """, [idx, photo.text])
                if not done:
                    self.log(f"  ✗ コメント: images[{idx}][comment] が見つかりません")

        self.log(f"=== ホームズ: 外観・分譲地入力完了（{uploaded}枚アップロード） ===")
        return True

    # ==============================
    # ステップ⑥: 内観へ移動
    # ==============================

    def _click_naikan(self) -> bool:
        """保存後モーダルの「内観」リンクをクリックしてページ移動"""
        try:
            # 完了モーダルが出るまで待つ
            self._page.wait_for_selector("div.modalImageComplete", timeout=10000)
            self._page.locator("a.itemConfirm.interior").click(timeout=5000)
            self._page.wait_for_load_state("load", timeout=15000)
            try:
                self._page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            time.sleep(1.0)
            self.log("  ✓ 内観ページへ移動しました")
            return True
        except Exception as e:
            self.log(f"  ✗ 内観リンクのクリックエラー: {e}")
            return False

    def _fill_naikan(self, photos: list, photo_folder: str = "") -> bool:
        """
        内観: 画像アップロード → タイトル（キャプション）+ コメント（文言）をJS入力。
        - キャプション → input[name="images[n][title]"]
        - 文言         → textarea[name="images[n][comment]"]
        """
        self.log("=== ホームズ: 内観の入力を開始します ===")
        uploaded = 0

        for idx, photo in enumerate(photos, 1):
            has_file    = bool(photo.filename)
            has_caption = bool(photo.caption)
            has_text    = bool(photo.text)

            if not has_file and not has_caption and not has_text:
                continue

            # ① 画像アップロード
            if has_file:
                filepath = os.path.join(photo_folder, photo.filename)
                if os.path.exists(filepath):
                    try:
                        drop_area = self._page.locator(
                            f"div.dropArea[data-index='{idx}']"
                        )
                        # 内観は data-name="SpecialImage"（外観・分譲地と同じ）
                        file_input = drop_area.locator(
                            "input[type='file'][data-name='SpecialImage']"
                        )
                        if file_input.count() == 0:
                            file_input = drop_area.locator(
                                "input[type='file']"
                            ).first
                        file_input.set_input_files(filepath)
                        uploaded += 1
                        time.sleep(1.0)  # フィールド表示を待つ
                    except Exception as e:
                        self.log(f"  ✗ 画像アップロードエラー（スロット{idx}）: {e}")
                else:
                    self.log(f"  ✗ ファイルなし: {filepath}")

            # ② タイトル（キャプション）
            if has_caption:
                done = self._page.evaluate("""
                    ([n, val]) => {
                        const inp = document.querySelector(
                            `input[name="images[${n}][title]"]`
                        );
                        if (!inp) return false;
                        inp.value = val;
                        inp.dispatchEvent(new Event('input',  {bubbles: true}));
                        inp.dispatchEvent(new Event('change', {bubbles: true}));
                        return true;
                    }
                """, [idx, photo.caption])
                if not done:
                    self.log(f"  ✗ タイトル: images[{idx}][title] が見つかりません")

            # ③ コメント（文言）
            if has_text:
                done = self._page.evaluate("""
                    ([n, val]) => {
                        const ta = document.querySelector(
                            `textarea[name="images[${n}][comment]"]`
                        );
                        if (!ta) return false;
                        ta.value = val;
                        ta.dispatchEvent(new Event('input',  {bubbles: true}));
                        ta.dispatchEvent(new Event('change', {bubbles: true}));
                        return true;
                    }
                """, [idx, photo.text])
                if not done:
                    self.log(f"  ✗ コメント: images[{idx}][comment] が見つかりません")

        self.log(f"=== ホームズ: 内観入力完了（{uploaded}枚アップロード） ===")
        return True

    # ==============================
    # 保存
    # ==============================

    def _click_save(self) -> bool:
        """「この内容で登録する」ボタンをクリック"""
        try:
            btn = self._page.locator(
                "input[type='submit'][value='この内容で登録する']"
            )
            btn.click(timeout=5000)
            self._page.wait_for_load_state("load", timeout=15000)
            try:
                self._page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            time.sleep(1.5)
            self.log("  ✓ 保存完了（この内容で登録する）")
            return True
        except Exception as e:
            self.log(f"  ✗ 保存ボタンクリックエラー: {e}")
            return False
