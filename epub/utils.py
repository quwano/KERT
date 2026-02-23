"""
EPUB3生成の共通ユーティリティモジュール（後方互換性用）。

このモジュールは後方互換性のために維持されています。
新しいコードでは以下のモジュールを直接インポートしてください:
- text_processing: テキスト正規化、ルビ処理、位置マッピング
- xhtml_processing: XHTML処理（XML入力用）
- textgrid_utils: TextGrid処理
- epub_packaging: EPUBパッケージング
"""

# text.processing から再エクスポート
from text.processing import (
    normalize_text,
    strip_ruby,
    escape_with_ruby,
    escape_with_formatting,
    reading_pos_to_original,
    get_original_range,
)

# text.xhtml から再エクスポート
from text.xhtml import (
    normalize_xhtml_text,
    xhtml_reading_pos_to_original,
    get_xhtml_original_range,
)

# audio.textgrid.utils から再エクスポート
from audio.textgrid.utils import extract_textgrid_intervals

# epub.packaging から再エクスポート
from epub.packaging import (
    CSS_CONTENT,
    CONTAINER_XML,
    create_epub_structure,
    write_css_file,
    write_container_xml,
    package_epub,
)

# 後方互換性のための__all__定義
__all__ = [
    # text_processing
    "normalize_text",
    "strip_ruby",
    "escape_with_ruby",
    "escape_with_formatting",
    "reading_pos_to_original",
    "get_original_range",
    # xhtml_processing
    "normalize_xhtml_text",
    "xhtml_reading_pos_to_original",
    "get_xhtml_original_range",
    # textgrid_utils
    "extract_textgrid_intervals",
    # epub_packaging
    "CSS_CONTENT",
    "CONTAINER_XML",
    "create_epub_structure",
    "write_css_file",
    "write_container_xml",
    "package_epub",
]
