"""
CommonMarkテキストの解析モジュール。

見出し（#〜#####）の階層構造を解析し、セクションに分割します。
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from text.common import READING_SUB_PATTERN, strip_formatting, TextNormalizer, strip_formatting_for_display
from text.processing import escape_with_formatting


# 見出しパターン: 行頭の#（1〜5個）+ 空白 + テキスト
HEADING_PATTERN = re.compile(r'^(#{1,5})\s+(.+)$')


@dataclass
class HeadingInfo:
    """見出し情報を保持するデータクラス。"""
    level: int                    # 1-5 (# through #####)
    title: str                    # プレーンテキスト（nav用）
    title_xhtml: str              # XHTML形式（h1-h5用）
    title_raw: str = ""           # 元のマークダウンテキスト（process_paragraph用）
    content: list[str] = field(default_factory=list)       # この見出し配下の段落
    children: list['HeadingInfo'] = field(default_factory=list)  # 子見出し


@dataclass
class Section:
    """EPUBチャプター用のセクション情報。"""
    id: str                       # chapter1, chapter2, etc.
    heading: HeadingInfo          # 見出し情報
    paragraphs: list[str] = field(default_factory=list)   # 本文段落


def extract_heading(line: str) -> tuple[int, str] | None:
    """
    行から見出しレベルとテキストを抽出する。

    Parameters
    ----------
    line : str
        解析する行。

    Returns
    -------
    tuple[int, str] | None
        見出しの場合は (レベル, テキスト) のタプル。
        見出しでない場合は None。

    Examples
    --------
    >>> extract_heading("# Title")
    (1, "Title")
    >>> extract_heading("## Chapter")
    (2, "Chapter")
    >>> extract_heading("Normal text")
    None
    """
    match = HEADING_PATTERN.match(line.strip())
    if match:
        level = len(match.group(1))
        title = match.group(2).strip()
        return level, title
    return None


def process_title_for_xhtml(title: str) -> str:
    """
    見出しテキストをXHTML用に処理する。

    書式記法をXHTMLタグに変換します。
    - 読み替え記法 [表示](+読み) → 表示
    - 強調 **text** → <strong>text</strong>
    - 下線 [text]{.underline} → <u>text</u>
    - 枠囲み [text]{.frame} → <span>text</span>
    - ルビ [漢字](-かんじ) → <ruby>漢字<rt>かんじ</rt></ruby>

    Parameters
    ----------
    title : str
        元の見出しテキスト。

    Returns
    -------
    str
        XHTML用に処理されたテキスト（書式タグ付き）。
    """
    return escape_with_formatting(title)


def process_title_for_reading(title: str) -> str:
    """
    見出しテキストを読み上げ用に処理する。

    読み替え記法 [表示](+読み) から読み部分を抽出します。

    Parameters
    ----------
    title : str
        元の見出しテキスト。

    Returns
    -------
    str
        TTS用に処理されたテキスト。
    """
    # 読み替え記法から読み部分を抽出: [表示](+読み) → 読み
    return READING_SUB_PATTERN.sub(r'\2', title)


def parse_commonmark(file_path: str) -> tuple[HeadingInfo | None, list[str]]:
    """
    CommonMarkファイルを解析して見出し階層構造を構築する。

    Parameters
    ----------
    file_path : str
        CommonMarkファイルのパス。

    Returns
    -------
    tuple[HeadingInfo | None, list[str]]
        - 見出し階層のルート（最初のh1見出し）。見出しがない場合はNone。
        - ファイル内の全行リスト。

    Notes
    -----
    見出しの階層構造を構築し、各見出しの配下にある段落を
    content属性に格納します。
    """
    if not Path(file_path).exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.rstrip('\n\r') for line in f]

    if not lines:
        return None, []

    # 見出しと段落を解析
    headings: list[HeadingInfo] = []
    current_heading: HeadingInfo | None = None

    for line in lines:
        heading_info = extract_heading(line)

        if heading_info:
            level, title = heading_info
            # title_xhtml: 書式タグ付きXHTML（h1-h5およびnav用）
            title_xhtml = process_title_for_xhtml(title)
            # title_plain: プレーンテキスト（書式除去、内部使用・読み上げ用）
            title_plain = strip_formatting_for_display(title)

            new_heading = HeadingInfo(
                level=level,
                title=title_plain,
                title_xhtml=title_xhtml,
                title_raw=title,
                content=[],
                children=[]
            )
            headings.append(new_heading)
            current_heading = new_heading
        elif current_heading is not None:
            # 現在の見出しに段落を追加
            if line.strip():  # 空行以外
                current_heading.content.append(line)
        # 見出しが出現する前の段落は無視（またはルートに追加する場合は別途処理）

    if not headings:
        return None, lines

    # 階層構造を構築
    root = _build_hierarchy(headings)

    return root, lines


def _build_hierarchy(headings: list[HeadingInfo]) -> HeadingInfo:
    """
    フラットな見出しリストから階層構造を構築する。

    Parameters
    ----------
    headings : list[HeadingInfo]
        見出しのフラットリスト（出現順）。

    Returns
    -------
    HeadingInfo
        階層構造のルート見出し。
    """
    if not headings:
        raise ValueError("見出しリストが空です")

    root = headings[0]
    stack: list[HeadingInfo] = [root]

    for heading in headings[1:]:
        # スタックからこの見出しの親を見つける
        while stack and stack[-1].level >= heading.level:
            stack.pop()

        if stack:
            # 親の子として追加
            stack[-1].children.append(heading)
        # else: ルートと同レベルまたは上位の見出し（通常は発生しない）

        stack.append(heading)

    return root


def split_into_sections(root: HeadingInfo) -> list[Section]:
    """
    見出し階層をフラットなセクションリストに変換する。

    各見出しが1つのセクション（EPUBチャプター）になります。

    Parameters
    ----------
    root : HeadingInfo
        見出し階層のルート。

    Returns
    -------
    list[Section]
        セクションのリスト（出現順）。
    """
    sections: list[Section] = []
    chapter_num = 1

    def _traverse(heading: HeadingInfo) -> None:
        nonlocal chapter_num

        section = Section(
            id=f"chapter{chapter_num}",
            heading=heading,
            paragraphs=heading.content.copy()
        )
        sections.append(section)
        chapter_num += 1

        for child in heading.children:
            _traverse(child)

    _traverse(root)
    return sections


def generate_reading_text(sections: list[Section]) -> str:
    """
    セクションリストからTTS用読み上げテキストを生成する。

    Parameters
    ----------
    sections : list[Section]
        セクションのリスト。

    Returns
    -------
    str
        TTS用の読み上げテキスト（改行区切り）。

    Notes
    -----
    - 読み替え記法 [表示](+読み) は読み部分に変換
    - 各見出しと段落は改行で区切られる
    """
    lines: list[str] = []

    for section in sections:
        # 見出しを読み用に変換
        heading_reading = _process_line_for_reading(section.heading.title_raw or section.heading.title)
        if heading_reading.strip():
            lines.append(heading_reading)

        # 段落を読み用に変換
        for para in section.paragraphs:
            para_reading = _process_line_for_reading(para)
            if para_reading.strip():
                lines.append(para_reading)

    return '\n'.join(lines)


def _process_line_for_reading(text: str) -> str:
    """
    行をTTS読み上げ用に処理する。

    Parameters
    ----------
    text : str
        元のテキスト行。

    Returns
    -------
    str
        TTS用に処理されたテキスト。
    """
    # すべての書式記法を除去して読み用テキストに変換
    result = strip_formatting(text)
    # 特殊文字を読み仮名に変換
    result = TextNormalizer.to_reading(result)
    return result


def get_book_title(root: HeadingInfo | None) -> str:
    """
    ルート見出しから書籍タイトルを取得する。

    Parameters
    ----------
    root : HeadingInfo | None
        見出し階層のルート。

    Returns
    -------
    str
        書籍タイトル。ルートがない場合は "Untitled"。
    """
    if root is None:
        return "Untitled"
    return root.title
