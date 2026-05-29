"""
Excel読み込みモジュール
サイト設定・写真情報をExcelから読み込む
"""
import os
from dataclasses import dataclass, field
import openpyxl


@dataclass
class SiteConfig:
    """サイト設定（Excelの基本情報・支払い例シートから読み込む）"""
    # 基本情報シート
    tantosha_name: str = ""          # 担当者名
    link_names: list = field(default_factory=list)   # リンク表示名称1〜5
    link_urls:  list = field(default_factory=list)   # リンク先URL1〜5

    # 支払い例シート（入力項目）
    kinri: float = 0.725             # 変動金利（年利 %）
    kikan: int   = 40                # 返済期間（年）

    # 支払い例シート（固定テキスト）
    shri_bkn_joho: str = "【物件金額100%のお借入の場合】"
    shri_loan:     str = ""          # 住宅ローンのご案内
    loan_annai:    str = ""          # フラット35ローンご案内


@dataclass
class PhotoEntry:
    """写真1枚分のデータ"""
    slot:     str = ""   # スロット番号（順番）
    filename: str = ""   # ファイル名
    caption:  str = ""   # キャプション
    text:     str = ""   # 文言


def read_site_config(filepath: str) -> SiteConfig:
    """
    Excelファイルからサイト設定を読み込む

    読み込むシート:
    - 「基本情報」: キー・バリュー形式 (A列=フィールド名, B列=値)
    - 「支払い例」: B2=物件価格, B3=金利, B4=返済期間, B14=住宅ローン文言, B15=フラット35文言
    """
    wb = openpyxl.load_workbook(filepath)
    config = SiteConfig()

    # ---- 基本情報シート ----
    if "基本情報" in wb.sheetnames:
        ws = wb["基本情報"]
        data = {}
        for row in ws.iter_rows(min_row=2, values_only=True):
            key = str(row[0]).strip() if row[0] else ""
            val = str(row[1]).strip() if row[1] is not None else ""
            if key and key != "None":
                data[key] = val

        config.tantosha_name = data.get("担当者名", "")
        for i in range(1, 6):
            config.link_names.append(data.get(f"リンク表示名称{i}", ""))
            config.link_urls.append(data.get(f"リンク先URL{i}", ""))

    # ---- 支払い例シート ----
    if "支払い例" in wb.sheetnames:
        ws = wb["支払い例"]

        def cell_val(row, col):
            v = ws.cell(row, col).value
            return v if v is not None else ""

        # 入力項目（B3=金利, B4=返済期間）※B2は物件価格なので読まない
        try:
            kinri = float(cell_val(3, 2))
            config.kinri = kinri
        except (ValueError, TypeError):
            pass

        try:
            kikan = int(cell_val(4, 2))
            config.kikan = kikan
        except (ValueError, TypeError):
            pass

        # 固定テキスト（B10=物件情報, B14=住宅ローン, B15=フラット35）
        v10 = str(cell_val(10, 2))
        if v10 and v10 != "None":
            config.shri_bkn_joho = v10

        v14 = str(cell_val(14, 2))
        if v14 and v14 != "None":
            config.shri_loan = v14

        v15 = str(cell_val(15, 2))
        if v15 and v15 != "None":
            config.loan_annai = v15

    return config


def read_photos(filepath: str, sheet_name: str = "写真") -> list:
    """
    指定シートから写真データを読み込む（デフォルト: 「写真」シート）

    列構成: 順番 | ファイル名 | キャプション | 文言 | スーモスロット参考
    """
    wb = openpyxl.load_workbook(filepath)
    photos = []

    if sheet_name not in wb.sheetnames:
        return photos

    ws = wb[sheet_name]
    for row in ws.iter_rows(min_row=2, values_only=True):
        slot     = str(row[0]).strip() if row[0] is not None else ""
        filename = str(row[1]).strip() if row[1] is not None else ""
        caption  = str(row[2]).strip() if row[2] is not None else ""
        text     = str(row[3]).strip() if row[3] is not None else ""

        if filename == "None":
            filename = ""

        # ファイル名・キャプション・文言のうち1つでもあれば対象（テキストのみ行も含む）
        if not filename and not caption and not text:
            continue

        photos.append(PhotoEntry(
            slot=slot,
            filename=filename,
            caption=caption,
            text=text,
        ))

    return photos


@dataclass
class LayoutRow:
    """レイアウト指定1行分のデータ"""
    pattern: str = "A"   # パターン（A〜F）
    title:   str = ""    # タイトル


def read_layout(filepath: str) -> list:
    """
    「レイアウト指定」シートからパターン・タイトルのリストを読み込む。
    列構成: 段目 | パターン | タイトル
    """
    wb = openpyxl.load_workbook(filepath)
    rows = []
    if "レイアウト指定" not in wb.sheetnames:
        return rows
    ws = wb["レイアウト指定"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        pattern = str(row[1]).strip() if row[1] is not None else "A"
        title   = str(row[2]).strip() if row[2] is not None else ""
        if pattern == "None":
            pattern = "A"
        if title == "None":
            title = ""
        if not pattern and not title:
            continue
        rows.append(LayoutRow(pattern=pattern, title=title))
    return rows
