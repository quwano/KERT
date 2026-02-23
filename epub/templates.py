"""
EPUB3用テンプレート生成モジュール。

XHTML、SMIL、OPFドキュメントのテンプレート生成を共通化します。
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from core.config import LANG  # デフォルト言語（後方互換性のため）


def _format_smil_clock_value(seconds: float) -> str:
    """
    秒数をSMIL3 clock value形式に変換する。

    Parameters
    ----------
    seconds : float
        秒数。

    Returns
    -------
    str
        SMIL3 clock value形式（例: "0:01:23.456"）。
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours}:{minutes:02d}:{secs:06.3f}"


# 画像ファイル拡張子からMIMEタイプへのマッピング
IMAGE_MEDIA_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
}


def get_image_media_type(filename: str) -> str:
    """
    画像ファイル名からMIMEタイプを取得する。

    Parameters
    ----------
    filename : str
        画像ファイル名（拡張子付き）。

    Returns
    -------
    str
        MIMEタイプ。未知の拡張子の場合は'application/octet-stream'。
    """
    ext = Path(filename).suffix.lower()
    return IMAGE_MEDIA_TYPES.get(ext, 'application/octet-stream')

if TYPE_CHECKING:
    from core.metadata_reader import BookMetadata


@dataclass
class ChapterInfo:
    """チャプター情報を保持するデータクラス。"""
    id: str
    title: str
    duration: float
    level: int = 1               # 見出しレベル（1-5、CommonMark用）
    title_xhtml: str = ""        # nav用XHTMLタイトル（書式タグ付き）
    xhtml_filename: str = ""
    smil_filename: str = ""
    audio_filename: str = ""

    def __post_init__(self):
        if not self.xhtml_filename:
            self.xhtml_filename = f"{self.id}.xhtml"
        if not self.smil_filename:
            self.smil_filename = f"{self.id}.smil"
        if not self.audio_filename:
            self.audio_filename = f"{self.id}.mp3"

    def get_nav_title(self) -> str:
        """nav用のタイトルを取得する。title_xhtmlがあればそれを、なければエスケープしたtitleを返す。"""
        if self.title_xhtml:
            return self.title_xhtml
        return escape(self.title)


def generate_xhtml_chapter(
    title: str,
    paragraphs: list[str],
    css_path: str = "../styles/style.css",
    h1_content: str | None = None,
    nav_content: str | None = None,
    lang: str | None = None
) -> str:
    """
    チャプター用XHTMLドキュメントを生成する。

    Parameters
    ----------
    title : str
        ドキュメントのタイトル（<title>要素に使用）。
    paragraphs : list[str]
        段落要素のリスト（既にXHTMLフォーマット済み）。
    css_path : str
        CSSファイルへの相対パス。
    h1_content : str | None
        h1要素の内容。Noneの場合はh1要素を生成しない。
    nav_content : str | None
        nav要素の内容。Noneの場合はnav要素を生成しない。

    Returns
    -------
    str
        生成されたXHTMLドキュメント。
    """
    nav_section = ""
    if nav_content:
        nav_section = f"\n    {nav_content}"

    h1_section = ""
    if h1_content:
        h1_section = f"\n        <h1>{h1_content}</h1>"

    paragraphs_content = chr(10).join(paragraphs) if paragraphs else ""
    doc_lang = lang if lang else LANG

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{doc_lang}">
<head>
    <title>{escape(title)}</title>
    <link rel="stylesheet" type="text/css" href="{css_path}"/>
</head>
<body>{nav_section}
    <section epub:type="chapter" role="doc-chapter">{h1_section}
{paragraphs_content}
    </section>
