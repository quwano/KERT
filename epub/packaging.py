"""
EPUBパッケージングモジュール。

EPUB3のフォルダ構造作成、ファイル出力、
ZIPパッケージング等の機能を提供します。
"""
import re
import shutil
import zipfile
from pathlib import Path

from core import logger


CSS_CONTENT = """
/* 再生中のハイライト設定 */
.-epub-media-overlay-active {
    background-color: #ffff00 !important;
    color: #000000 !important;
}
.media-overlay-active {
    background-color: #ffff00 !important;
    color: #000000 !important;
}
h1 {
    font-size: 1.5em;
    margin-bottom: 1em;
}
h2, h3, h4, h5 {
    font-weight: normal;
}
"""

CONTAINER_XML = ('<?xml version="1.0" encoding="UTF-8"?>'
                 '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                 '<rootfiles>'
                 '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                 '</rootfiles>'
                 '</container>')


def create_epub_structure() -> tuple[Path, Path]:
    """
    EPUB3用のフォルダ構造を作成する。

    既存のOEBPS/META-INFフォルダがあれば削除してから、
    新しいフォルダ構造を作成します。

    Returns
    -------
    tuple[Path, Path]
        (oebps, meta_inf) フォルダのPathオブジェクトのタプル。

    Notes
    -----
    作成されるフォルダ構造::

        OEBPS/
        ├── text/
        ├── smil/
        ├── audio/
        ├── styles/
        └── images/
        META-INF/
    """
    oebps = Path("OEBPS")
    meta_inf = Path("META-INF")

    # 既存のフォルダをクリーンアップ
    for d in [oebps, meta_inf]:
        if d.exists():
            shutil.rmtree(d)

    # フォルダ構造の作成
    (oebps / "text").mkdir(parents=True)
    (oebps / "smil").mkdir(parents=True)
    (oebps / "audio").mkdir(parents=True)
    (oebps / "styles").mkdir(parents=True)
    (oebps / "images").mkdir(parents=True)
    meta_inf.mkdir(parents=True)

    return oebps, meta_inf


def write_css_file(oebps: Path) -> None:
    """
    CSSファイルを出力する。

    Parameters
    ----------
    oebps : Path
        OEBPSディレクトリのパス。styles/style.css に出力されます。
    """
    with open(oebps / "styles/style.css", "w", encoding="utf-8") as f:
        f.write(CSS_CONTENT)


def write_container_xml(meta_inf: Path) -> None:
    """
    container.xmlファイルを出力する。

    Parameters
    ----------
    meta_inf : Path
        META-INFディレクトリのパス。
    """
    with open(meta_inf / "container.xml", "w", encoding="utf-8") as f:
        f.write(CONTAINER_XML)


def package_epub(output_epub: str, oebps: Path, meta_inf: Path) -> None:
    """
    EPUB3形式でZIPパッケージングを行う。

    EPUB仕様に従い、mimetypeファイルを無圧縮で先頭に配置し、
    META-INFとOEBPSディレクトリを圧縮して格納します。

    Parameters
    ----------
    output_epub : str
        出力EPUBファイルのパス。
    oebps : Path
        OEBPSディレクトリのパス。
    meta_inf : Path
        META-INFディレクトリのパス。

    Notes
    -----
    EPUB仕様では以下の順序でファイルを格納する必要があります:
    1. mimetype（無圧縮、先頭）
    2. META-INF/
    3. OEBPS/
    """
    with zipfile.ZipFile(output_epub, "w") as z:
        # mimetypeは無圧縮で先頭に
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        # META-INFとOEBPSを圧縮して格納
        for d in [meta_inf, oebps]:
            for p in d.rglob("*"):
                if p.is_file():
                    z.write(p, p, compress_type=zipfile.ZIP_DEFLATED)


# 画像記法のパターン: ![代替テキスト](パス)
_IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')


def extract_and_copy_images(
    paragraphs: list[str],
    source_dir: Path,
    oebps: Path
) -> list[str]:
    """
    段落テキストから画像参照を抽出し、OEBPSのimagesフォルダにコピーする。

    Parameters
    ----------
    paragraphs : list[str]
        処理する段落のリスト。画像記法 ![alt](path) を含む場合があります。
    source_dir : Path
        画像ファイルの検索基準ディレクトリ。
    oebps : Path
        OEBPSディレクトリのパス。

    Returns
    -------
    list[str]
        コピーされた画像ファイル名のリスト（重複なし）。
    """
    image_filenames: list[str] = []
    full_text = "\n".join(paragraphs)
    image_refs = _IMAGE_PATTERN.findall(full_text)  # [(alt, path), ...]

    for alt, img_path in image_refs:
        img_source = source_dir / img_path
        if img_source.exists():
            filename = img_source.name
            if filename not in image_filenames:
                shutil.copy(img_source, oebps / "images" / filename)
                image_filenames.append(filename)
        else:
            logger.warning(f"画像ファイルが見つかりません: {img_source}")

    return image_filenames
