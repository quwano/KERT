# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

KERT（EPUB3 & DAISY4 Support Tool）は、CommonMark拡張テキストファイルまたはXMLファイルからMedia Overlay（音声同期）付きのEPUB3電子書籍を生成するPythonプロジェクトです。再生中に句読点単位でハイライト表示される音声付き電子書籍を作成します。

## 多言語対応

以下の言語をサポートしています：

| 言語コード | 言語 | TTS エンジン | MFA モデル |
|-----------|------|-------------|-----------|
| `ja_JP` | 日本語 | VOICEVOX | japanese_mfa |
| `en_US` | English (US) | macOS say (Samantha) / Windows SAPI | english_us_arpa |
| `de_DE` | Deutsch | macOS say (Anna) / Windows SAPI | german_mfa |

## 処理パイプライン

### CommonMarkファイル入力の場合（単一ファイル）
```
input.md (CommonMark形式)
    ↓ parsers/commonmark.py (見出し解析・セクション分割)
sections (HeadingInfo tree)
    ↓ parsers/source_adapter.py (CommonMarkSourceAdapter)
reading_text
    ↓ audio/tts.py (TTS: VOICEVOX/macOS say/Windows SAPI)
audio.wav
    ↓ audio/tts.py (FFmpeg)
audio.mp3
    ↓ audio/textgrid/generator.py (Montreal Forced Aligner)
audio.TextGrid
    ↓ epub/builder_commonmark.py
book_YYYYMMDDHHMMSS.epub (階層的nav.xhtml付き)
```

### CommonMarkファイル入力の場合（複数ファイル）
```
folder/
├── 01_chapter1.md
├── 02_chapter2.md
└── ...
    ↓ 各ファイルごとに音声生成
work_multi/
├── textgrid/*.TextGrid
└── audio/*.mp3
    ↓ epub/builder_commonmark.py (build_commonmark_multi_epub)
book_YYYYMMDDHHMMSS.epub (複数音声、階層的nav.xhtml付き)
```

### XMLファイル入力の場合（単一ファイル）
```
source.xml (入力XML)
    ↓ parsers/xml_converter.py (XSLT 3.0 via saxonche)
audio.txt (読み上げ用テキスト)
    ↓ audio/tts.py (TTS)
audio.wav
    ↓ audio/tts.py (FFmpeg)
audio.mp3
    ↓ audio/textgrid/generator.py (Montreal Forced Aligner)
audio.TextGrid
    ↓ epub/builder.py (XMLからXHTML変換、title1-title5で階層分割)
book_YYYYMMDDHHMMSS.epub (階層的nav.xhtml付き)
```

### XMLファイル入力の場合（複数ファイル）
```
folder/
├── 01_chapter1.xml
├── 02_chapter2.xml
└── ...
    ↓ 各ファイルごとに音声生成
work_multi/
├── textgrid/*.TextGrid
└── audio/*.mp3
    ↓ epub/builder_multi.py
book_YYYYMMDDHHMMSS.epub (各ファイルがチャプター、階層的nav.xhtml付き)
```

## 実行コマンド

```bash
# メイン処理（全パイプライン実行）
python main.py
```

## フォルダ構成

