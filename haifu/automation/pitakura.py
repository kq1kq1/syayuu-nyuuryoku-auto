"""
ピタクラ管理画面の自動化モジュール
Vue.js + Element UI (el-upload) ベース

ページスロット構成:
  外観画像セクション: 初期3スロット（行1〜5をここへ）
  その他画像セクション: 初期3スロット（行6以降をここへ）
"""
import time
import os
from typing import Optional, Callable
from .base import AutomationBase


# ===== ページ定数 =====
_GAIKAN_ROWS = 5   # Excel行1〜5を外観セクションへ
_GAIKAN_INIT = 3   # 外観の初期スロット数
_SONOTA_INIT = 3   # その他の初期スロット数


class PitakuraAutomation(AutomationBase):
    """ピタクラ管理画面の自動化"""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None,
                 select_callback: Optional[Callable[[list], Optional[int]]] = None):
        super().__init__(log_callback)
        self._select_callback = select_callback  # (urls: list[str]) -> int | None

    # ==============================
    # 一括入力メインフロー
    # ==============================

    def fill_all(self, kenchu_bangou: str = "",
                 photos: list = None, photo_folder: str = "") -> bool:
        """
        ① 建築確認番号入力
        ② スロット準備（+追加ボタンでスロット確保）
        ③ 画像アップロード（1枚ずつ）
        ④ セレクタ（写真種別）入力
        ⑤ 文言テキスト入力
        ⑥ 保存
        """
        self.log("=== ピタクラ: 入力を開始します ===")

        if not self._connect_to_pitakura():
            return False

        # ① 建築確認番号
        if kenchu_bangou:
            self._fill_kenchiku_bangou(kenchu_bangou)

        if photos:
            # ② スロット準備
            self._prepare_slots(photos)

            # ③ スロット割り当て（「その他」スロットをスキップしてExcel行を詰める）
            assignments = self._assign_slots(photos)

            # ④ 画像アップロード
            uploaded_slots = self._fill_images(assignments, photo_folder)

            # ⑤ セレクタ（アップロード済み分のみ）
            self._fill_captions(assignments, uploaded_slots)

            # ⑥ 文言（アップロード済み分のみ）
            self._fill_texts(assignments, uploaded_slots)

        # ⑥ 保存
        self._click_save()

        self.log("=== ピタクラ: 入力完了 ===")
        return True

    # ==============================
    # 接続
    # ==============================

    def _connect_to_pitakura(self) -> bool:
        # /edit を含む物件編集ページのみ対象
        all_pages = self.get_pages_by_url("pitat-cloud.com")
        pages = [p for p in all_pages if "/edit" in p.url]

        if not pages:
            self.log("  ✗ ピタクラの物件編集タブが見つかりません")
            self.log("  → URL に /edit を含む物件編集ページを開いてください")
            return False

        if len(pages) == 1:
            self._page = pages[0]
            self._page.bring_to_front()
            self.log(f"  ✓ ピタクラタブに接続: {self._page.url}")
            return True

        # ---- 複数タブ: ユーザーに選択させる ----
        self.log(f"  ピタクラ物件編集タブが{len(pages)}個見つかりました。タブを選択してください")
        if self._select_callback:
            urls = [p.url for p in pages]
            idx = self._select_callback(urls)
            if idx is None:
                self.log("  ✗ タブ選択がキャンセルされました")
                return False
            self._page = pages[idx]
        else:
            self._page = pages[0]
            self.log("  （コールバック未設定のため先頭タブを使用）")

        self._page.bring_to_front()
        self.log(f"  ✓ ピタクラタブに接続: {self._page.url}")
        return True

    # ==============================
    # ① 建築確認番号
    # ==============================

    def _fill_kenchiku_bangou(self, bangou: str) -> bool:
        """「建築確認番号」ラベルの行にあるテキスト入力へJSで入力"""
        try:
            done = self._page.evaluate("""
                (val) => {
                    const rows = document.querySelectorAll('.row-struct, .row');
                    for (const row of rows) {
                        const label = row.querySelector('[class*="row-label"], [class*="label"]');
                        if (label && label.textContent.includes('建築確認番号')) {
                            const inp = row.querySelector(
                                'input[type="text"], input:not([type="radio"]):not([type="checkbox"]):not([type="file"])'
                            );
                            if (inp) {
                                inp.focus();
                                inp.value = '';
                                inp.value = val;
                                inp.dispatchEvent(new Event('input',  {bubbles: true}));
                                inp.dispatchEvent(new Event('change', {bubbles: true}));
                                inp.blur();
                                return true;
                            }
                        }
                    }
                    return false;
                }
            """, bangou)
            if done:
                self.log(f"  ✓ 建築確認番号: {bangou}")
            else:
                self.log("  ✗ 建築確認番号フィールドが見つかりません")
            return bool(done)
        except Exception as e:
            self.log(f"  ✗ 建築確認番号入力エラー: {e}")
            return False

    # ==============================
    # ② スロット準備
    # ==============================

    def _has_content(self, photo) -> bool:
        return bool(photo.filename or photo.caption or photo.text)

    def _prepare_slots(self, photos: list) -> None:
        """外観・その他の各セクションに必要なスロット数を確保する"""

        gaikan_need = sum(1 for p in photos[:_GAIKAN_ROWS] if self._has_content(p))
        sonota_need = sum(1 for p in photos[_GAIKAN_ROWS:] if self._has_content(p))

        # 追加前の既存スロットに「その他」スキップが何個あるか確認
        gaikan_skipped = sum(1 for i in range(_GAIKAN_INIT)
                             if self._slot_caption_is_sonota(i))
        sonota_skipped = sum(1 for i in range(_GAIKAN_INIT, _GAIKAN_INIT + _SONOTA_INIT)
                             if self._slot_caption_is_sonota(i))

        # 外観の追加数（スキップ分は補わない：溢れた行はその他へ）
        gaikan_add = max(0, gaikan_need - _GAIKAN_INIT)

        # 外観セクションの実収容可能数（追加後 - スキップ）
        gaikan_capacity = (_GAIKAN_INIT + gaikan_add) - gaikan_skipped
        # 外観に収まりきらない分はその他へオーバーフロー
        overflow = max(0, gaikan_need - gaikan_capacity)

        # その他の実効必要数（= その他のExcel行 + 外観からの溢れ）
        effective_sonota_need = sonota_need + overflow
        # その他の追加数（既存スロットのスキップ分も補う）
        sonota_add = max(0, effective_sonota_need - (_SONOTA_INIT - sonota_skipped))

        overflow_msg = f"（外観から{overflow}枚溢れ）" if overflow else ""
        self.log(
            f"  外観: {gaikan_need}枚 スキップ{gaikan_skipped} +{gaikan_add}追加 /"
            f" その他: {effective_sonota_need}枚{overflow_msg} スキップ{sonota_skipped} +{sonota_add}追加"
        )

        if gaikan_add == 0 and sonota_add == 0:
            return

        # 「外観画像」「その他画像」ラベルを含む section-bar 内のボタンをJS経由でクリック
        for label, count, name in [("外観画像", gaikan_add, "外観"), ("その他画像", sonota_add, "その他")]:
            if count == 0:
                continue
            ok_count = 0
            for i in range(count):
                result = self._page.evaluate("""
                    (label) => {
                        // [class*="section-bar"] を持つ全要素からラベルテキストで絞り込む
                        const bars = document.querySelectorAll('[class*="section-bar"]');
                        for (const bar of bars) {
                            if (bar.textContent.includes(label)) {
                                const btn = bar.querySelector(
                                    'button[class*="button-white"], button[class*="initial-active"]'
                                );
                                if (btn) {
                                    btn.dispatchEvent(
                                        new MouseEvent('click', {bubbles: true, cancelable: true, view: window})
                                    );
                                    return true;
                                }
                            }
                        }
                        return false;
                    }
                """, label)
                if result:
                    ok_count += 1
                else:
                    self.log(f"  ✗ 「{label}」セクションの+追加ボタンが見つかりません")
                    break
                time.sleep(0.8)

            if ok_count > 0:
                self.log(f"  ✓ {name}画像 +{ok_count}スロット追加（計{[gaikan_need, sonota_need][name=='その他']}枠）")

    # ==============================
    # スロット取得ヘルパー
    # ==============================

    def _get_slot(self, slot_idx: int):
        """slot_idx 番目（0始まり）のスロット要素を返す"""
        return self._page.locator("div.divide-equally-add-col.handle").nth(slot_idx)

    def _active_photos(self, photos: list) -> list:
        """_prepare_slots 用: content があるものだけ (slot_idx, photo) のリストで返す"""
        result = []
        idx = 0
        for photo in photos:
            if self._has_content(photo):
                result.append((idx, photo))
                idx += 1
        return result

    def _assign_slots(self, photos: list) -> list:
        """
        ページスロットを順にスキャンし、Excelの写真行を割り当てる。
        ページのセレクタが「その他」のスロットはスキップし、Excel行を消費しない。
        戻り値: [(slot_idx, photo), ...]
        """
        active = [p for p in photos if self._has_content(p)]
        if not active:
            return []

        slot_count = self._page.locator("div.divide-equally-add-col.handle").count()
        result = []
        photo_idx = 0

        for slot_idx in range(slot_count):
            if photo_idx >= len(active):
                break
            if self._slot_caption_is_sonota(slot_idx):
                self.log(f"  → スロット{slot_idx + 1} スキップ（セレクタ:その他）")
                # Excel行は消費しない
                continue
            result.append((slot_idx, active[photo_idx]))
            photo_idx += 1

        return result

    # ==============================
    # ③ 画像アップロード（1枚ずつ）
    # ==============================

    def _slot_caption_is_sonota(self, slot_idx: int) -> bool:
        """ページ上のスロットのセレクタが「その他」になっていればTrue"""
        try:
            return bool(self._page.evaluate("""
                (idx) => {
                    const slots = document.querySelectorAll('div.divide-equally-add-col.handle');
                    const slot = slots[idx];
                    if (!slot) return false;
                    const sel = slot.querySelector(':scope > div:nth-child(2) > .select-wrap > select');
                    if (!sel) return false;
                    const selected = sel.options[sel.selectedIndex];
                    return selected && selected.text.trim() === 'その他';
                }
            """, slot_idx))
        except Exception:
            return False

    def _fill_images(self, assignments: list, photo_folder: str) -> set:
        """_assign_slots の結果を受け取り、1枚ずつアップロード。
        戻り値: 処理対象となったスロット番号の set"""
        self.log("=== ピタクラ: 画像アップロード開始 ===")
        uploaded_slots: set = set()

        for slot_idx, photo in assignments:
            if not photo.filename:
                # ファイルなしでもキャプション・文言は入れる
                uploaded_slots.add(slot_idx)
                continue

            filepath = os.path.join(photo_folder, photo.filename)
            if not os.path.exists(filepath):
                self.log(f"  ✗ ファイルなし: {filepath}")
                continue
            try:
                slot = self._get_slot(slot_idx)
                with self._page.expect_file_chooser(timeout=8000) as fc:
                    slot.locator("button:has-text('選択')").click(timeout=5000)
                fc.value.set_files(filepath)
                uploaded_slots.add(slot_idx)
                time.sleep(1.5)
            except Exception as e:
                self.log(f"  ✗ 画像アップロードエラー（スロット{slot_idx + 1}）: {e}")

        self.log(f"=== ピタクラ: 画像アップロード完了（{len(uploaded_slots)}枚） ===")
        return uploaded_slots

    # ==============================
    # ④ セレクタ（写真種別）
    # ==============================

    def _fill_captions(self, assignments: list, uploaded_slots: set) -> None:
        """各スロットの写真種別セレクタをJSで選択。
        アップロード済みスロット（uploaded_slots）のみ処理する。"""
        self.log("=== ピタクラ: セレクタ入力開始 ===")
        ok_count = 0

        for slot_idx, photo in assignments:
            if not photo.caption:
                continue
            if slot_idx not in uploaded_slots:
                continue
            try:
                result = self._page.evaluate("""
                    ([idx, label]) => {
                        const slots = document.querySelectorAll('div.divide-equally-add-col.handle');
                        const slot = slots[idx];
                        if (!slot) return 'スロット未検出';

                        // :scope で直下の div:nth-child(2) > .select-wrap > select に限定
                        const sel = slot.querySelector(
                            ':scope > div:nth-child(2) > .select-wrap > select'
                        );
                        if (!sel) return 'select未検出';

                        // 完全一致で選択
                        for (const opt of sel.options) {
                            if (opt.text.trim() === label) {
                                sel.value = opt.value;
                                sel.dispatchEvent(new Event('change', {bubbles: true}));
                                sel.dispatchEvent(new Event('input',  {bubbles: true}));
                                return 'ok';
                            }
                        }
                        // 部分一致フォールバック
                        for (const opt of sel.options) {
                            if (opt.text.trim().includes(label) || label.includes(opt.text.trim())) {
                                sel.value = opt.value;
                                sel.dispatchEvent(new Event('change', {bubbles: true}));
                                sel.dispatchEvent(new Event('input',  {bubbles: true}));
                                return 'ok(部分一致:' + opt.text.trim() + ')';
                            }
                        }
                        const choices = Array.from(sel.options).map(o => o.text.trim()).join(' / ');
                        return '未一致: "' + label + '" / 選択肢: ' + choices;
                    }
                """, [slot_idx, photo.caption])

                if result.startswith('ok'):
                    ok_count += 1
                    self.log(f"  ✓ セレクタ（スロット{slot_idx + 1}）: {photo.caption}")
                else:
                    self.log(f"  ✗ セレクタエラー（スロット{slot_idx + 1}）: {result}")
                time.sleep(0.3)
            except Exception as e:
                self.log(f"  ✗ セレクタエラー（スロット{slot_idx + 1}）: {e}")

        self.log(f"=== ピタクラ: セレクタ入力完了（{ok_count}件） ===")

    # ==============================
    # ⑤ 文言テキスト
    # ==============================

    def _fill_texts(self, assignments: list, uploaded_slots: set) -> None:
        """span.textbox-wrap.col-36.ignore-handle input へ文言を入力。
        アップロード済みスロット（uploaded_slots）のみ処理する。"""
        self.log("=== ピタクラ: テキスト入力開始 ===")

        for slot_idx, photo in assignments:
            if not photo.text:
                continue
            if slot_idx not in uploaded_slots:
                continue
            try:
                slot = self._get_slot(slot_idx)
                inp = slot.locator("span.textbox-wrap.col-36.ignore-handle input[type='text']")
                inp.fill(photo.text, timeout=3000)
                time.sleep(0.3)
            except Exception as e:
                self.log(f"  ✗ テキストエラー（スロット{slot_idx + 1}）: {e}")

        self.log("=== ピタクラ: テキスト入力完了 ===")

    # ==============================
    # ⑥ 保存
    # ==============================

    def _click_save(self) -> bool:
        """登録ボタン（button.button-register）をクリック → 確認ダイアログの「いいえ」を押す"""
        try:
            btn = self._page.locator("button.button-register").first
            btn.click(timeout=5000)
            self.log("  ✓ 登録ボタンをクリックしました")
        except Exception as e:
            self.log(f"  ✗ 保存ボタンクリックエラー: {e}")
            return False

        # 確認ダイアログが出たら「いいえ」（el-button--primary）をクリック
        try:
            confirm_btn = self._page.locator(
                ".el-message-box__btns button.el-button--primary"
            ).first
            confirm_btn.wait_for(state="visible", timeout=5000)
            confirm_btn.click(timeout=5000)
            self.log("  ✓ 確認ダイアログを承認しました")
        except Exception as e:
            self.log(f"  △ 確認ダイアログが見つかりませんでした（スキップ）: {e}")

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