</body>
</html>'''


def generate_nav_xhtml(
    book_title: str,
    chapters: list[ChapterInfo],
    css_path: str = "../styles/style.css",
    lang: str | None = None
) -> str:
    """
    目次用nav.xhtmlを生成する。

    Parameters
    ----------
    book_title : str
        書籍のタイトル。
    chapters : list[ChapterInfo]
        チャプター情報のリスト。
    css_path : str
        CSSファイルへの相対パス。

    Returns
    -------
    str
        生成されたnav.xhtmlドキュメント。
    """
    nav_items = "\n".join([
        f'            <li><a href="{ch.xhtml_filename}">{ch.get_nav_title()}</a></li>'
        for ch in chapters
    ])
    doc_lang = lang if lang else LANG
    toc_title = "Table of Contents" if doc_lang != "ja" else "目次"

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{doc_lang}">
<head>
    <title>{escape(book_title)} - {toc_title}</title>
    <link rel="stylesheet" type="text/css" href="{css_path}"/>
</head>
<body>
    <nav epub:type="toc" id="toc" role="doc-toc">
        <h1>{toc_title}</h1>
        <ol>
{nav_items}
        </ol>
    </nav>
</body>
</html>'''


def generate_nav_xhtml_single(
    book_title: str,
    content_filename: str = "content.xhtml",
    css_path: str = "../styles/style.css",
    lang: str | None = None
) -> str:
    """
    単一ファイル用の目次nav.xhtmlを生成する。

    Parameters
    ----------
    book_title : str
        書籍のタイトル。
    content_filename : str
        コンテンツXHTMLファイル名。
    css_path : str
        CSSファイルへの相対パス。
    lang : str | None
        言語コード。

    Returns
    -------
    str
        生成されたnav.xhtmlドキュメント。
    """
    doc_lang = lang if lang else LANG
    toc_title = "Table of Contents" if doc_lang != "ja" else "目次"

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{doc_lang}">
<head>
    <title>{escape(book_title)} - {toc_title}</title>
    <link rel="stylesheet" type="text/css" href="{css_path}"/>
</head>
<body>
    <nav epub:type="toc" id="toc" role="doc-toc">
        <h1>{toc_title}</h1>
        <ol>
            <li><a href="{content_filename}">{escape(book_title)}</a></li>
        </ol>
    </nav>
</body>
</html>'''


def generate_nav_xhtml_hierarchical(
    book_title: str,
    chapters: list[ChapterInfo],
    css_path: str = "../styles/style.css",
    lang: str | None = None
) -> str:
    """
    階層構造を持つ目次用nav.xhtmlを生成する（CommonMark用）。

    Parameters
    ----------
    book_title : str
        書籍のタイトル。
    chapters : list[ChapterInfo]
        チャプター情報のリスト（level属性で階層を表現）。
    css_path : str
        CSSファイルへの相対パス。

    Returns
    -------
    str
        生成されたnav.xhtmlドキュメント。

    Notes
    -----
    ChapterInfo.levelに基づいてネストした<ol>構造を生成します。
    例: level=1の下にlevel=2があれば、level=2はネストされた<ol>内に配置されます。
    """
    nav_items = _build_nav_list_hierarchical(chapters)
    doc_lang = lang if lang else LANG
    toc_title = "Table of Contents" if doc_lang != "ja" else "目次"

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{doc_lang}">
<head>
    <title>{escape(book_title)} - {toc_title}</title>
    <link rel="stylesheet" type="text/css" href="{css_path}"/>
</head>
<body>
    <nav epub:type="toc" id="toc" role="doc-toc">
        <h1>{toc_title}</h1>
        <ol>
{nav_items}
        </ol>
    </nav>
</body>
</html>'''


