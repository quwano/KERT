"""数式処理パッケージ。

TeX→MathML（pandoc）、MathML→音声テキスト（Speech Rule Engine）の変換を提供します。
"""
from mathconv.converter import (
    MathProcessor,
    MathEntry,
    tex_to_mathml,
    mathml_to_speech,
    set_current_processor,
    get_current_processor,
    detect_math_in_commonmark,
    detect_math_in_xml,
    check_math_tools,
    MATH_PLACEHOLDER_PATTERN,
    INLINE_MATH_PATTERN,
    DISPLAY_MATH_PATTERN,
)

__all__ = [
    "MathProcessor",
    "MathEntry",
    "tex_to_mathml",
    "mathml_to_speech",
    "set_current_processor",
    "get_current_processor",
    "detect_math_in_commonmark",
    "detect_math_in_xml",
    "check_math_tools",
    "MATH_PLACEHOLDER_PATTERN",
    "INLINE_MATH_PATTERN",
    "DISPLAY_MATH_PATTERN",
]
