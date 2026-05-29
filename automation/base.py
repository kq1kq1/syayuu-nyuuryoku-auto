"""
自動化の基底クラス
全サイト共通のChrome接続・操作メソッドを提供する
"""
import time
from typing import Optional, Callable
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext


CDP_PORT = 9222  # start_chrome.batで起動するデバッグポート


class AutomationBase:
    """ブラウザ自動化の基底クラス"""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        self.log_callback = log_callback or print
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    def log(self, msg: str):
        self.log_callback(msg)

    def connect(self) -> bool:
        """既存のChromeブラウザにCDP接続する"""
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.connect_over_cdp(
                f"http://localhost:{CDP_PORT}"
            )
            contexts = self._browser.contexts
            if not contexts:
                self.log("エラー: Chromeでページが開かれていません")
                return False

            # 現在アクティブなタブを取得
            self._page = contexts[0].pages[0] if contexts[0].pages else None
            if not self._page:
                self.log("エラー: タブが見つかりません")
                return False

            self.log(f"Chrome接続成功: {self._page.url}")
            return True

        except Exception as e:
            self.log(f"Chrome接続エラー: {e}")
            self.log("→ start_chrome.bat でChromeを起動してください")
            return False

    def get_current_url(self) -> str:
        if self._page:
            return self._page.url
        return ""

    def disconnect(self):
        try:
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

    # ---- 共通操作メソッド ----

    def fill_text(self, selector: str, value: str, clear: bool = True, timeout: int = 5000):
        """テキストフィールドに入力"""
        try:
            el = self._page.wait_for_selector(selector, timeout=timeout)
            if clear:
                el.triple_click()
                el.fill("")
            el.fill(value)
            return True
        except Exception as e:
            self.log(f"入力エラー [{selector}]: {e}")
            return False

    def select_option(self, selector: str, value: str, timeout: int = 5000):
        """セレクトボックスを選択"""
        try:
            self._page.wait_for_selector(selector, timeout=timeout)
            self._page.select_option(selector, value=value)
            return True
        except Exception as e:
            self.log(f"選択エラー [{selector}]: {e}")
            return False

    def click(self, selector: str, timeout: int = 5000):
        """要素をクリック"""
        try:
            el = self._page.wait_for_selector(selector, timeout=timeout)
            el.click()
            return True
        except Exception as e:
            self.log(f"クリックエラー [{selector}]: {e}")
            return False

    def upload_file(self, selector: str, filepath: str, timeout: int = 5000):
        """ファイルアップロード（input[type=file]）"""
        try:
            import os
            if not os.path.exists(filepath):
                self.log(f"ファイルが見つかりません: {filepath}")
                return False
            el = self._page.wait_for_selector(selector, timeout=timeout)
            el.set_input_files(filepath)
            return True
        except Exception as e:
            self.log(f"アップロードエラー [{selector}]: {e}")
            return False

    def upload_file_with_dialog(self, trigger_selector: str, filepath: str, timeout: int = 10000):
        """ボタンクリックでファイルダイアログが開くタイプのアップロード"""
        try:
            import os
            if not os.path.exists(filepath):
                self.log(f"ファイルが見つかりません: {filepath}")
                return False
            with self._page.expect_file_chooser(timeout=timeout) as fc_info:
                self.click(trigger_selector)
            file_chooser = fc_info.value
            file_chooser.set_files(filepath)
            return True
        except Exception as e:
            self.log(f"ダイアログアップロードエラー [{trigger_selector}]: {e}")
            return False

    def wait(self, seconds: float = 1.0):
        time.sleep(seconds)

    def wait_for_url_change(self, old_url: str, timeout: int = 10):
        """URLが変わるまで待機"""
        for _ in range(timeout * 10):
            if self._page.url != old_url:
                return True
            time.sleep(0.1)
        return False

    def get_all_pages(self) -> list[Page]:
        """全タブのリストを返す"""
        pages = []
        for ctx in self._browser.contexts:
            pages.extend(ctx.pages)
        return pages

    def switch_to_page_by_url(self, url_fragment: str) -> bool:
        """URLの一部で一致するタブに切り替える（最初の1件）"""
        for page in self.get_all_pages():
            if url_fragment in page.url:
                self._page = page
                self._page.bring_to_front()
                return True
        return False

    def get_pages_by_url(self, url_fragment: str) -> list:
        """URLの一部で一致する全タブをリストで返す"""
        return [p for p in self.get_all_pages() if url_fragment in p.url]

    def detect_site(self) -> str:
        """
        現在のURLからサイトを判定して返す
        戻り値: "suumo" | "homes" | "athome" | "unknown"
        """
        url = self.get_current_url().lower()
        if "suumo" in url or "recruit-sumai" in url:
            return "suumo"
        elif "homes.co.jp" in url or "lifeull" in url:
            return "homes"
        elif "athome" in url:
            return "athome"
        else:
            return "unknown"
