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

    # 読み込み状況（種別専用列の書き忘れ検知用）
    payment_variant_available: bool = False       # D列（土地の場合）が用意されているか
    payment_variant_rows: list = field(default_factory=list)  # 実際にD列を使った行番号


@dataclass
class PhotoEntry:
    """写真1枚分のデータ"""
    slot:     str = ""   # スロット番号（順番）
    filename: str = ""   # ファイル名
    caption:  str = ""   # キャプション
    text:     str = ""   # 文言


# 「支払い例」シートで種別ごとの値を書く列。
# B列（通常）の右、C列（メモ書き）のさらに右に置く。
PAYMENT_VARIANT_COLUMN = 4   # D列
PAYMENT_BASE_COLUMN = 2      # B列


def read_site_config(filepath: str, variant: str = "") -> SiteConfig:
    """
    Excelファイルからサイト設定を読み込む

    読み込むシート:
    - 「基本情報」: キー・バリュー形式 (A列=フィールド名, B列=値)
    - 「支払い例」: B2=物件価格, B3=金利, B4=返済期間, B14=住宅ローン文言, B15=フラット35文言

    variant に "土地" を渡すと、支払い例シートのD列（土地の場合）を優先して読む。
    D列が空欄の行はB列にフォールバックする（差分のある行だけ書けば済むようにするため）。
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

        def cell_val(row):
            """種別専用列（D）を優先し、空欄ならB列を使う"""
            if variant:
                v = ws.cell(row, PAYMENT_VARIANT_COLUMN).value
                if _cell(v):
                    config.payment_variant_rows.append(row)
                    return v
            v = ws.cell(row, PAYMENT_BASE_COLUMN).value
            return v if v is not None else ""

        # 入力項目（B3=金利, B4=返済期間）※B2は物件価格なので読まない
        try:
            kinri = float(cell_val(3))
            config.kinri = kinri
        except (ValueError, TypeError):
            pass

        try:
            kikan = int(cell_val(4))
            config.kikan = kikan
        except (ValueError, TypeError):
            pass

        # 固定テキスト（B10=物件情報, B14=住宅ローン, B15=フラット35）
        v10 = str(cell_val(10))
        if v10 and v10 != "None":
            config.shri_bkn_joho = v10

        v14 = str(cell_val(14))
        if v14 and v14 != "None":
            config.shri_loan = v14

        v15 = str(cell_val(15))
        if v15 and v15 != "None":
            config.loan_annai = v15

        config.payment_variant_available = (
            ws.max_column >= PAYMENT_VARIANT_COLUMN
            and any(_cell(ws.cell(r, PAYMENT_VARIANT_COLUMN).value)
                    for r in (1, 3, 4, 10, 14, 15))
        )

    return config


# 各項目に対応する見出し名。シートによって表記が違うので候補を並べる。
# （ホームズのシートだけ文言列が「コメント（文言）」になっている）
COLUMN_ALIASES = {
    "slot":     ("順番",),
    "filename": ("ファイル名",),
    "caption":  ("キャプション",),
    "text":     ("文言", "コメント（文言）"),
}

# 見出しが読めなかった古いシート用の並び順（従来の固定位置）
LEGACY_ORDER = ("slot", "filename", "caption", "text")


def _cell(value) -> str:
    """セルの値を文字列にする。None や 'None' は空文字に潰す。"""
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s == "None" else s


def _resolve_columns(ws, variant: str = ""):
    """見出し行から「項目名 → 列インデックス」の対応を作る。

    variant（例: "土地"）を渡すと、「キャプション（土地）」のような
    種別専用の列も探して override として返す。
    列を挿したり並べ替えたりしても壊れないように、位置ではなく名前で引く。
    """
    header = {}
    for idx, cell in enumerate(next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())):
        name = _cell(cell)
        if name and name not in header:
            header[name] = idx

    base, override, names_found = {}, {}, {}
    for key, names in COLUMN_ALIASES.items():
        for name in names:
            if name in header:
                base[key] = header[name]
                if variant:
                    # 全角・半角どちらの括弧で書かれていても拾う
                    for alt in (f"{name}（{variant}）", f"{name}({variant})"):
                        if alt in header:
                            override[key] = header[alt]
                            names_found[key] = alt
                            break
                break
    return base, override, names_found


def read_photos(filepath: str, sheet_name: str = "写真", variant: str = "") -> list:
    """
    指定シートから写真データを読み込む（デフォルト: 「写真」シート）

    列構成: 順番 | ファイル名 | キャプション | 文言 | スーモスロット参考

    variant に "土地" などを渡すと「キャプション（土地）」のような
    種別専用の列を優先して読む。その列が空欄の行は通常の列にフォールバックする
    （差分のある行だけ書けば済むようにするため）。

    戻り値の list には fallback_count 属性が付く。
    種別専用の列が空欄で通常列を使った行数で、書き忘れの検知に使う。
    """
    wb = openpyxl.load_workbook(filepath)
    photos = PhotoList()

    if sheet_name not in wb.sheetnames:
        photos.missing_sheet = True
        return photos

    ws = wb[sheet_name]
    base, override, variant_names = _resolve_columns(ws, variant)
    photos.variant_columns = [variant_names[k] for k in sorted(variant_names)]

    # 見出しが読めない古いシートは従来どおり位置で読む
    if not base:
        base = {key: i for i, key in enumerate(LEGACY_ORDER)}
        override = {}
        photos.legacy_layout = True

    def pick(row, key):
        col = override.get(key)
        if col is not None and col < len(row):
            value = _cell(row[col])
            if value:
                return value, False
            return _pick_base(row, base, key), True  # 空欄 → 通常列へ
        return _pick_base(row, base, key), False

    for row in ws.iter_rows(min_row=2, values_only=True):
        slot, _         = pick(row, "slot")
        filename, _     = pick(row, "filename")
        caption, fb_cap = pick(row, "caption")
        text, fb_txt    = pick(row, "text")

        # ファイル名・キャプション・文言のうち1つでもあれば対象（テキストのみ行も含む）
        if not filename and not caption and not text:
            continue

        if fb_cap or fb_txt:
            photos.fallback_count += 1

        photos.append(PhotoEntry(
            slot=slot,
            filename=filename,
            caption=caption,
            text=text,
        ))

    return photos


def _pick_base(row, base, key) -> str:
    col = base.get(key)
    if col is None or col >= len(row):
        return ""
    return _cell(row[col])


class PhotoList(list):
    """read_photos の戻り値。読み込み時の状況を属性で持ち回る。"""

    def __init__(self, *args):
        super().__init__(*args)
        self.fallback_count = 0    # 種別専用列が空欄で通常列を使った行数
        self.variant_columns = []  # 実際に見つかった種別専用列
        self.legacy_layout = False # 見出しが読めず位置で読んだか
        self.missing_sheet = False # シート自体が存在しなかったか


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