def _build_nav_list_hierarchical(
    chapters: list[ChapterInfo],
    base_indent: int = 12
) -> str:
    """
    チャプターリストから階層的なnav用リスト要素を構築する。

    Parameters
    ----------
    chapters : list[ChapterInfo]
        チャプター情報のリスト。
    base_indent : int
        基本インデント（スペース数）。

    Returns
    -------
    str
        ネストした<li>要素の文字列。
    """
    if not chapters:
        return ""

    result_lines: list[str] = []
    stack: list[int] = []  # 開いている<ol>タグのレベルを追跡

    for i, ch in enumerate(chapters):
        level = ch.level
        indent = " " * base_indent

        # スタックから現在のレベルより深いものを閉じる
        while stack and stack[-1] >= level:
            prev_level = stack.pop()
            close_indent = " " * (base_indent + len(stack) * 4)
            result_lines.append(f"{close_indent}</ol>")
            result_lines.append(f"{close_indent}</li>")

        # 現在のインデントを計算
        current_indent = " " * (base_indent + len(stack) * 4)

        # 次のチャプターをチェックして、子があるかどうかを判断
        has_children = (
            i + 1 < len(chapters) and
            chapters[i + 1].level > level
        )

        if has_children:
            # 子がある場合: <li>を開いたままにして<ol>を開始
            result_lines.append(
                f'{current_indent}<li><a href="{ch.xhtml_filename}">{ch.get_nav_title()}</a>'
            )
            result_lines.append(f'{current_indent}    <ol>')
            stack.append(level)
        else:
            # 子がない場合: 単独の<li>
            result_lines.append(
                f'{current_indent}<li><a href="{ch.xhtml_filename}">{ch.get_nav_title()}</a></li>'
            )

    # 残りの開いている<ol>タグを閉じる
    while stack:
        stack.pop()
        close_indent = " " * (base_indent + len(stack) * 4)
        result_lines.append(f"{close_indent}</ol>")
        result_lines.append(f"{close_indent}</li>")

    return "\n".join(result_lines)


def generate_xhtml_chapter_with_heading_level(
    title: str,
    paragraphs: list[str],
    heading_level: int = 1,
    heading_content: str | None = None,
    css_path: str = "../styles/style.css",
    lang: str | None = None
) -> str:
    """
    指定した見出しレベルでチャプター用XHTMLドキュメントを生成する（CommonMark用）。

    Parameters
    ----------
    title : str
        ドキュメントのタイトル（<title>要素に使用）。
    paragraphs : list[str]
        段落要素のリスト（既にXHTMLフォーマット済み）。
    heading_level : int
        見出しレベル（1-6）。1=h1, 2=h2, etc.
    heading_content : str | None
        見出し要素の内容。Noneの場合は見出し要素を生成しない。
    css_path : str
        CSSファイルへの相対パス。

    Returns
    -------
    str
        生成されたXHTMLドキュメント。
    """
    # 見出しレベルを1-6に制限
    level = max(1, min(6, heading_level))
    heading_tag = f"h{level}"

    heading_section = ""
    if heading_content:
        heading_section = f"\n        <{heading_tag}>{heading_content}</{heading_tag}>"

    paragraphs_content = chr(10).join(paragraphs) if paragraphs else ""
    doc_lang = lang if lang else LANG

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="{doc_lang}">
<head>
    <title>{escape(title)}</title>
    <link rel="stylesheet" type="text/css" href="{css_path}"/>
</head>
<body>
    <section epub:type="chapter" role="doc-chapter">{heading_section}
{paragraphs_content}
    </section>
</body>
</html>'''


def generate_smil_document(
    chapter_id: str,
    smil_pars: list[str],
    xhtml_path: str
) -> str:
    """
    SMILドキュメントを生成する。

    Parameters
    ----------
    chapter_id : str
        チャプターID。
    smil_pars : list[str]
        SMIL par要素のリスト。
    xhtml_path : str
        参照するXHTMLファイルへの相対パス。

    Returns
    -------
    str
        生成されたSMILドキュメント。
    """
    pars_content = "".join(smil_pars)

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<smil xmlns="http://www.w3.org/ns/SMIL" xmlns:epub="http://www.idpf.org/2007/ops" version="3.0">
    <body>
        <seq id="main_seq" epub:textref="{xhtml_path}">
{pars_content}
        </seq>
    </body>
</smil>'''


