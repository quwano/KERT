"""
XMLファイルからaudio.txt（読み上げ用テキスト）およびXHTMLコンテンツを生成するモジュール。

XSLT 3.0 プロセッサ（saxonche）を使用してXML変換を行います。
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from saxonche import PySaxonProcessor

from text.common import TextNormalizer
from core.config import PUNCTUATION_CHARS

# XSLTファイルのパス（resourcesディレクトリに配置）
PROJECT_ROOT = Path(__file__).parent.parent
XSLT_AUDIO_TXT = PROJECT_ROOT / "resources" / "xml_to_audio_txt.xsl"
XSLT_XHTML = PROJECT_ROOT / "resources" / "xml_to_xhtml.xsl"
XSLT_SPLIT = PROJECT_ROOT / "resources" / "xml_split_at_delimiters.xsl"


@dataclass
class XmlSection:
    """XMLのセクション情報（title + paragraphs）。"""
    level: int                            # 見出しレベル (0-5、0=タイトルなし)
    title_text: str = ""                  # プレーンテキスト（nav用）
    title_xhtml: str = ""                 # XHTML（spanタグ付き、見出し内容用）
    paragraphs_xhtml: list[str] = field(default_factory=list)  # 本文段落XHTML


def convert_xml_to_audio_txt(xml_path: str, output_path: str) -> None:
    """
    XMLファイルから読み上げ用テキスト（audio.txt）を生成する。

    Parameters
    ----------
    xml_path : str
        入力XMLファイルのパス。
    output_path : str
        出力テキストファイルのパス。

    Notes
    -----
    XSLTによる変換ルール:
    - ruby要素: @yomi属性値（読み仮名）を出力
    - yomikae要素: @yomi属性値（読み替え）を出力
    - title1-title5/p要素: 改行区切りで出力
    - その他の装飾要素: 要素内容のみ出力
    """
    with PySaxonProcessor(license=False) as proc:
        xslt_proc = proc.new_xslt30_processor()
        executable = xslt_proc.compile_stylesheet(stylesheet_file=str(XSLT_AUDIO_TXT))
        result = executable.transform_to_string(source_file=str(xml_path))

        # 特殊文字を読み仮名に変換（MFAアライメント用）
        result = TextNormalizer.to_reading(result)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)


def get_sections_from_xml(xml_path: str) -> list[XmlSection]:
    """
    XMLファイルからセクションリストを取得する。

    Parameters
    ----------
    xml_path : str
        入力XMLファイルのパス。

    Returns
    -------
    list[XmlSection]
        セクション情報のリスト。
    """
    with PySaxonProcessor(license=False) as proc:
        xslt_proc = proc.new_xslt30_processor()

        # Step 1: 句読点で分割する前処理
        split_exec = xslt_proc.compile_stylesheet(stylesheet_file=str(XSLT_SPLIT))
        delimiter_regex = f"[{PUNCTUATION_CHARS}]"
        split_exec.set_parameter("delimiter-pattern",
                                 proc.make_string_value(delimiter_regex))
        split_result = split_exec.transform_to_string(source_file=str(xml_path))

        # Step 2: 前処理済みXMLからXHTML変換
        xhtml_exec = xslt_proc.compile_stylesheet(stylesheet_file=str(XSLT_XHTML))
        split_node = proc.parse_xml(xml_text=split_result)
        result = xhtml_exec.transform_to_string(xdm_node=split_node)

    return _extract_sections(result)


def get_title_and_paragraphs_from_xml(xml_path: str) -> tuple[str, str, list[str]]:
    """
    XMLファイルからタイトルと本文段落を取得する（XHTML変換済み）。

    後方互換性のため維持。内部でget_sections_from_xml()を使用。

    Parameters
    ----------
    xml_path : str
        入力XMLファイルのパス。

    Returns
    -------
    tuple[str, str, list[str]]
        - title_text : str
            タイトルのプレーンテキスト（目次用、ルビ除去済み）。
        - title_xhtml : str
            タイトルのXHTMLコンテンツ（h1内容用）。
        - paragraphs_xhtml : list[str]
            本文段落のXHTMLコンテンツリスト。
    """
    sections = get_sections_from_xml(xml_path)

    if not sections:
        return "", "", []

    # 最初のセクションのtitleを返す
    title_text = sections[0].title_text
    title_xhtml = sections[0].title_xhtml

    # 全セクションの段落をフラットに返す
    all_paragraphs: list[str] = []
    for sec in sections:
        all_paragraphs.extend(sec.paragraphs_xhtml)

    return title_text, title_xhtml, all_paragraphs


def _extract_sections(xml_str: str) -> list[XmlSection]:
    """
    XSLT出力XMLからセクションリストを抽出する。

    Parameters
    ----------
    xml_str : str
        XSLT変換結果のXML文字列。
        形式: <result><section level="N"><heading>...</heading><heading-text>...</heading-text><p>...</p>...</section>...</result>

    Returns
    -------
    list[XmlSection]
        セクション情報のリスト。
    """
    sections: list[XmlSection] = []

    # <section level="N">...</section> をイテレート
    section_pattern = r'<section\s+level="(\d+)">(.*?)</section>'
    for match in re.finditer(section_pattern, xml_str, re.DOTALL):
        level = int(match.group(1))
        content = match.group(2)

        # <heading>...</heading> を抽出
        title_xhtml = _extract_content(content, "heading")

        # <heading-text>...</heading-text> を抽出
        heading_text_xhtml = _extract_content(content, "heading-text")
        title_text = _strip_xhtml_tags(heading_text_xhtml) if heading_text_xhtml else _strip_xhtml_tags(title_xhtml)

        # <p>...</p> を抽出
        paragraphs = _extract_paragraphs(content)

        sections.append(XmlSection(
            level=level,
            title_text=title_text,
            title_xhtml=title_xhtml,
            paragraphs_xhtml=paragraphs
        ))

    return sections


def _extract_content(xml_str: str, tag_name: str) -> str:
    """XMLから指定タグの内容を抽出する。"""
    pattern = rf"<{tag_name}>(.*?)</{tag_name}>"
    match = re.search(pattern, xml_str, re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_paragraphs(xml_str: str) -> list[str]:
    """XMLからすべてのp要素の内容をリストで抽出する。"""
    pattern = r"<p>(.*?)</p>"
    matches = re.findall(pattern, xml_str, re.DOTALL)
    return [m.strip() for m in matches]


def _strip_xhtml_tags(xhtml: str) -> str:
    """XHTMLタグを除去してプレーンテキストを返す。"""
    # ruby要素からルビテキスト（rt内容）を除去し、親字のみ残す
    result = re.sub(r"<ruby><rb>(.*?)</rb><rt>.*?</rt></ruby>", r"\1", xhtml)
    # その他すべてのタグを除去
    result = re.sub(r"<[^>]+>", "", result)
    return result


def is_xml_file(file_path: str) -> bool:
    """ファイルがXMLファイルかどうかを判定する。"""
    return Path(file_path).suffix.lower() == ".xml"


def is_txt_file(file_path: str) -> bool:
    """ファイルがテキストファイルかどうかを判定する。"""
    return Path(file_path).suffix.lower() == ".txt"
