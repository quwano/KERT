"""
テキスト処理モジュール。

テキスト正規化、書式処理、XHTML変換を提供する。
"""
from text.common import (
    TextNormalizer,
    RUBY_PATTERN,
    READING_SUB_PATTERN,
    strip_formatting,
    strip_formatting_for_display,
    ruby_to_xhtml,
    create_reading_file,
    change_suffix,
)
from text.processing import (
    FormattingHandler,
    normalize_text,
    escape_with_formatting,
    reading_pos_to_original,
    get_original_range,
)
from text.xhtml import (
    normalize_xhtml_text,
    xhtml_reading_pos_to_original,
    get_xhtml_original_range,
)

__all__ = [
    # common
    "TextNormalizer",
    "RUBY_PATTERN",
    "READING_SUB_PATTERN",
    "strip_formatting",
    "strip_formatting_for_display",
    "ruby_to_xhtml",
    "create_reading_file",
    "change_suffix",
    # processing
    "FormattingHandler",
    "normalize_text",
    "escape_with_formatting",
    "reading_pos_to_original",
    "get_original_range",
    # xhtml
    "normalize_xhtml_text",
    "xhtml_reading_pos_to_original",
    "get_xhtml_original_range",
]
