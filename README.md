# 社有物件自動入力Bot

不動産ポータルサイトの管理画面へ、物件情報・写真・コメントを **自動入力** するツールです。
Excelに用意したデータをもとに、Playwright（Python）が起動済みのChromeを操作します。

対応サイト:

| サイト | 入力内容 |
|--------|---------|
| **SUUMO** | 基本情報 → 内外観・その他画像 → 支払い例 → レイアウト指定 |
| **ホームズ** | 物件編集 → 基本画像 → 外観・分譲地 → 内観 |
| **ピタクラ** | 建築確認番号 → 外観内観写真 → キャプション → 文言 |
| **自社サイト** | 担当者選択 → おすすめチェック → 建確番号 → 画像 → 文言 |

---

## 動作の仕組み

```
[Excel テンプレート] ──┐
[物件写真フォルダ]  ──┼─→ [main.py / GUI] ──→ Playwright ──CDP:9222──→ [Chrome]
                                                                          ↑
                                          ログイン済みプロファイルで各サイトを開いておく
```

- ツールは **自分でChromeを起動しません**。先に「デバッグポート9222付きのChrome」を立ち上げ、各サイトにログインしておく必要があります。
- ツールはその起動済みChromeに**接続して**操作します（`automation/base.py` の `connect_over_cdp`）。

---

## 必要なもの（新しいマシンで使うとき）

### 1. Google Chrome
通常のChromeがインストールされていればOK。**Edgeでは動きません。**

`1.最初にダブルクリック(ブラウザが開く).bat` が以下の順に自動で探します。

1. `%ProgramFiles%\Google\Chrome\Application\chrome.exe`
2. `%ProgramFiles(x86)%\...`
3. `%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe`（ユーザー領域インストール）
4. レジストリ `App Paths`（HKLM → HKCU）

### 2. Python

| 方式 | 対象 | Pythonインストール |
|------|------|----------------|
| **A. 配布版（非エンジニア向け）** | 営業担当など | **不要**。zipに動くPythonが同梱されている |
| **B. ソース版（開発者・自分用）** | コードを触る人 | Python 3.13 を python.org からインストール |

起動batは「同梱の `python\pythonw.exe` → `pyw.exe`（pyランチャー）→ PATH上の `pythonw.exe`」の順に自動判別するので、**同じフォルダが配布先PCでも開発PCでもそのまま動きます。**

### 3. 各サイトへのログイン（初回のみ・全マシン共通）
ブラウザ起動batが専用プロファイル（`%LOCALAPPDATA%\syayuu_nyuuryoku_chrome`）でChromeを開きます。
**初回はそのChromeで各サイトに手動ログイン**してください。ログイン状態はプロファイルに保存され、次回以降は自動で維持されます（ID/PWの再入力不要）。

> ⚠️ 新しいマシンでは、このプロファイルが空なので **4サイトすべてに1回ずつ手動ログインが必要** です。

### 4. Excelテンプレートと写真
- `社有入力テンプレート.xlsx` … 入力データ。アプリの「Excelテンプレート作成」ボタンで生成できる。
- `物件写真/` … 写真フォルダ（`同仕様モデルハウス/`, `ホームズ写真/` など）。

### 5. 起動URL設定（urls.txt）
Chrome起動時に開くURL（SUUMOのトークン付きURLを含む）は、セキュリティのため
リポジトリには含めず `urls.txt` に分離しています（`.gitignore` 済み）。

起動batは `urls.txt` → `config\urls.txt` の順に探すので、どちらに置いてもOKです。
無い場合は `urls.example.txt` から自動コピーしてメモ帳を開くので、
`YOUR_SUUMO_TOKEN_HERE` を実トークンに書き換えて保存 → 再実行してください。

> 配布zipのビルド時に `urls.txt` が存在すれば同梱されるため、受け取った人の設定は不要になります。

---

## セットアップ手順

### A. 配布版（非エンジニア向け）

配布zipには **tkinter入りのPythonランタイムと必要ライブラリがすべて同梱**されています。
そのため受け取った人の側では、**インターネット接続・Pythonインストール・管理者権限のいずれも不要**です。
`【最初だけ】セットアップ.bat` は廃止しました。

> Dropbox / OneDrive の中は避けて、**デスクトップなどローカルフォルダ**に展開してください（同期がファイルをロックします）。

1. `社有物件自動入力Bot.zip` を **デスクトップ** に展開
2. `1.最初にダブルクリック(ブラウザが開く).bat`
3. `2.次にダブルクリック(自動入力アプリが起動する).bat`

同梱の `はじめにお読みください.txt` に、この手順とよくあるトラブルを日本語で書いてあります。

### B. ソース版（開発者・自分用）