def _generate_optional_metadata_elements(metadata: "BookMetadata | None") -> str:
    """
    オプションのメタデータ要素を生成する。

    Parameters
    ----------
    metadata : BookMetadata | None
        書籍のメタデータ。Noneの場合は空文字列を返す。

    Returns
    -------
    str
        生成されたメタデータ要素のXML文字列。
    """
    if metadata is None:
        return ""

    elements: list[str] = []

    if metadata.contributor:
        elements.append(f"        <dc:contributor>{escape(metadata.contributor)}</dc:contributor>")
    if metadata.creator:
        elements.append(f"        <dc:creator>{escape(metadata.creator)}</dc:creator>")
    if metadata.publisher:
        elements.append(f"        <dc:publisher>{escape(metadata.publisher)}</dc:publisher>")
    if metadata.rights:
        elements.append(f"        <dc:rights>{escape(metadata.rights)}</dc:rights>")
    if metadata.subject:
        elements.append(f"        <dc:subject>{escape(metadata.subject)}</dc:subject>")
    if metadata.date:
        elements.append(f"        <dc:date>{metadata.date}</dc:date>")

    if hasattr(metadata, "accessibility_metadata") and metadata.accessibility_metadata:
        for key, value in metadata.accessibility_metadata:
            elements.append(f"        <meta property=\"schema:{escape(key)}\">{escape(value)}</meta>")

    if elements:
        return chr(10) + chr(10).join(elements)
    return ""


# =============================================================================
# OPF生成共通関数
# =============================================================================

def _generate_image_manifest_items(images: list[str] | None) -> list[str]:
    """画像のmanifest項目を生成する。"""
    if not images:
        return []
    return [
        f'        <item id="img{i+1}" href="images/{img}" media-type="{get_image_media_type(img)}"/>'
        for i, img in enumerate(images)
    ]


def _generate_opf_document(
    book_title: str,
    lang: str | None,
    metadata: "BookMetadata | None",
    duration_metas: list[str],
    manifest_items: list[str],
    spine_items: list[str]
) -> str:
    """
    OPFドキュメントを生成する共通関数。

    Parameters
    ----------
    book_title : str
        書籍のタイトル。
    lang : str | None
        言語コード。
    metadata : BookMetadata | None
        書籍のメタデータ。
    duration_metas : list[str]
        duration meta要素のリスト。
    manifest_items : list[str]
        manifest item要素のリスト。
    spine_items : list[str]
        spine itemref要素のリスト。

    Returns
    -------
    str
        生成されたOPFドキュメント。
    """
    modified_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    optional_metadata = _generate_optional_metadata_elements(metadata)
    doc_lang = lang if lang else LANG

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id" xml:lang="{doc_lang}" prefix="media: http://www.idpf.org/epub/vocab/overlays/#">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:identifier id="pub-id">urn:uuid:{uuid.uuid4()}</dc:identifier>
        <dc:title>{escape(book_title)}</dc:title>
        <dc:language>{doc_lang}</dc:language>{optional_metadata}
        <meta property="dcterms:modified">{modified_time}</meta>
{chr(10).join(duration_metas)}
        <meta property="media:active-class">-epub-media-overlay-active</meta>
    </metadata>
    <manifest>
{chr(10).join(manifest_items)}
    </manifest>
    <spine>
{chr(10).join(spine_items)}
    </spine>