```
KERT/
├── main.py                    # エントリーポイント
├── core/                      # コアモジュール
│   ├── __init__.py
│   ├── config.py              # 設定定数の一元管理
│   ├── exceptions.py          # カスタム例外クラス
│   ├── logger.py              # ロギングユーティリティ
│   └── metadata_reader.py     # メタデータ（metadata.txt）読み込み
├── audio/                     # 音声処理モジュール
│   ├── __init__.py
│   ├── pipeline.py            # 音声生成パイプライン統合
│   ├── tts.py                 # TTS音声生成（VOICEVOX/macOS say/Windows SAPI）、FFmpegでMP3変換
│   └── textgrid/              # TextGrid処理サブパッケージ
│       ├── __init__.py
│       ├── generator.py       # MFAを使用したTextGrid生成
│       ├── matcher.py         # TextGridとテキストのマッチング処理
│       └── utils.py           # TextGridユーティリティ
├── epub/                      # EPUB生成モジュール
│   ├── __init__.py
│   ├── builder.py             # 単一ファイル（XML）からのEPUB3生成（階層セクション対応）
│   ├── builder_multi.py       # 複数ファイル（XML）からのEPUB3生成（階層セクション対応）
│   ├── builder_commonmark.py  # CommonMarkファイルからのEPUB3生成
│   ├── packaging.py           # EPUBパッケージング（フォルダ構造、ZIP生成）
│   ├── templates.py           # XHTML/SMIL/OPF/nav.xhtmlテンプレート生成
│   └── utils.py               # EPUB生成共通ユーティリティ（後方互換性用）
├── parsers/                   # 入力パースモジュール
│   ├── __init__.py
│   ├── commonmark.py          # CommonMark解析、見出し階層抽出、セクション分割
│   ├── source_adapter.py      # 入力ソース抽象化（XML/CommonMark）
│   └── xml_converter.py       # XMLからaudio.txt/XHTMLへの変換（XSLT 3.0使用）
├── text/                      # テキスト処理モジュール
│   ├── __init__.py
│   ├── common.py              # 共通ユーティリティ（TextNormalizer、ルビ変換等）
│   ├── processing.py          # テキスト正規化、書式処理、位置マッピング
│   └── xhtml.py               # XHTML処理（XML入力用位置マッピング）
├── tools/                     # スタンドアロンツール
│   ├── __init__.py
│   ├── split_commonmark.py    # CommonMarkファイル分割ツール
│   └── unwrap_lines.py        # 行結合ツール
└── resources/                 # リソースファイル
    ├── xml_to_audio_txt.xsl   # XML→読み上げテキスト変換用XSLT
    ├── xml_to_xhtml.xsl       # XML→XHTML変換用XSLT
    ├── xml_split_at_delimiters.xsl  # XML句読点分割前処理用XSLT
    └── document_schema.xsd    # XML入力用スキーマ
```

## 主要モジュール

