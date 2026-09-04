"""
配布パッケージのビルド（開発者専用スクリプト）

このスクリプトを実行すると dist/ に「配布先PCにPythonが一切無くても動く」
完全同梱フォルダと zip が出来上がる。

仕組み:
  1. python.org から埋め込み版Python（embeddable）をDLして dist に展開
  2. 埋め込み版には tkinter が含まれていないので、
     このスクリプトを実行しているPythonのインストール先から tkinter 一式を移植
  3. pip を入れて requirements.txt のライブラリをインストール
  4. アプリ本体（.py と bat）をコピー
  5. zip に固める

つまり「ネットからのDLはビルド時に済ませておく」方式。
配布先ではネット接続・Pythonインストール・管理者権限のいずれも不要になる。

使い方:
    python build_haifu.py               # 通常ビルド（python/ は再利用して高速）
    python build_haifu.py --clean        # python/ を作り直す
    python build_haifu.py --no-zip       # zip を作らずフォルダだけ
    python build_haifu.py --with-photos  # 物件写真/ も同梱する（サイズ注意）

同梱されるもの:
    アプリ本体 + 同梱Python + はじめにお読みください.txt
    urls.txt                  … あれば（SUUMOトークン入り。受け取った人の設定が不要になる）
    社有入力テンプレート.xlsx   … あれば（アプリにテンプレート作成ボタンが無いので実質必須）
    物件写真/                  … --with-photos を付けたときだけ
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

# 文字化け対策（cp932コンソールで日本語を出しても落ちないようにする）
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --- パスは常にスクリプト位置起点で解決する（カレントディレクトリに依存しない） ---
ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
CACHE = ROOT / ".build_cache"

PACKAGE_NAME = "社有物件自動入力Bot"

# main.py の EXCEL_FILENAME / PARENT_PHOTO_DIR と揃えること
EXCEL_FILENAME = "社有入力テンプレート.xlsx"
PHOTO_DIRNAME = "物件写真"

GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# ランタイムの検証コード。
# `import tkinter` だけでは不十分。tkinter は純Pythonモジュールなので、
# tcl/ ディレクトリ（Tcl/Tkのスクリプト群）が欠けていても import は成功し、
# 実際にウィンドウを作る段階で初めて落ちる。壊れたzipを「OK」と表示しないよう、
# 必ず Tk() を生成するところまで確認する。
TK_CHECK = (
    "import tkinter, tkinter.ttk, tkinter.filedialog; "
    "r = tkinter.Tk(); r.withdraw(); "
    "print('tk', r.tk.call('info', 'patchlevel')); r.destroy()"
)
FULL_CHECK = "import openpyxl, playwright.sync_api; " + TK_CHECK

# 同梱ランタイムに入れたライブラリの素性を記録するファイル。
# requirements.txt を変えたのに python/ を使い回して古いまま配る事故を防ぐ。
STAMP_NAME = ".requirements.sha256"

# 配布フォルダに入れるアプリ本体。ここに書いたものだけが配布される。
APP_FILES = [
    "main.py",
    "excel_reader.py",
    "make_template.py",
    "add_chuko_sheets.py",
    "1.最初にダブルクリック(ブラウザが開く).bat",
    "2.次にダブルクリック(自動入力アプリが起動する).bat",
    "urls.example.txt",
    "はじめにお読みください.txt",
]
APP_DIRS = ["automation"]


def log(msg: str) -> None:
    print(msg, flush=True)


def die(msg: str) -> None:
    log("")
    log("=" * 60)
    log(f"  ビルド中止: {msg}")
    log("=" * 60)
    sys.exit(1)


# ============================================================
# ホスト側（このPC）の前提チェック
# ============================================================
def check_host() -> Path:
    """tkinter の移植元になるPythonインストール先を返す"""
    try:
        import tkinter  # noqa: F401
    except ImportError:
        die(
            "このPythonには tkinter がありません。\n"
            "  python.org の公式インストーラ版Python（tcl/tkを含むもの）で実行してください。\n"
            f"  現在のPython: {sys.executable}"
        )

    base = Path(sys.base_prefix)
    missing = [str(p) for p in (base / "DLLs" / "_tkinter.pyd", base / "tcl", base / "Lib" / "tkinter") if not p.exists()]
    if missing:
        die("tkinter の移植元ファイルが見つかりません:\n  " + "\n  ".join(missing))

    log(f"[準備] 移植元Python: {base}")
    log(f"[準備] バージョン  : {sys.version.split()[0]}")
    return base


def embed_zip_url() -> tuple[str, str]:
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    name = f"python-{ver}-embed-amd64.zip"
    return f"https://www.python.org/ftp/python/{ver}/{name}", name


# ============================================================
# ダウンロード（キャッシュ付き）
# ============================================================
def download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        log(f"[DL ] キャッシュ利用: {dest.name}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"[DL ] {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:
        tmp.unlink(missing_ok=True)
        die(
            f"ダウンロードに失敗しました: {url}\n"
            f"  原因: {e}\n"
            "  社内プロキシ / ファイアウォール / アンチウイルスを確認してください。"
        )
    tmp.replace(dest)
    log(f"[DL ] 完了: {dest.name} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
    return dest


# ============================================================
# 同梱Pythonランタイムの構築
# ============================================================
def build_runtime(host_base: Path, work: Path) -> None:
    """work（短いパスの作業ディレクトリ）に、tkinter入りの動くPythonを組み立てる"""
    url, zip_name = embed_zip_url()
    zip_path = download(url, CACHE / zip_name)

    log("[1/4] 埋め込み版Pythonを展開")
    work.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(work)

    # ---- ._pth を書き換える ----
    # ・#import site → import site  : site-packages を有効化（pip で入れた物を読むため）
    # ・Lib を追加                  : 移植した Lib/tkinter を読ませるため
    pth_files = list(work.glob("python*._pth"))
    if not pth_files:
        die("python*._pth が見つかりません（zipの中身が想定と違います）")
    for pth in pth_files:
        lines = pth.read_text(encoding="utf-8").splitlines()
        lines = [("import site" if ln.strip() == "#import site" else ln) for ln in lines]
        if "Lib" not in [ln.strip() for ln in lines]:
            lines.append("Lib")
        if "import site" not in [ln.strip() for ln in lines]:
            lines.append("import site")
        pth.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"[1/4] {pth_files[0].name} を書き換え（import site 有効化 + Lib 追加）")

    # ---- tkinter 一式を移植 ----
    # 埋め込み版zipには _tkinter.pyd / tcl / tk が入っていないため、
    # 同じバージョンの通常インストールから必要ファイルだけコピーする。
    # zlib1.dll を忘れると tcl86t.dll がロードできず
    # 「ImportError: DLL load failed while importing _tkinter」になるので注意。
    log("[2/4] tkinter を移植")
    dlls = host_base / "DLLs"
    copied = []
    for pattern in ("_tkinter.pyd", "tcl*.dll", "tk*.dll", "zlib1.dll"):
        for src in sorted(dlls.glob(pattern)):
            shutil.copy2(src, work / src.name)
            copied.append(src.name)
    if "_tkinter.pyd" not in copied:
        die(f"_tkinter.pyd が {dlls} にありません")
    log(f"       DLL: {', '.join(copied)}")

    for src, dst in ((host_base / "tcl", work / "tcl"), (host_base / "Lib" / "tkinter", work / "Lib" / "tkinter")):
        if dst.exists():
            shutil.rmtree(dst)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst)
        log(f"       {src.name}/ → {dst.relative_to(work)}/")

    verify(work, TK_CHECK, "tkinter の移植")

    # ---- pip とライブラリ ----
    log("[3/4] pip をインストール")
    get_pip = download(GET_PIP_URL, CACHE / "get-pip.py")
    run_py(work, [str(get_pip), "--no-warn-script-location"], "pip のインストール")

    log("[4/4] ライブラリをインストール（requirements.txt）")
    install_requirements(work)

    verify(work, FULL_CHECK, "同梱ランタイムの動作確認")


def requirements_hash() -> str:
    req = ROOT / "requirements.txt"
    if not req.exists():
        die("requirements.txt がありません")
    return hashlib.sha256(req.read_bytes()).hexdigest()


def install_requirements(runtime: Path) -> None:
    req = ROOT / "requirements.txt"
    run_py(runtime, ["-m", "pip", "install", "--no-warn-script-location", "-r", str(req)],
           "ライブラリのインストール")
    (runtime / STAMP_NAME).write_text(requirements_hash(), encoding="ascii")


def run_py(work: Path, args: list, what: str) -> None:
    r = subprocess.run([str(work / "python.exe")] + args, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        tail = "\n".join((r.stdout + r.stderr).splitlines()[-15:])
        die(f"{what} に失敗しました。\n\n{tail}")


def verify(work: Path, code: str, what: str) -> None:
    r = subprocess.run(
        [str(work / "python.exe"), "-c", code], capture_output=True, text=True, errors="replace"
    )
    if r.returncode != 0:
        tail = "\n".join((r.stdout + r.stderr).splitlines()[-10:])
        die(f"{what} に失敗しました。\n\n{tail}")
    log(f"       OK: {code}")


# ============================================================
# アプリ本体のコピー
# ============================================================
def clean_package(pkg: Path) -> None:
    """python/ 以外を消してから作り直す。

    上書きコピーだけで済ませると、前回ビルドの残骸がそのまま zip に入る。
    --with-photos で一度ビルドすると次回以降も写真が残り続ける、
    消したはずの実データが混入する、といった事故になるため毎回掃除する。
    """
    if not pkg.exists():
        return
    removed = []
    for p in pkg.iterdir():
        if p.name == "python":
            continue  # 同梱ランタイムは高価なので残す
        removed.append(p.name)
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    if removed:
        log(f"[app] 前回の成果物を削除: {', '.join(sorted(removed))}")


def copy_app(pkg: Path) -> None:
    log("[app] アプリ本体をコピー")
    for name in APP_FILES:
        src = ROOT / name
        if not src.exists():
            die(f"配布対象のファイルがありません: {name}")
        shutil.copy2(src, pkg / name)
    for name in APP_DIRS:
        src = ROOT / name
        if not src.exists():
            die(f"配布対象のフォルダがありません: {name}/")
        dst = pkg / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    log(f"       {len(APP_FILES)} ファイル + {len(APP_DIRS)} フォルダ")

    # urls.txt（SUUMOトークンを含む）は、あれば実ファイルを同梱する。
    # 無ければ example のまま配って受け取った人に入力してもらう。
    for cand in (ROOT / "urls.txt", ROOT / "config" / "urls.txt"):
        if cand.exists():
            shutil.copy2(cand, pkg / "urls.txt")
            log(f"       urls.txt を同梱（{cand.relative_to(ROOT)}）→ 受け取った人は設定不要")
            break
    else:
        log("       [!] urls.txt なし → 受け取った人がSUUMOトークンを手入力する必要あり")


def copy_extras(pkg: Path, with_photos: bool) -> None:
    """入力データ（Excel・写真）の同梱。無くてもビルドは通すが警告を出す。"""
    excel = ROOT / EXCEL_FILENAME
    if excel.exists():
        shutil.copy2(excel, pkg / EXCEL_FILENAME)
        log(f"[data] {EXCEL_FILENAME} を同梱（{excel.stat().st_size / 1024:.0f} KB）")
    else:
        # アプリ内にテンプレート作成ボタンが無いため、これが無いと
        # 受け取った人は入力データを用意できない。
        log(f"[data] [!] {EXCEL_FILENAME} がありません。")
        log("            受け取った人は入力データを用意できません。")
        log("            リポジトリ直下に置いてから再ビルドしてください。")

    photos = ROOT / PHOTO_DIRNAME
    if not photos.exists():
        return
    size_mb = sum(p.stat().st_size for p in photos.rglob("*") if p.is_file()) / 1024 / 1024
    if with_photos:
        dst = pkg / PHOTO_DIRNAME
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(photos, dst)
        log(f"[data] {PHOTO_DIRNAME}/ を同梱（{size_mb:.1f} MB）")
    else:
        log(f"[data] {PHOTO_DIRNAME}/ は同梱しません（{size_mb:.1f} MB）。含めるなら --with-photos")


# ============================================================
# main
# ============================================================
def main() -> None:
    clean = "--clean" in sys.argv
    make_zip = "--no-zip" not in sys.argv
    with_photos = "--with-photos" in sys.argv

    log("=" * 60)
    log(f"  {PACKAGE_NAME} 配布パッケージ ビルド")
    log("=" * 60)

    host_base = check_host()
    pkg = DIST / PACKAGE_NAME
    runtime = pkg / "python"

    if clean and runtime.exists():
        log("[準備] --clean: 既存の python/ を削除")
        shutil.rmtree(runtime)

    if runtime.exists():
        log("[準備] python/ は既存のものを再利用（作り直すには --clean）")
        # requirements.txt を編集したのに古いライブラリのまま配ってしまう事故を防ぐ。
        stamp = runtime / STAMP_NAME
        current = stamp.read_text(encoding="ascii").strip() if stamp.exists() else ""
        if current != requirements_hash():
            log("[準備] requirements.txt が変わっています → ライブラリを入れ直します")
            install_requirements(runtime)
        verify(runtime, FULL_CHECK, "既存ランタイムの確認")
    else:
        # ランタイムはいったん短いパスで組み立てる。
        # dist が深い階層にあると pip が Windows のパス長制限(260文字)に当たって
        # OSError で失敗するため、TEMP で作ってから移動する。
        with tempfile.TemporaryDirectory(prefix="shbot_") as td:
            work = Path(td) / "py"
            build_runtime(host_base, work)
            log("[移動] ランタイムを dist へ移動")
            runtime.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(work), str(runtime))

    clean_package(pkg)
    copy_app(pkg)
    copy_extras(pkg, with_photos)

    if make_zip:
        log("[zip] 圧縮中...")
        zip_path = DIST / f"{PACKAGE_NAME}.zip"
        zip_path.unlink(missing_ok=True)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            for p in sorted(pkg.rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    z.write(p, Path(PACKAGE_NAME) / p.relative_to(pkg))
        size = zip_path.stat().st_size / 1024 / 1024
        log(f"[zip] 完了: {zip_path.name} ({size:.1f} MB)")

    log("")
    log("=" * 60)
    log("  ビルド完了")
    log("=" * 60)
    log(f"  フォルダ: {pkg}")
    if make_zip:
        log(f"  配布zip : {DIST / (PACKAGE_NAME + '.zip')}")
    log("")
    log("  受け取った人の手順:")
    log("    1. zip を展開（Dropbox / OneDrive の中は避ける）")
    log("    2. 「1.最初にダブルクリック(ブラウザが開く).bat」")
    log("    3. 「2.次にダブルクリック(自動入力アプリが起動する).bat」")
    log("  ネット接続・Pythonインストール・管理者権限はいずれも不要")
    log("")


if __name__ == "__main__":
    main()