</package>'''


def generate_opf_single_chapter(
    book_title: str,
    duration: float,
    xhtml_filename: str = "content.xhtml",
    smil_filename: str = "chapter1.smil",
    audio_filename: str = "audio.mp3",
    metadata: "BookMetadata | None" = None,
    images: list[str] | None = None,
    lang: str | None = None
) -> str:
    """
    単一チャプター用OPFドキュメントを生成する。

    Parameters
    ----------
    book_title : str
        書籍のタイトル。
    duration : float
        音声の総再生時間（秒）。
    xhtml_filename : str
        XHTMLファイル名。
    smil_filename : str
        SMILファイル名。
    audio_filename : str
        音声ファイル名。
    metadata : BookMetadata | None
        書籍のメタデータ。Noneの場合はオプション項目を含めない。
    images : list[str] | None
        画像ファイル名のリスト。Noneまたは空の場合は画像なし。

    Returns
    -------
    str
        生成されたOPFドキュメント。
    """
    formatted_duration = _format_smil_clock_value(duration)

    duration_metas = [
        f'        <meta property="media:duration">{formatted_duration}</meta>',
        f'        <meta property="media:duration" refines="#mo1">{formatted_duration}</meta>',
    ]

    manifest_items = [
        '        <item id="nav" href="text/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        f'        <item id="text1" href="text/{xhtml_filename}" media-type="application/xhtml+xml" media-overlay="mo1"/>',
        f'        <item id="mo1" href="smil/{smil_filename}" media-type="application/smil+xml"/>',
        f'        <item id="audio1" href="audio/{audio_filename}" media-type="audio/mpeg"/>',
        '        <item id="css" href="styles/style.css" media-type="text/css"/>',
    ]
    manifest_items.extend(_generate_image_manifest_items(images))

    spine_items = ['        <itemref idref="text1"/>']

    return _generate_opf_document(
        book_title, lang, metadata, duration_metas, manifest_items, spine_items
    )


def generate_opf_multi_chapter(
    book_title: str,
    chapters: list[ChapterInfo],
    total_duration: float,
    metadata: "BookMetadata | None" = None,
    images: list[str] | None = None,
    lang: str | None = None
) -> str:
    """
    複数チャプター用OPFドキュメントを生成する。

    Parameters
    ----------
    book_title : str
        書籍のタイトル。
    chapters : list[ChapterInfo]
        チャプター情報のリスト。
    total_duration : float
        音声の総再生時間（秒）。
    metadata : BookMetadata | None
        書籍のメタデータ。Noneの場合はオプション項目を含めない。
    images : list[str] | None
        画像ファイル名のリスト。Noneまたは空の場合は画像なし。

    Returns
    -------
    str
        生成されたOPFドキュメント。
    """
    manifest_items = [
        '        <item id="nav" href="text/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '        <item id="css" href="styles/style.css" media-type="text/css"/>',
    ]
    manifest_items.extend(_generate_image_manifest_items(images))

    spine_items: list[str] = []
    duration_metas = [
        f'        <meta property="media:duration">{_format_smil_clock_value(total_duration)}</meta>'
    ]

    for ch in chapters:
        ch_id = ch.id
        manifest_items.extend([
            f'        <item id="{ch_id}" href="text/{ch.xhtml_filename}" '
            f'media-type="application/xhtml+xml" media-overlay="mo_{ch_id}"/>',
            f'        <item id="mo_{ch_id}" href="smil/{ch.smil_filename}" '
            f'media-type="application/smil+xml"/>',
            f'        <item id="audio_{ch_id}" href="audio/{ch.audio_filename}" '
            f'media-type="audio/mpeg"/>',
        ])
        spine_items.append(f'        <itemref idref="{ch_id}"/>')
        duration_metas.append(
            f'        <meta property="media:duration" refines="#mo_{ch_id}">'
            f'{_format_smil_clock_value(ch.duration)}</meta>'
        )

    return _generate_opf_document(
        book_title, lang, metadata, duration_metas, manifest_items, spine_items
    )


def generate_opf_commonmark(
    book_title: str,
    chapters: list[ChapterInfo],
    total_duration: float,
    audio_filename: str = "audio.mp3",
    metadata: "BookMetadata | None" = None,
    images: list[str] | None = None,
    lang: str | None = None
) -> str:
    """
    CommonMark用OPFドキュメントを生成する（単一音声ファイル、複数チャプター）。

    Parameters
    ----------
    book_title : str
        書籍のタイトル。
    chapters : list[ChapterInfo]
        チャプター情報のリスト。
    total_duration : float
        音声の総再生時間（秒）。
    audio_filename : str
        音声ファイル名（全チャプター共通）。
    metadata : BookMetadata | None
        書籍のメタデータ。Noneの場合はオプション項目を含めない。
    images : list[str] | None
        画像ファイル名のリスト。Noneまたは空の場合は画像なし。

    Returns
    -------
    str
        生成されたOPFドキュメント。
    """
    manifest_items = [
        '        <item id="nav" href="text/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '        <item id="css" href="styles/style.css" media-type="text/css"/>',
        f'        <item id="audio" href="audio/{audio_filename}" media-type="audio/mpeg"/>',
    ]
    manifest_items.extend(_generate_image_manifest_items(images))

    spine_items: list[str] = []
    duration_metas = [
        f'        <meta property="media:duration">{_format_smil_clock_value(total_duration)}</meta>'
    ]

    for ch in chapters:
        ch_id = ch.id
        manifest_items.extend([
            f'        <item id="{ch_id}" href="text/{ch.xhtml_filename}" '
            f'media-type="application/xhtml+xml" media-overlay="mo_{ch_id}"/>',
            f'        <item id="mo_{ch_id}" href="smil/{ch.smil_filename}" '
            f'media-type="application/smil+xml"/>',
        ])
        spine_items.append(f'        <itemref idref="{ch_id}"/>')
        duration_metas.append(
            f'        <meta property="media:duration" refines="#mo_{ch_id}">'
            f'{_format_smil_clock_value(ch.duration)}</meta>'
        )

    return _generate_opf_document(
        book_title, lang, metadata, duration_metas, manifest_items, spine_items
    )


def generate_opf_commonmark_multi(
    book_title: str,
    chapters: list[ChapterInfo],
    total_duration: float,
    metadata: "BookMetadata | None" = None,
    images: list[str] | None = None,
    lang: str | None = None
) -> str:
    """
    複数CommonMarkファイル用OPFドキュメントを生成する（複数音声ファイル）。

    Parameters
    ----------
    book_title : str
        書籍のタイトル。
    chapters : list[ChapterInfo]
        チャプター情報のリスト。各チャプターにaudio_filenameが設定されている必要あり。
    total_duration : float
        音声の総再生時間（秒）。
    metadata : BookMetadata | None
        書籍のメタデータ。Noneの場合はオプション項目を含めない。
    images : list[str] | None
        画像ファイル名のリスト。Noneまたは空の場合は画像なし。
    lang : str | None
        言語コード。

    Returns
    -------
    str
        生成されたOPFドキュメント。
    """
    # 一意な音声ファイル名を収集
    audio_files: list[str] = []
    for ch in chapters:
        if ch.audio_filename and ch.audio_filename not in audio_files:
            audio_files.append(ch.audio_filename)

    manifest_items = [
        '        <item id="nav" href="text/nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '        <item id="css" href="styles/style.css" media-type="text/css"/>',
    ]

    # 音声ファイルのmanifest項目を追加
    for i, audio_filename in enumerate(audio_files):
        manifest_items.append(
            f'        <item id="audio{i+1}" href="audio/{audio_filename}" media-type="audio/mpeg"/>'
        )

    manifest_items.extend(_generate_image_manifest_items(images))

    spine_items: list[str] = []
    duration_metas = [
        f'        <meta property="media:duration">{_format_smil_clock_value(total_duration)}</meta>'
    ]

    for ch in chapters:
        ch_id = ch.id
        manifest_items.extend([
            f'        <item id="{ch_id}" href="text/{ch.xhtml_filename}" '
            f'media-type="application/xhtml+xml" media-overlay="mo_{ch_id}"/>',
            f'        <item id="mo_{ch_id}" href="smil/{ch.smil_filename}" '
            f'media-type="application/smil+xml"/>',
        ])
        spine_items.append(f'        <itemref idref="{ch_id}"/>')
        duration_metas.append(
            f'        <meta property="media:duration" refines="#mo_{ch_id}">'
            f'{_format_smil_clock_value(ch.duration)}</meta>'
        )

    return _generate_opf_document(
        book_title, lang, metadata, duration_metas, manifest_items, spine_items
    )