| パッケージ/ファイル | 役割 |
|----------|------|
| `main.py` | エントリーポイント、パイプライン全体の制御、UI |
| **core/** | |
| `core/config.py` | 設定定数の一元管理、多言語設定 |
| `core/exceptions.py` | カスタム例外クラス |
| `core/logger.py` | ロギングユーティリティ |
| `core/metadata_reader.py` | メタデータ（metadata.txt）読み込み |
| **audio/** | |
| `audio/pipeline.py` | 音声生成パイプライン統合（テキスト→WAV→MP3→TextGrid） |
| `audio/tts.py` | TTS音声生成（VOICEVOX/macOS say/Windows SAPI）、FFmpegでMP3変換 |
| `audio/textgrid/generator.py` | MFAを使用したTextGrid（タイミング情報）生成 |
| `audio/textgrid/matcher.py` | TextGridとテキストのマッチング処理（Strategy Pattern使用） |
| **epub/** | |
| `epub/builder.py` | 単一XMLファイルからのEPUB3生成（title1-title5による階層セクション対応） |
| `epub/builder_multi.py` | 複数XMLファイルからのEPUB3生成（階層セクション対応） |
| `epub/builder_commonmark.py` | CommonMarkファイルからのEPUB3生成（単一/複数） |
| `epub/packaging.py` | EPUBパッケージング（フォルダ構造、ZIP生成） |
| `epub/templates.py` | XHTML/SMIL/OPF/nav.xhtmlテンプレート生成 |
| **parsers/** | |
| `parsers/commonmark.py` | CommonMark解析、見出し階層抽出、セクション分割 |
| `parsers/source_adapter.py` | 入力ソース抽象化（XML/CommonMark） |
| `parsers/xml_converter.py` | XMLからaudio.txt/XHTMLへの変換（XSLT 3.0使用） |
| **text/** | |
| `text/common.py` | 共通ユーティリティ（TextNormalizer、ルビ変換等） |
| `text/processing.py` | テキスト正規化、書式処理、位置マッピング |
| `text/xhtml.py` | XHTML処理（XML入力用位置マッピング） |

## 入力形式

### 1. CommonMark拡張形式（推奨）

見出し（`#`〜`#####`）で階層構造を表現。各見出しが別XHTMLファイルに分割されます。

```markdown
# 書籍タイトル

最初の段落。

## 第一章

第一章の内容。

### 第一節

第一節の内容。
```

**書式記法:**
- `[表示テキスト](+読み)` : 読み替え（表示と読み上げが異なる場合）
- `[漢字](-ふりがな)` : ルビ
- `**テキスト**` : 太字（strong）
- `[テキスト]{.underline}` : 下線
- `[テキスト]{.frame}` : 囲み枠
- `~テキスト~` : 下付き文字（sub）
- `^テキスト^` : 上付き文字（sup）
- `![代替テキスト](画像パス)` : 画像

### 2. XML形式

XMLスキーマ（document_schema.xsd）に準拠。`title1`〜`title5`で階層構造を表現。

| 要素 | 役割 |
|------|------|
| `root` | ルート要素 |
| `title1`〜`title5` | 見出し（レベル1〜5、階層的nav生成） |
| `p` | 段落 |
| `ruby` | ルビ（要素内容=親字、@yomi=読み） |
| `yomikae` | 読み替え（表示=要素内容、読み上げ=@yomi） |
| `u` | 下線 |
| `g` | 強調 |
| `sub` | 下付き文字 |
| `sup` | 上付き文字 |

## nav.xhtml生成ルール

| 入力形式 | 単一ファイル | 複数ファイル |
|---------|-------------|-------------|
| CommonMark | `#`〜`#####`の階層構造（なければメタデータタイトルのみ） | 各ファイルの見出し階層を結合 |
| XML | `title1`〜`title5`の階層構造（なければメタデータタイトルのみ） | 各ファイルの`title1`〜`title5`階層を結合 |

## システム要件

- **VOICEVOX**: 日本語音声合成エンジン（localhost:50021で起動、ja_JP使用時）
- **macOS say**: 英語/ドイツ語音声合成（macOS上でen_US/de_DE使用時）
- **Windows SAPI**: 英語/ドイツ語音声合成（Windows上でen_US/de_DE使用時、macOS sayの代替として自動選択）
- **FFmpeg**: 音声変換（WAV→MP3）
- **Conda**: MFA環境管理（環境名: `mfa`）
- **Montreal Forced Aligner**: 音声アライメント
  - 日本語: `japanese_mfa` モデル
  - 英語: `english_us_arpa` モデル
  - ドイツ語: `german_mfa` モデル
- **Python パッケージ**:
  - `textgrid`: TextGrid操作ライブラリ
  - `saxonche`: XSLT 3.0プロセッサ（XML入力機能用）

## アーキテクチャ上の注意点

### parsers/source_adapter.py の設計パターン
- **Factory Pattern**: `SourceAdapter.create()`で適切なアダプターを生成
  - `XMLSourceAdapter`: XML用（`get_sections()`で階層セクション取得可能）
  - `CommonMarkSourceAdapter`: CommonMark用（`get_sections()`, `get_heading_hierarchy()`で階層取得可能）
- 各アダプターは統一インターフェースを提供（`get_title()`, `get_paragraphs()`, `generate_reading_text()`等）

### audio/textgrid/matcher.py の設計パターン
- **Strategy Pattern**: `MatchingStrategy`抽象基底クラスを使用
  - `WordMatchingStrategy`: 単語単位ハイライト
  - `PunctuationMatchingStrategy`: 句読点単位ハイライト（`。、，.,`まで）— 現在UIではこちらに固定
- **MatchingState**: 処理状態を保持するデータクラス
- **UnkTokenProcessor**: MFA未認識単語(`<unk>`)の処理を担当
- **TextGridMatcher**: ファサードクラス
- テキスト入力とXML入力で異なる正規化・位置変換関数を使用（`is_xml`フラグで切り替え）

### parsers/commonmark.py のデータ構造
- **HeadingInfo**: 見出し情報（level, title, title_raw, title_xhtml, content, children）
  - `title_raw`: 書式記法を保持した生テキスト（`generate_reading_text()`で使用）
  - `title`: `strip_formatting_for_display()`済みの表示用テキスト
- **Section**: セクション情報（id, heading, paragraphs）
- `parse_commonmark()`: ファイルを解析して見出し階層を構築
- `split_into_sections()`: 見出し階層をフラットなセクションリストに変換

### parsers/xml_converter.py のデータ構造
- **XmlSection**: セクション情報（level, title_text, title_xhtml, paragraphs_xhtml）
  - `level`: 見出しレベル（0-5、0=タイトルなし）
- `get_sections_from_xml()`: XSLT 2段階変換（句読点分割→XHTML変換）でセクションリスト取得
- XSLT前処理: `xml_split_at_delimiters.xsl`で句読点文字ごとに`<span>`分割

### text/processing.py の主要クラス
- **FormattingHandler**: 書式記法をXHTMLタグに変換（プレースホルダー方式）
- `normalize_text`: テキストファイル用の正規化（ルビ記法→読み、全角→半角）
- `reading_pos_to_original`: 読みテキスト位置→元テキスト位置の変換

### text/common.py の主要クラス
- **TextNormalizer**: テキスト正規化ユーティリティ（全角→半角変換等を一元管理）
  - 丸数字（①②③...）、ローマ数字（Ⅰ Ⅱ Ⅲ...）、全角数字、括弧、ハイフンの正規化

### audio/textgrid/generator.py
- MFAは`conda run -n mfa`経由で実行
- `--beam 100 --retry_beam 400`オプションでアライメント精度向上
- 言語に応じた辞書・音響モデルを自動選択

## 生成されるEPUB3構造

### 単一ファイル入力時（CommonMark見出しあり、またはXML title1-title5あり）
```
OEBPS/
├── text/
│   ├── nav.xhtml       # 階層的目次
│   ├── chapter1.xhtml  # 見出し1
│   ├── chapter2.xhtml  # 見出し2
│   └── ...
├── smil/
│   ├── chapter1.smil
│   ├── chapter2.smil
│   └── ...
├── audio/
│   └── audio.mp3       # 単一音声ファイル
├── styles/
│   └── style.css
└── content.opf
META-INF/
└── container.xml
```

### 複数ファイル入力時
```
OEBPS/
├── text/
│   ├── nav.xhtml       # 目次（各ファイルの階層構造を結合）
│   ├── chapter1.xhtml  # ファイル1
│   ├── chapter2.xhtml  # ファイル2
│   └── ...
├── smil/
│   ├── chapter1.smil
│   ├── chapter2.smil
│   └── ...
├── audio/
│   ├── chapter1.mp3    # 各ファイルに対応する音声
│   ├── chapter2.mp3
│   └── ...
├── styles/
│   └── style.css
└── content.opf
```

## メタデータファイル（metadata.txt）

入力ファイルと同じディレクトリに配置。UTF-8エンコーディング。

```
title: 書籍タイトル
author: 著者名
contributor: 協力者
publisher: 出版社名
rights: 権利表記
subject: ジャンル
```

- `title`: 必須（nav.xhtmlとOPFで使用）
- `author`, `contributor`, `publisher`, `rights`, `subject`: オプション
- アクセシビリティメタデータ（`accessMode`, `accessibilityFeature`等）: 同一キー複数値対応

### ファイル名の規則
- 単一ファイル: `{入力ファイル名(拡張子なし)}_metadata.txt`（同ディレクトリ）
- フォルダ: `{フォルダ名}_metadata.txt`（親ディレクトリ）

## 設定値（core/config.py で一元管理）

| 設定 | 説明 |
|------|------|
| `LANG` | EPUB3ドキュメントのデフォルト言語（"ja"） |
| `AUDIO_BASE_NAME` | 音声ファイルのベース名 |
| `PRIMARY_SOUND_SUFFIX` | 生成されるWAVファイルの拡張子 |
| `SECONDARY_SOUND_SUFFIX` | 変換後MP3ファイルの拡張子 |
| `INPUT_TEXTGRID` | デフォルトのTextGridファイル名 |
| `SOURCE_AUDIO` | デフォルトの音声ファイル名 |
| `MFA_ENV_NAME` | Conda環境名 |
| `VOICEVOX_BASE_URL` | VOICEVOXエンジンのURL |
| `DEFAULT_SPEAKER_ID` | VOICEVOXデフォルトスピーカーID（109: 東北イタコ） |
| `DEFAULT_LANGUAGE` | デフォルト言語（"ja_JP"） |
| `LANGUAGE_CONFIGS` | 言語ごとの設定辞書（`LanguageConfig`データクラス） |
| `PUNCTUATION_CHARS` | 句読点文字設定（XSLT分割・matcher共通） |
