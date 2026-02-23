"""
EPUB生成モジュール。

EPUB3の生成、パッケージング、テンプレート生成を提供する。
"""
from epub.builder import build_complete_epub
from epub.builder_multi import build_multi_epub
from epub.builder_commonmark import build_commonmark_epub, build_commonmark_multi_epub
from epub.packaging import package_epub
from epub.templates import (
    ChapterInfo,
    generate_xhtml_chapter,
    generate_nav_xhtml,
    generate_nav_xhtml_single,
    generate_nav_xhtml_hierarchical,
    generate_smil_document,
    generate_opf_single_chapter,
    generate_opf_multi_chapter,
)

__all__ = [
    "build_complete_epub",
    "build_multi_epub",
    "build_commonmark_epub",
    "build_commonmark_multi_epub",
    "package_epub",
    "ChapterInfo",
    "generate_xhtml_chapter",
    "generate_nav_xhtml",
    "generate_nav_xhtml_single",
    "generate_nav_xhtml_hierarchical",
    "generate_smil_document",
    "generate_opf_single_chapter",
    "generate_opf_multi_chapter",
]
