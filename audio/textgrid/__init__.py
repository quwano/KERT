"""
TextGrid処理モジュール。

MFAを使用したTextGrid生成とマッチング処理を提供する。
"""
from audio.textgrid.generator import generate_textgrid_from_files_auto
from audio.textgrid.matcher import process_paragraph
from audio.textgrid.utils import extract_textgrid_intervals

__all__ = [
    "generate_textgrid_from_files_auto",
    "process_paragraph",
    "extract_textgrid_intervals",
]
