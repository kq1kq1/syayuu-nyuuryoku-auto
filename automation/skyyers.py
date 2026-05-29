"""
スカイヤーズ（sys.arcs.jp）管理画面の自動化モジュール

入力フロー:
  ① おすすめ物件チェック（input#osusume_flag）
  ② 担当者選択（select#tanto_cd）
  ③ 建築確認番号（input#build_confirm_no）
  ④ 画像スロットごとに
     - 画像アップロード（input[name="IMG_FILE{n}"]）
     - キャプション選択（select#IMG_KIND{n}）
     - コメント入力（textarea#IMG_COMM{n}）
  ⑤ 保存ボタン（input#bt_upd）
"""
import time
import os
from typing import Optional, Callable
from .base import AutomationBase


class SkyeyersAutomation(AutomationBase):
    """スカイヤーズ管理画面の自動化"""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        super().__init__(log_callback)

    # ==============================
    # 一括入力メインフロー
    # ==============================

    def fill_all(self, tantosha_name: str = "", kenchu_bangou: str = "",
                 photos: list = None, photo_folder: str = "") -> bool:
        """
        ① おすすめチェック
        ② 担当者選択
        ③ 建築確認番号入力
        ④ 画像・キャプション・コメント入力
        ⑤ 保存
        """
        self.log("=== スカイヤーズ: 入力を開始します ===")

        if not self._connect_to_skyyers():
            return False

        # ① おすすめチェック
        self._check_osusume()

        # ② 担当者
        if tantosha_name:
            self._select_tanto(tantosha_name)

        # ③ 建築確認番号
        if kenchu_bangou:
            self._fill_kenchiku_bangou(kenchu_bangou)

        # ④ 画像・キャプション・コメント
        if photos:
            self._fill_slots(photos, photo_folder)

        # ⑤ 保存
        self._click_save()

        self.log("=== スカイヤーズ: 入力完了 ===")
        return True

    # ==============================
    # 接続
    # ==============================

    def _connect_to_skyyers(self) -> bool:
        """スカイヤーズのタブに切り替える"""
        if self.switch_to_page_by_url("arcs.jp"):
            self._page.bring_to_front()
            self.log(f"  ✓ スカイヤーズタブに接続: {self._page.url}")
            return True
        self.log("  ✗ スカイヤーズのタブが見つかりません")
        self.log("  → sys.arcs.jp の物件編集ページを開いてください")
        return False

    # ==============================
    # ① おすすめチェック
    # ==============================

    def _check_osusume(self) -> bool:
        """おすすめ物件チェックボックスにチェックを入れる"""
        try:
            cb = self._page.locator("input#osusume_flag")
            if not cb.is_checked(timeout=3000):
                cb.check(timeout=3000)
            self.log("  ✓ おすすめ物件チェック")
            return True
        except Exception as e:
            self.log(f"  ✗ おすすめチェックエラー: {e}")
            return False

    # ==============================
    # ② 担当者選択
    # ==============================

    def _select_tanto(self, tanto_name: str) -> bool:
        """担当者ドロップダウンから名前でマッチして選択"""
        try:
            # 完全一致で試みる
            self._page.select_option("select#tanto_cd", label=tanto_name, timeout=3000)
            self.log(f"  ✓ 担当者: {tanto_name}")
            return True
        except Exception:
            pass
        # 部分一致フォールバック
        try:
            result = self._page.evaluate("""
                (name) => {
                    const sel = document.querySelector('select#tanto_cd');
                    if (!sel) return '担当者セレクト未検出';
                    for (const opt of sel.options) {
                        if (opt.text.includes(name) || name.includes(opt.text.trim())) {
                            sel.value = opt.value;
                            sel.dispatchEvent(new Event('change', {bubbles: true}));
                            return 'ok:' + opt.text.trim();
                        }
                    }
                    return '未一致: ' + name;
                }
            """, tanto_name)
            if result.startswith('ok:'):
                self.log(f"  ✓ 担当者（部分一致）: {result[3:]}")
                return True
            else:
                self.log(f"  ✗ 担当者選択エラー: {result}")
                return False
        except Exception as e:
            self.log(f"  ✗ 担当者選択エラー: {e}")
            return False

    # ==============================
    # ③ 建築確認番号
    # ==============================

    def _fill_kenchiku_bangou(self, bangou: str) -> bool:
        """建築確認番号を入力する"""
        try:
            inp = self._page.locator("input#build_confirm_no")
            inp.fill(bangou, timeout=3000)
            self.log(f"  ✓ 建築確認番号: {bangou}")
            return True
        except Exception as e:
            self.log(f"  ✗ 建築確認番号エラー: {e}")
            return False

    # ==============================
    # ④ 画像・キャプション・コメント
    # ==============================

    def _slot_is_target(self, n: int) -> bool:
        """スロットnのIMG_KINDが空白または外観のときTrueを返す（ピタクラと同じ考え方）"""
        try:
            text = self._page.evaluate(f"""
                () => {{
                    const sel = document.querySelector('select#IMG_KIND{n}');
                    if (!sel) return null;
                    const opt = sel.options[sel.selectedIndex];
                    return opt ? opt.text.trim() : '';
                }}
            """)
            # nullはスロットが存在しない、''または'外観'のみ入力対象
            if text is None:
                return False
            return text == '' or text == '外観' or text == '内観'
        except Exception:
            return False

    def _fill_slots(self, photos: list, photo_folder: str) -> None:
        """ページのスロットをスキャンし、空白か外観のスロットにのみExcel行を割り当てる。
        それ以外のスロット（内観・間取り等）はスキップしてExcel行を消費しない。"""
        self.log("=== スカイヤーズ: 画像スロット入力開始 ===")

        # ページ上のスロット総数を取得
        slot_count = self._page.evaluate("""
            () => document.querySelectorAll('select[id^="IMG_KIND"]').length
        """)
        self.log(f"  ページ上スロット数: {slot_count}")

        active = [p for p in photos if p.filename or p.caption or p.text]
        ok_count  = 0
        photo_idx = 0

        for n in range(1, slot_count + 1):
            if photo_idx >= len(active):
                break

            if not self._slot_is_target(n):
                self.log(f"  → スロット{n} スキップ（既存キャプションあり）")
                continue  # Excel行を消費しない

            photo = active[photo_idx]

            # --- 画像アップロード ---
            if photo.filename:
                filepath = os.path.join(photo_folder, photo.filename)
                if os.path.exists(filepath):
                    try:
                        file_inp = self._page.locator(f"input[name='IMG_FILE{n}']")
                        file_inp.set_input_files(filepath, timeout=5000)
                        time.sleep(1.0)
                    except Exception as e:
                        self.log(f"  ✗ 画像エラー（スロット{n}）: {e}")
                else:
                    self.log(f"  ✗ ファイルなし: {filepath}")

            # --- キャプション選択 ---
            if photo.caption:
                try:
                    self._page.select_option(
                        f"select#IMG_KIND{n}", label=photo.caption, timeout=3000
                    )
                except Exception:
                    try:
                        self._page.evaluate("""
                            ([n, label]) => {
                                const sel = document.querySelector('select#IMG_KIND' + n);
                                if (!sel) return;
                                for (const opt of sel.options) {
                                    if (opt.text.includes(label) || label.includes(opt.text.trim())) {
                                        sel.value = opt.value;
                                        sel.dispatchEvent(new Event('change', {bubbles: true}));
                                        return;
                                    }
                                }
                            }
                        """, [n, photo.caption])
                    except Exception as e:
                        self.log(f"  ✗ キャプションエラー（スロット{n}）: {e}")

            # --- コメント入力 ---
            if photo.text:
                try:
                    ta = self._page.locator(f"textarea#IMG_COMM{n}")
                    ta.fill(photo.text, timeout=3000)
                except Exception as e:
                    self.log(f"  ✗ コメントエラー（スロット{n}）: {e}")

            ok_count += 1
            photo_idx += 1
            time.sleep(0.3)

        self.log(f"=== スカイヤーズ: スロット入力完了（{ok_count}件） ===")

    # ==============================
    # ⑤ 保存
    # ==============================

    def _click_save(self) -> bool:
        """更新ボタン → 確認ダイアログを自動でOK → 保存完了"""
        try:
            # 確認ダイアログ（confirm）を自動でOKにするハンドラを登録
            self._page.once("dialog", lambda dlg: dlg.accept())

            # bt_regist(document.oform, 1) を直接呼び出す
            self._page.evaluate("bt_regist(document.oform, 1)")
            self.log("  ✓ 更新ボタンを実行・ダイアログをOK")
        except Exception as e:
            self.log(f"  △ bt_regist 未検出、element.click() で代替: {e}")
            try:
                self._page.once("dialog", lambda dlg: dlg.accept())
                self._page.evaluate("document.querySelector('input#bt_upd').click()")
            except Exception as e2:
                self.log(f"  ✗ 保存ボタンクリックエラー: {e2}")
                return False

        try:
            self._page.wait_for_load_state("load", timeout=15000)
            try:
                self._page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
        except Exception:
            pass

        time.sleep(1.5)
        self.log("  ✓ 保存完了")
        return True
