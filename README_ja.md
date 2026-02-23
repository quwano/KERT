# KERT - EPUB3 & DAISY4 Support Tool

**[English](./README.md)** | **日本語**

![version](https://img.shields.io/badge/version-v1.0.0-brightgreen)
![license](https://img.shields.io/badge/license-GPL-green)
![platform](https://img.shields.io/badge/platform-MacOS%20Sequoia%2FTahoe%20Windows%2011-blue)

## このプロジェクトについて

KERT は、テキストファイルから **Media Overlay（音声同期）付き DAISY4/EPUB3フォーマットの電子書籍** を生成するツールです。Pythonで記述されています。

入力形式として **CommonMark 拡張記法**（`.txt` / `.md`）と **XML 形式**（`.xml`）に対応しています。

### 処理の流れ

```
入力ファイル (.txt / .md / .xml)
    ↓  テキスト解析・読み上げテキスト生成
    ↓  TTS（音声合成）で WAV 生成
    ↓  FFmpeg で MP3 変換
    ↓  Montreal Forced Aligner で音声アライメント（TextGrid 生成）
    ↓  XHTML + SMIL 生成・EPUB パッケージング
EPUB3 ファイル（音声同期付き）
```

## 必要な環境

### Python

Python 3.12 以上が必要です（型ヒントに `X | None` 構文を使用しているため）。

### Conda / Montreal Forced Aligner (MFA)

音声とテキストのアライメント（どの単語が音声のどの位置に対応するかの解析）に [Montreal Forced Aligner (MFA)](https://montreal-forced-aligner.readthedocs.io/) を使用します。

#### Conda のインストール

MFA の実行環境として Conda が必要です。[Miniforge](https://github.com/conda-forge/miniforge) または [Miniconda](https://docs.anaconda.com/free/miniconda/) をインストールしてください。

> **Windows での注意**: KERT は conda の実行ファイルを自動的に検出します（PATH、環境変数 `CONDA_EXE`、`%USERPROFILE%\miniforge3` 等の一般的なインストールパスを順に検索）。自動検出で見つからない場合は、システム環境変数の PATH に Conda の `Scripts` ディレクトリを追加するか、環境変数 `CONDA_EXE` に conda.exe のフルパスを設定してください。

#### MFA のインストール

MFA は Conda 環境にインストールします。環境名はデフォルトで `mfa` です。

```bash
# Conda 環境の作成と MFA インストール
conda create -n mfa -c conda-forge montreal-forced-aligner
conda activate mfa
```

MFA のインストール後、使用する言語の辞書モデルと音響モデルをダウンロードしてください（詳細は「[MFA モデルのインストール](#mfa-モデルのインストール)」を参照）。

> **注意**: KERT の実行中に MFA は `conda run -n mfa` 経由で自動的に呼び出されるため、事前に `conda activate mfa` する必要はありません。

#### 日本語使用時の追加セットアップ

日本語の MFA モデル（`japanese_mfa`）は内部で spacy / sudachipy を使用します。MFA インストール後に以下のコマンドで追加パッケージをインストールしてください:

```bash
conda activate mfa
pip install spacy sudachipy sudachidict_core
```

### VOICEVOX（日本語のみ）

日本語の音声合成には [VOICEVOX](https://voicevox.hiroshiba.jp/) を使用します。

- VOICEVOX エンジンを起動した状態で KERT を実行してください。
- デフォルトの接続先は `http://localhost:50021` です。
- デフォルトのスピーカーは ID 109（東北イタコ）です。

英語・ドイツ語のみ使用する場合は VOICEVOX は不要です。

> **重要: VOICEVOX の利用規約について**
>
> VOICEVOX で生成した音声を含む EPUB を配布・公開する場合は、VOICEVOX の[利用規約](https://voicevox.hiroshiba.jp/term/)および使用したキャラクターごとの利用規約を必ず確認してください。キャラクターによっては商用利用の制限やクレジット表記の義務があります。KERT のデフォルト話者は「東北イタコ」（ID 109）です。利用規約の詳細は [東北イタコ公式サイト](https://voicevox.hiroshiba.jp/product/tohoku_itako/) を参照してください。

### macOS say / Windows SAPI（英語・ドイツ語）

英語・ドイツ語の音声合成には OS 組み込みの TTS を使用します。

- **macOS**: `say` コマンド（英語: Samantha、ドイツ語: Anna）
- **Windows**: PowerShell 経由で System.Speech.Synthesis（SAPI）を使用。macOS say と同じ言語設定で自動的にフォールバックされます。

追加のインストールは不要です。

### FFmpeg

TTS が生成した WAV ファイルを MP3 に変換するために [FFmpeg](https://ffmpeg.org/) を使用します。

```bash
# macOS (Homebrew)
brew install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg
```

`ffmpeg` コマンドにパスが通っていることを確認してください。

### pip パッケージ

```bash
pip install -r requirements.txt
```

インストールされるパッケージ:

| パッケージ | 用途 |
|-----------|------|
| `textgrid` | MFA が生成した TextGrid ファイルの読み込み |
| `saxonche` | XSLT 3.0 プロセッサ |
saxoncheはXML入力時の変換に使用します。CommonMark 入力のみの場合は不要です。不要な場合は、requirements.txtからsaxoncheの記述を削除してください。

## 多言語対応

### 対応言語一覧

| 言語コード | 言語 | TTS エンジン | MFA 辞書 / 音響モデル |
|-----------|------|-------------|---------------------|
| `ja_JP` | 日本語 | VOICEVOX | `japanese_mfa` |
| `en_US` | English (US) | macOS say (Samantha) / Windows SAPI | `english_us_arpa` |
| `de_DE` | Deutsch | macOS say (Anna) / Windows SAPI | `german_mfa` |

### MFA モデルのインストール

使用する言語に応じて、MFA の辞書モデルと音響モデルをダウンロードしてください。

```bash
# 日本語
conda run -n mfa mfa model download dictionary japanese_mfa
conda run -n mfa mfa model download acoustic japanese_mfa

# 英語 (US)
conda run -n mfa mfa model download dictionary english_us_arpa
conda run -n mfa mfa model download acoustic english_us_arpa

# ドイツ語
conda run -n mfa mfa model download dictionary german_mfa
conda run -n mfa mfa model download acoustic german_mfa
```

### 新しい言語の追加方法

上記 3 言語以外も対応可能です。言語を追加するには、以下の手順で行います。

1. **MFA モデルの準備**: 対象言語の辞書モデルと音響モデルをインストールします。利用可能なモデルは [MFA のドキュメント](https://mfa-models.readthedocs.io/) を参照してください。

2. **`core/config.py` の `LANGUAGE_CONFIGS` に追記**: 以下の形式でエントリを追加します。

```python
"fr_FR": LanguageConfig(
    code="fr_FR",
    display_name="Français",
    epub_lang="fr",
    mfa_dictionary="french_mfa",      # MFA 辞書モデル名
    mfa_acoustic="french_mfa",        # MFA 音響モデル名
    tts_engine="say",                  # "voicevox" または "say"
    tts_voice="Thomas",               # macOS say の音声名（say の場合）
),
```

- `tts_engine`: 日本語は `"voicevox"`、それ以外は `"say"` を指定します。Windows では `"say"` 指定時に自動的に SAPI にフォールバックされます。
- `tts_voice`: macOS say で使用する音声名です。`say -v '?'` で利用可能な音声を確認できます。

## ドキュメントの作り方

KERT は **CommonMark 拡張記法** と **XML 形式** の 2 種類の入力形式に対応しています。

### CommonMark 拡張記法

拡張子 `.txt` または `.md` のテキストファイルに、CommonMark（Markdown）ベースの記法で記述します。

#### 見出しによる階層構造

`#`（1〜5 個）で見出しを記述します。見出しごとに EPUB 内の別ページ（XHTML ファイル）に分割され、目次（nav.xhtml）に階層構造として反映されます。

```markdown
# 書籍タイトル

最初の段落。

## 第一章

第一章の内容。

### 第一節

第一節の内容。
```

- `#` が書籍タイトル（h1）になります。
- `##` 以降が章・節として階層化されます。
- 見出しがないファイルでも処理可能です（その場合、metadata.txt のタイトルが使用されます）。

#### 書式記法一覧

| 記法 | 説明 | 例                 | EPUB での表示                   |
|------|------|-------------------|-----------------------------|
| `[漢字](-ふりがな)` | ルビ | `[首都](-しゅと)`| <ruby>首都<rt>しゅと</rt></ruby> |
| `[表示テキスト](+読み)` | 読み替え | `[本気](+まじ)`| 「本気」と表示、「まじ」と読み上げ           |
| `**テキスト**` | 太字 | `**重要**`| **重要**                      |
| `[テキスト]{.underline}` | 下線 | `[注意]{.underline}`| <u>注意</u>                   |
| `[テキスト]{.frame}` | 囲み枠 | `[　ア　]{.frame}`| 枠線付きテキスト                    |
| `~テキスト~` | 下付き文字 | `H~2~O`| H<sub>2</sub>O              |
| `^テキスト^` | 上付き文字 | `10^3^`| 10<sup>3</sup>              |

- 読み替え記法 `[表示](+読み)` は、表示と音声読み上げを別々に指定したい場合に使います。
- 書式記法はネスト（入れ子）に対応しています。例: `[**太字の下線**]{.underline}`

#### 画像の挿入

```markdown
![代替テキスト](画像ファイルパス)
```

- 画像ファイルは入力ファイルと同じディレクトリに配置するか、相対パスで指定します。
- 画像は EPUB 内の `images/` ディレクトリにコピーされます。
- 対応形式: SVG, PNG, JPEG, GIF, WebP

### XML 形式

XML スキーマ（`resources/document_schema.xsd`）に準拠した XML ファイルで記述します。

#### 基本構造

```xml
<?xml version="1.0" encoding="UTF-8"?>
<root>
  <title1>書籍タイトル</title1>
  <p>本文の段落です。</p>
  <p>次の段落です。</p>
</root>
```

ルート要素は `<root>` で、その直下に見出し要素（`title1`〜`title5`）と段落要素（`p`）を配置します。

#### 要素一覧

| 要素 | 説明 | 例                                 |
|------|------|-----------------------------------|
| `<p>` | 段落 | `<p>本文テキスト</p>`                   |
| `<title1>`〜`<title5>` | 見出し（レベル 1〜5） | `<title1>タイトル</title1>`           |
| `<ruby yomi="読み">親字</ruby>` | ルビ | `<ruby yomi="しゅと">首都</ruby>`      |
| `<yomikae yomi="読み">表示</yomikae>` | 読み替え | `<yomikae yomi="まじ">本気</yomikae>` |
| `<u>` | 下線 | `<u>下線テキスト</u>`                   |
| `<g>` | 強調（太字） | `<g>強調テキスト</g>`                   |
| `<sub>` | 下付き文字 | `<sub>2</sub>`                    |
| `<sup>` | 上付き文字 | `<sup>3</sup>`                    |

- 装飾要素はネストできます。例: `<u><g>太字の下線</g></u>`

#### 階層構造（title1〜title5）

`title1`〜`title5` を使用すると、見出しごとに EPUB 内で別ページに分割され、階層的な目次が生成されます。CommonMark の `#`〜`#####` に対応します。

```xml
<root>
  <title1>書籍タイトル</title1>
  <title2>第一章</title2>
  <p>第一章の内容。</p>
  <title3>第一節</title3>
  <p>第一節の内容。</p>
  <title2>第二章</title2>
  <p>第二章の内容。</p>
</root>
```

### 書誌情報ファイル（metadata.txt）

EPUB の書誌情報（タイトル、著者など）を記載するテキストファイルです。**タイトルは必須**です。

#### ファイル名の規則

- **単一ファイル入力**: 入力ファイルと同じディレクトリに `{入力ファイル名（拡張子なし）}_metadata.txt` を配置します。
  - 例: `mybook.txt` → `mybook_metadata.txt`
  - 例: `document.xml` → `document_metadata.txt`
- **フォルダ入力**: フォルダの親ディレクトリに `{フォルダ名}_metadata.txt` を配置します。
  - 例: フォルダ `chapters/` → 親ディレクトリに `chapters_metadata.txt`

#### フォーマット

UTF-8 エンコーディングのテキストファイルで、各行に `キー: 値` の形式で記述します。

```
title: 書籍タイトル
author: 著者名
contributor: 協力者
publisher: 出版社名
rights: (C) 2026 著者名
subject: ジャンル
```

| キー | 説明 | 必須 |
|------|------|------|
| `title` | 書籍タイトル | 必須 |
| `author` | 著者名 | |
| `contributor` | 協力者 | |
| `publisher` | 出版社名 | |
| `rights` | 権利表記 | |
| `subject` | ジャンル・分類 | |

#### アクセシビリティメタデータ

EPUB のアクセシビリティ情報を追加できます。

```
accessMode: textual
accessModeSufficient: textual
accessibilityFeature: index
accessibilityHazard: noFlashingHazard
accessibilityHazard: noMotionSimulationHazard
accessibilityHazard: noSoundHazard
accessibilitySummary: No special notes
```

各情報については[DAISYのサイト](https://kb.daisy.org/publishing/docs/metadata/schema.org/index.html)を参照してください。

### 単一ファイルとフォルダ（複数ファイル）

KERT は 2 つの処理モードに対応しています。

**単一ファイルモード**: 1 つの入力ファイルから 1 つの EPUB を生成します。音声ファイルは 1 つにまとまります。

**フォルダモード**: フォルダ内の複数ファイルをまとめて 1 つの EPUB を生成します。各ファイルが 1 チャプターになり、ファイルごとに個別の音声ファイルが生成されます。

```
chapters/
├── 01_prologue.txt    → chapter1.xhtml + chapter1.mp3
├── 02_chapter1.txt    → chapter2.xhtml + chapter2.mp3
└── 03_chapter2.txt    → chapter3.xhtml + chapter3.mp3
```

- ファイルはファイル名の自然順（数字部分を数値として比較）でソートされます。
- CommonMark の場合、`.txt` と `.md` の両方が収集対象です。
- XML の場合、`.xml` ファイルが収集対象です。
- フォルダの `_metadata.txt` は親ディレクトリに配置してください。

## 使い方

### 実行方法

```bash
python main.py
```

対話形式で以下を順に選択します。

1. **言語**: 日本語 / English (US) / Deutsch
2. **入力形式**: CommonMark 拡張テキストファイル / XML ファイル
3. **処理モード**: 単一ファイル / フォルダ（複数ファイル）
4. **入力パス**: ファイルまたはフォルダのパス
5. **中間ファイル**: 残すかどうか

### 実行例

日本語・CommonMark・単一ファイルの場合:

```
$ python main.py
==================================================
EPUB生成ツール
==================================================
言語を選択してください / Select language:
  1: 日本語 (ja_JP)
  2: English (US) (en_US)
  3: Deutsch (de_DE)
------
言語 / Language (1-3, デフォルト: 1): 1
------
入力形式を選択してください:
  1: CommonMark拡張テキストファイル（.txt/.md）
  2: XMLファイル（.xml）
------
選択 (1-2, デフォルト: 1): 1
------
処理モードを選択してください:
  1: 単一CommonMark拡張ファイルからEPUB生成
  2: フォルダ内の複数CommonMark拡張ファイルからEPUB生成
------
選択 (1-2, デフォルト: 1): 1
------
CommonMark拡張ファイル（.txt/.md）のパスを指定してください
/path/to/mybook.txt
------
中間ファイル（META-INF, OEBPS, audio.*）を残しますか？
  1: 残さない（デフォルト）
  2: 残す
------
選択 (1-2, デフォルト: 1): 1
```

### 出力ファイル

生成される EPUB ファイルは入力ファイルと同じディレクトリに出力されます。

ファイル名の形式: `{入力ファイル名}_{モード番号}_{タイムスタンプ}.epub`

- モード番号: 選択した言語・形式・処理モードの番号を連結した文字列（例: `111`）
- タイムスタンプ: `YYYYMMDDHHmmss` 形式

例: `mybook_111_20250219143000.epub`

### 中間ファイル

「中間ファイルを残す」を選択すると、`intermediate_products/` ディレクトリに以下が保存されます。

**単一ファイルモードの場合**:

| ファイル | 内容 |
|---------|------|
| `audio.txt` | TTS に渡す読み上げ用テキスト |
| `audio.wav` | TTS が生成した WAV 音声 |
| `audio.mp3` | FFmpeg で変換した MP3 音声 |
| `audio.TextGrid` | MFA が生成したアライメント情報 |
| `META-INF/` | EPUB コンテナ情報 |
| `OEBPS/` | EPUB コンテンツ（XHTML, SMIL, CSS など） |

**フォルダモードの場合**:

| ファイル | 内容 |
|---------|------|
| `work_multi/audio/` | 各チャプターの MP3 音声 |
| `work_multi/textgrid/` | 各チャプターの TextGrid |
| `META-INF/` | EPUB コンテナ情報 |
| `OEBPS/` | EPUB コンテンツ |

中間ファイルの XHTML を確認することで、書式記法の変換結果やスパン分割の状態をデバッグできます。

## 生成される EPUB の構造

生成される EPUB3 の内部構造は以下のとおりです。

**単一ファイル入力（見出しあり）の場合**:

```
book.epub
├── mimetype
├── META-INF/
│   └── container.xml
└── OEBPS/
    ├── content.opf          ← パッケージドキュメント
    ├── text/
    │   ├── nav.xhtml        ← 階層的目次
    │   ├── chapter1.xhtml   ← # 見出し1
    │   ├── chapter2.xhtml   ← ## 見出し2
    │   └── ...
    ├── smil/
    │   ├── chapter1.smil    ← 音声同期情報
    │   ├── chapter2.smil
    │   └── ...
    ├── audio/
    │   └── audio.mp3        ← 単一音声ファイル
    └── styles/
        └── style.css        ← ハイライト表示用 CSS
```

**フォルダ入力の場合**:

```
book.epub
├── mimetype
├── META-INF/
│   └── container.xml
└── OEBPS/
    ├── content.opf
    ├── text/
    │   ├── nav.xhtml
    │   ├── chapter1.xhtml   ← ファイル1
    │   ├── chapter2.xhtml   ← ファイル2
    │   └── ...
    ├── smil/
    │   ├── chapter1.smil
    │   ├── chapter2.smil
    │   └── ...
    ├── audio/
    │   ├── chapter1.mp3     ← ファイル1の音声
    │   ├── chapter2.mp3     ← ファイル2の音声
    │   └── ...
    └── styles/
        └── style.css
```

再生中のハイライト表示は、CSS クラス `.-epub-media-overlay-active` によって黄色背景で表示されます。

ハイライトの色を変更したい場合は、`epub/packaging.py` の `CSS_CONTENT` 内にある `background-color` と `color` の値を編集してください。

### 動作確認環境

本ツールが生成したEPUB3は、以下の環境で動作確認しています。

- **表示・メディアオーバーレイの動作**: [Thorium Reader](https://thorium.edrlab.org/)
- **EPUB3 準拠チェック**: [Ace by DAISY](https://daisy.github.io/ace/)

## 付属ツール

`tools/` ディレクトリに、入力ファイルの準備に使えるスタンドアロンツールが含まれています。

### split_commonmark — CommonMark ファイル分割

長い CommonMark ファイルを見出し単位で複数ファイルに分割します。フォルダモードで処理する際の前処理に使用できます。

```bash
python tools/split_commonmark.py
```

- `#`（h1）で始まるセクションは `{元ファイル名}_0{拡張子}` に出力
- `##`（h2）で始まるセクションは `{元ファイル名}_1{拡張子}`、`{元ファイル名}_2{拡張子}`、... に出力

### unwrap_lines — 行結合

段落内の改行を半角スペースに置き換えます。英文テキストなど、段落途中で改行されたファイルの前処理に使用できます。

```bash
python tools/unwrap_lines.py
```

- 空行を段落区切りとして認識し、段落内の改行をスペースに変換します。
- 出力ファイルは元のファイル名の末尾に `_` を付加した名前になります（例: `input.txt` → `input_.txt`）。

## 謝辞

本ツールの開発にあたり、テストや貴重なフィードバックをいただいた以下の方に深く感謝いたします。

**宮崎翼**さん - マニュアルに不備がないかの確認およびWindowsでの動作検証

## 作者
KUWANO KAZUYUKI

## ライセンス・権利情報

[LICENSE.md](LICENSE.md) / [LICENSE_ja.md](LICENSE_ja.md) を参照してください。
