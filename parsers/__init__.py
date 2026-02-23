"""
入力パースモジュール。

テキスト、XML、CommonMark形式の入力解析を提供する。
"""
from parsers.source_adapter import SourceAdapter, CommonMarkSourceAdapter
from parsers.commonmark import (
    parse_commonmark,
    split_into_sections,
    get_book_title,
    HeadingInfo,
    Section,
)
from parsers.xml_converter import (
    convert_xml_to_audio_txt,
    get_title_and_paragraphs_from_xml,
    is_xml_file,
    is_txt_file,
)

__all__ = [
    "SourceAdapter",
    "CommonMarkSourceAdapter",
    "parse_commonmark",
    "split_into_sections",
    "get_book_title",
    "HeadingInfo",
    "Section",
    "convert_xml_to_audio_txt",
    "get_title_and_paragraphs_from_xml",
    "is_xml_file",
    "is_txt_file",
]