```powershell
git clone https://github.com/kq1kq1/syayuu-nyuuryoku-auto.git
cd syayuu-nyuuryoku-auto
pip install -r requirements.txt

# 起動URLを設定（トークンはgit管理外なので手動で用意）
copy urls.example.txt urls.txt
notepad urls.txt   # YOUR_SUUMO_TOKEN_HERE を実トークンに書き換えて保存
```

あとは配布版と同じ2つのbatをダブルクリックするだけです（システムのPythonが自動で使われます）。

> Playwright本体のブラウザ（chromium）は **不要** です。既存のChromeにCDP接続するため。
> `playwright==1.44.0` は Python 3.13 用のwheelが無くインストールに失敗するため、`1.62.0` に上げてあります。
> `Pillow` はコード上で未使用だったため `requirements.txt` から外しました。

### C. 配布zipのビルド（開発者のみ）

```bash
python build_haifu.py
```

`dist/社有物件自動入力Bot.zip`（約53MB）が出来上がります。これを渡してください。

やっていること:

1. python.org から `python-3.13.4-embed-amd64.zip` をDL・展開（`.build_cache/` にキャッシュ）
2. **埋め込み版には tkinter が入っていない**ので、ローカルの Python 3.13.4 から移植
   `_tkinter.pyd` / `tcl86t.dll` / `tk86t.dll` / **`zlib1.dll`** / `tcl/` / `Lib/tkinter/`
3. `python313._pth` を書き換え（`import site` 有効化 + `Lib` 追加）
4. pip を入れて `requirements.txt` をインストール
5. アプリ本体と `urls.txt` をコピーして zip 化

```bash
python build_haifu.py --clean        # python/ を作り直す
python build_haifu.py --no-zip       # zipを作らずフォルダだけ
python build_haifu.py --with-photos  # 物件写真/ も同梱する（サイズ注意）
```

**入力データの同梱**（リポジトリ直下にあれば自動で入る）

| ファイル | 挙動 |
|---|---|
| `urls.txt` / `config/urls.txt` | あれば同梱 → 受け取った人のトークン設定が不要になる |
| `社有入力テンプレート.xlsx` | あれば同梱。**無いと警告が出る** |
| `物件写真/` | `--with-photos` を付けたときだけ同梱 |

> ⚠️ アプリの `_create_template()`（[main.py:663](main.py:663)）は **どのボタンにも配線されていません**。
> そのため受け取った人はアプリ内でテンプレートを作れません。
> **`社有入力テンプレート.xlsx` を必ず同梱してください。**
> （既存テンプレートを上書きする事故を避けるため、配線は意図的に見送っています）

> `zlib1.dll` を忘れると `ImportError: DLL load failed while importing _tkinter` になります。
> ランタイムはいったん `%TEMP%` で組み立ててから `dist/` へ移動します。深い階層で `pip install` すると
> Windowsのパス長制限（260文字）に当たって `OSError` で失敗するためです。
> ビルドにはネット接続が必要ですが、**配布先では不要**です。

---

## 使い方（全マシン共通）

1. **Chromeを起動**（デバッグポート9222 + 各サイトを自動で開く）
   - `1.最初にダブルクリック(ブラウザが開く).bat`
   - ⚠️ 初回はここで各サイトに手動ログイン
2. **入力したい物件の編集ページ** を、開いたChromeで表示する
3. **アプリを起動**
   - `2.次にダブルクリック(自動入力アプリが起動する).bat`
4. 起動時ダイアログで **建築確認番号** と **物件価格** を入力
5. **物件タイプ**（新築 / 中古）を選択
6. 写真フォルダを確認（中古は「参照...」で撮影写真フォルダを選び「連番リネーム」）
7. 入力したいサイトのボタンをクリック → 自動入力開始
8. **完了後、内容を目視確認してから手動で保存**

---

## Excel テンプレートのシート構成

| シート名 | 内容 |
|---------|------|
| 基本情報 | 担当者名・リンク表示名称1〜5・リンク先URL1〜5 |
| 写真 / 写真（中古） | 順番・ファイル名・キャプション・文言・スーモスロット参考 |
| 支払い例 | 物件価格(B2)・金利(B3)・返済期間(B4)・各種固定テキスト |
| 売主コメント / 〜（中古） | 順番・ファイル名・キャプション・文言 |
| レイアウト指定 | 段目・パターン(A〜F)・タイトル |
| ホームズ用 / ホームズ_外観分譲地 / ホームズ_内観 | ホームズ用画像（新築） |
| ホームズ_外観（中古）/ ホームズ_内観（中古） | ホームズ用画像（中古） |
| ピタクラ / ピタクラ（中古） | ピタクラ用 |
| スカイヤーズ / スカイヤーズ（中古） | スカイヤーズ用 |

> 金利・返済期間は「支払い例」シートで変更できます。物件価格はGUIで入力した値が自動で書き込まれます。

---

## ファイル構成

ソースの正は **リポジトリ直下だけ**です。配布フォルダは `build_haifu.py` が組み立てるので、
同じ `.py` を2箇所で管理する必要はありません。

