"""
既存の社有入力テンプレート.xlsx に土地用のキャプション列を追加するスクリプト。
既存のデータ・書式は一切変更しない。すでに列がある場合はスキップする。

追加先（土地は新築と同じシートを使うため、新築側のシートだけが対象）:
  写真          : キャプション（土地）列
  売主コメント  : キャプション（土地）列
  ピタクラ      : キャプション（土地）列
  支払い例      : D列「土地の場合」＋ E列に説明書き

列は「一番右の空き列」に足す。途中に挿入すると openpyxl では
列幅・セル書式・結合セルが正しく追随せず、手で編集済みのファイルを壊す恐れがあるため。
アプリ側は列の位置ではなく見出し名で読むので、
Excel上で列をドラッグしてキャプションの隣に移動しても問題なく動く。

使い方:
    python add_tochi_columns.py "社有入力テンプレート.xlsx"
"""
import shutil
import sys
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

NAVY = '1A5276'
WHITE = 'FFFFFF'
BLUE = 'E3F2FD'

# 支払い例シートは見出し行が無くセル位置で読むので、列を固定で決める。
# excel_reader.PAYMENT_VARIANT_COLUMN と揃えること。
PAYMENT_SHEET = '支払い例'
PAYMENT_VARIANT_COL = 4   # D列（土地の場合の値）
PAYMENT_NOTE_COL = 5      # E列（説明書き）
PAYMENT_ROWS = [
    (3,  '← 土地で金利が違う場合だけ記入'),
    (4,  '← 土地で返済期間が違う場合だけ記入'),
    (10, '← 土地用の物件(住戸)情報'),
    (14, '← 土地用の住宅ローンのご案内'),
    (15, '← 土地用のフラット35ローンご案内'),
]

# 対象シートと、追加する列の見出し
TARGETS = {
    '写真':         ['キャプション（土地）'],
    '売主コメント': ['キャプション（土地）'],
    'ピタクラ':     ['キャプション（土地）'],
}


def _header_names(ws) -> list:
    row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
    return [(str(v).strip() if v is not None else '') for v in row]


def _style_header(cell, text, model=None):
    cell.value = text
    if model is not None and model.font is not None and model.font.bold:
        # 既存の見出しと同じ見た目に揃える
        cell.font = Font(name=model.font.name, bold=True,
                         color=model.font.color.rgb if model.font.color else WHITE,
                         size=model.font.size)
        cell.fill = PatternFill('solid', fgColor=NAVY)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    else:
        cell.font = Font(name='Arial', bold=True, color=WHITE, size=10)
        cell.fill = PatternFill('solid', fgColor=NAVY)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)


def _add_payment_column(ws) -> bool:
    """支払い例シートに「土地の場合」列（D）と説明（E）を用意する。

    D列には値を書かない。ヒント文を入れてしまうと、それが
    そのまま入力値として読まれてしまうため。説明はE列にグレーで置く。
    """
    if _header_names(ws)[PAYMENT_VARIANT_COL - 1:PAYMENT_VARIANT_COL]:
        if ws.cell(1, PAYMENT_VARIANT_COL).value:
            return False  # 冪等：すでにある

    _style_header(ws.cell(1, PAYMENT_VARIANT_COL), '土地の場合（空欄なら左と同じ）')
    for row, note in PAYMENT_ROWS:
        c = ws.cell(row, PAYMENT_VARIANT_COL)
        c.font = Font(name='Arial', size=10)
        c.fill = PatternFill('solid', fgColor=BLUE)
        c.alignment = Alignment(vertical='top', wrap_text=True)
        n = ws.cell(row, PAYMENT_NOTE_COL)
        if not n.value:
            n.value = note
            n.font = Font(name='Arial', size=9, color='888888')
            n.alignment = Alignment(vertical='top')
    ws.column_dimensions[get_column_letter(PAYMENT_VARIANT_COL)].width = 52
    ws.column_dimensions[get_column_letter(PAYMENT_NOTE_COL)].width = 30
    return True


def add_tochi_columns(path: str, backup: bool = True) -> dict:
    """土地用の列を追加する。追加した内容を {シート名: [列名, ...]} で返す。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {p}")

    wb = openpyxl.load_workbook(p)
    added = {}

    for sheet_name, columns in TARGETS.items():
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        headers = _header_names(ws)

        # 見出しの書式を既存のキャプション列から借りる
        model = None
        if 'キャプション' in headers:
            model = ws.cell(1, headers.index('キャプション') + 1)

        for col_name in columns:
            if col_name in headers:
                continue  # 冪等：すでにある
            idx = len(headers) + 1
            _style_header(ws.cell(1, idx), col_name, model)
            ws.column_dimensions[get_column_letter(idx)].width = 26
            headers.append(col_name)
            added.setdefault(sheet_name, []).append(col_name)

    if PAYMENT_SHEET in wb.sheetnames:
        if _add_payment_column(wb[PAYMENT_SHEET]):
            added.setdefault(PAYMENT_SHEET, []).append('D列「土地の場合」')

    if not added:
        return added

    if backup:
        bak = p.with_name(p.stem + '_backup' + p.suffix)
        shutil.copy2(p, bak)
        print(f"バックアップ: {bak.name}")

    wb.save(p)
    return added


if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else '社有入力テンプレート.xlsx'
    print(f"対象ファイル: {target}")
    result = add_tochi_columns(target)
    if result:
        for sheet, cols in result.items():
            print(f"  追加: {sheet} → {', '.join(cols)}")
        print("完了")
        print()
        print("Excelで開いて、土地のときだけ差し替えたい行に")
        print("「キャプション（土地）」を記入してください。")
        print("空欄の行は通常の「キャプション」がそのまま使われます。")
    else:
        print("追加する列はありませんでした（すべて既存）")