```
syayuu_nyuuryoku_auto/
├── main.py                    # tkinter GUI + 実行エントリポイント
├── excel_reader.py            # Excelからデータ読み込み
├── make_template.py           # Excelテンプレート生成
├── add_chuko_sheets.py        # 中古シート追加
├── automation/
│   ├── base.py                # Chrome接続・共通操作の基底クラス
│   ├── suumo.py               # SUUMO自動入力
│   ├── homes.py               # ホームズ自動入力
│   ├── pitakura.py            # ピタクラ自動入力
│   └── skyyers.py             # 自社サイト自動入力
│
├── 1.最初にダブルクリック(ブラウザが開く).bat      # Chrome起動（純ASCII）
├── 2.次にダブルクリック(自動入力アプリが起動する).bat # アプリ起動（Python自動判別・純ASCII）
├── はじめにお読みください.txt                      # 配布先向けの日本語手順
├── urls.example.txt           # 起動URLのひな形
├── requirements.txt
├── build_haifu.py             # 配布zipのビルド（開発者専用）
│
├── 社有入力テンプレート.xlsx     # 入力データ（gitignore）
├── 物件写真/                   # 写真フォルダ群（gitignore）
├── urls.txt                   # 実URL・SUUMOトークン（gitignore）
├── config/                    # 開発メモ用セレクタJSON（コードからは未参照）
├── .build_cache/              # DL済みPython・get-pip のキャッシュ（gitignore）
└── dist/                      # ビルド成果物（gitignore）
    ├── 社有物件自動入力Bot/
    │   ├── python/            # tkinter込み同梱ランタイム
    │   └── （アプリ一式）
    └── 社有物件自動入力Bot.zip  # ← これを配布する
```

---

## トラブルシューティング

### 配布先PCで

| 症状 | 原因 | 対処 |
|------|------|------|
| `no Python runtime found` | zipの展開が不完全で `python/` が無い | zipをもう一度、フォルダごと展開する |
| `this Python runtime is missing required modules` | 同梱ランタイムのビルド不備 | 開発者が `python build_haifu.py --clean` で作り直して再配布 |
| `ERROR: Google Chrome was not found` | Chrome未インストール / Edgeのみ | Chromeをインストールする |
| Chromeは開くがサイトが出ない | `urls.txt` 未作成 | 「1.最初に...」実行で自動生成→メモ帳が開くのでトークン記入して再実行 |
| `Chrome接続エラー` / 接続失敗 | Chromeをポート9222で起動していない | 先に「1.最初に...」を実行。順番を守る |
| ログイン画面のまま入力されない | プロファイル未ログイン | 起動Chromeで各サイトに手動ログイン |
| Excel書き込みエラー | Excelを開いたまま | Excelを閉じてから再実行 |

> ダブルクリックしても無反応、という症状は起きません。
> `2.次にダブルクリック...bat` が `pythonw.exe`（コンソール無し）で起動する前に
> `import tkinter, openpyxl, playwright.sync_api` をコンソール側で先に検査し、
> 失敗したら原因を表示して `pause` で止まるようにしてあります。

### ビルド時（開発者PC）

| 症状 | 原因 | 対処 |
|------|------|------|
| `ダウンロードに失敗しました` | プロキシ / ファイアウォール / アンチウイルス | 別ネットワークで実行。DL済みなら `.build_cache/` が再利用される |
| `このPythonには tkinter がありません` | 埋め込み版や tcl/tk 無しPythonで実行した | python.org の公式インストーラ版Pythonで実行する |
| `_tkinter.pyd が ... にありません` | 移植元Pythonのインストールが不完全 | インストーラで「tcl/tk and IDLE」を有効にして修復インストール |
| `ライブラリのインストールに失敗` + `OSError` | Windowsのパス長制限 | リポジトリを浅い階層（`C:\dev\...` など）に置く |

---

## 技術メモ（開発者向け）

- Chrome接続は CDP（Chrome DevTools Protocol）ポート **9222**。`automation/base.py` の `connect_over_cdp`。
- Playwrightのクリックが効かない要素は `scrollIntoView` + JS `dispatchEvent` で回避。
- カテゴリポップアップは内外観 `div#jsiSelectPopBox` / 売主コメント `div#jsiSelectPopBoxUC` の両対応。
- 詳細な実装メモは `引継ぎ.md` 参照。

### 既知の未テスト項目
- SUUMOの**レイアウト指定タブ（`fill_layout`）** は実環境で未検証。セレクタ（ラジオの `value`、確定ボタンのテキスト）が変わっている可能性あり。

---

## 環境

- OS: Windows 10 / 11（64bit）
- Python: 3.13.4（配布版は同梱。配布先へのインストールは不要）
- 主要ライブラリ: playwright 1.62.0, openpyxl 3.1.5
- 配布zipサイズ: 約53MB（展開後 約120MB）
