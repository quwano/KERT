"""
単一テキスト/XMLファイルからMedia Overlay付きEPUB3を生成するモジュール。

TextGridファイルと音声ファイルを使用して、再生中に単語単位で
ハイライト表示される音声付き電子書籍を作成します。
"""
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from core import logger
from core.exceptions import FileNotFoundError_, NoContentError
from core.messages import msg
from epub.packaging import (
    create_epub_structure,
    write_css_file,
    write_container_xml,
    package_epub,
    extract_and_copy_images,
)
from audio.textgrid.utils import extract_textgrid_intervals
from epub.templates import (
    ChapterInfo,
    generate_xhtml_chapter,
    generate_xhtml_chapter_with_heading_level,
    generate_smil_document,
    generate_opf_single_chapter,
    generate_opf_commonmark,
    generate_nav_xhtml_single,
    generate_nav_xhtml_hierarchical,
)
from audio.textgrid.matcher import process_paragraph
from core.config import INPUT_TEXTGRID, SOURCE_AUDIO
from parsers.source_adapter import SourceAdapter

if TYPE_CHECKING:
    from core.metadata_reader import BookMetadata
    from parsers.xml_converter import XmlSection


def _build_xml_sections_epub(
    book_title: str,
    adapter: "SourceAdapter",
    highlight_mode: str,
    metadata: "BookMetadata | None",
    output_epub: str,
    epub_lang: str | None
) -> str:
    """
    セクション構造を持つ単一XMLファイルからEPUB3を生成する。

    CommonMarkの見出し分割と同様に、各title1-title5セクションを
    別々のXHTMLファイルとして出力し、階層的nav.xhtmlを生成する。
    """
    sections: list["XmlSection"] = adapter.get_sections()

    if not sections:
        raise NoContentError("処理するセクションがありません。")

    logger.section(msg("xml_sections_epub_start"))
    logger.info(msg("epub_section_count", count=len(sections)))

    # フォルダ構造の作成
    oebps, meta_inf = create_epub_structure()

    # 音声ファイルのコピー
    if not Path(SOURCE_AUDIO).exists():
        raise FileNotFoundError_(SOURCE_AUDIO, msg("file_type_audio"))
    audio_filename = "audio.mp3"
    shutil.copy(SOURCE_AUDIO, oebps / "audio" / audio_filename)

    # CSSファイルの作成
    write_css_file(oebps)

    # 画像ファイルの抽出とコピー
    source_dir = Path(adapter.file_path).parent
    all_paragraphs = adapter.get_paragraphs()
    image_filenames = extract_and_copy_images(all_paragraphs, source_dir, oebps)

    # TextGridからタイミング情報を取得
    tg_intervals, total_duration = extract_textgrid_intervals(INPUT_TEXTGRID)

    # 各セクションの処理
    chapters: list[ChapterInfo] = []
    span_id = 0
    tg_index = 0

    for sec_idx, section in enumerate(sections, 1):
        chapter_id = f"chapter{sec_idx}"
        xhtml_path = f"../text/{chapter_id}.xhtml"
        audio_path = f"../audio/{audio_filename}"
        element_prefix = f"{chapter_id}_w"

        smil_pars: list[str] = []
        xhtml_paragraphs: list[str] = []

        # セクション開始時間を記録
        start_time = tg_intervals[tg_index][1] if tg_index < len(tg_intervals) else 0.0

        # 見出しの処理（XSLT由来のspan付きXHTML）
        if section.title_xhtml:
            heading_p, heading_smil, span_id, tg_index = process_paragraph(
                section.title_xhtml, tg_intervals, tg_index, span_id,
                element_prefix, xhtml_path, audio_path,
                highlight_mode=highlight_mode,
                is_xml=True
            )
            smil_pars.extend(heading_smil)

            # 見出しのコンテンツを抽出（<p>タグを除去）
            if heading_p:
                h_content = heading_p.strip()
                if h_content.startswith("<p>") and h_content.endswith("</p>"):
                    h_content = h_content[3:-4]
            else:
                h_content = section.title_xhtml
        else:
            h_content = None

        # 本文段落の処理
        for paragraph in section.paragraphs_xhtml:
            para_p, para_smil, span_id, tg_index = process_paragraph(
                paragraph, tg_intervals, tg_index, span_id,
                element_prefix, xhtml_path, audio_path,
                highlight_mode=highlight_mode,
                is_xml=True
            )
            smil_pars.extend(para_smil)
            if para_p:
                xhtml_paragraphs.append(para_p)

        # セクション終了時間を記録
        end_time = tg_intervals[tg_index - 1][2] if tg_index > 0 else 0.0
        duration = end_time - start_time

        # XHTML生成（見出しレベルに応じたタグを使用）
        heading_level = section.level if section.level > 0 else 1
        xhtml_content = generate_xhtml_chapter_with_heading_level(
            title=section.title_text,
            paragraphs=xhtml_paragraphs,
            heading_level=heading_level,
            heading_content=h_content,
            lang=epub_lang
        )

        # SMIL生成
        smil_content = generate_smil_document(
            chapter_id=chapter_id,
            smil_pars=smil_pars,
            xhtml_path=xhtml_path
        )

        # ファイル書き出し
        with open(oebps / "text" / f"{chapter_id}.xhtml", "w", encoding="utf-8") as f:
            f.write(xhtml_content)
        with open(oebps / "smil" / f"{chapter_id}.smil", "w", encoding="utf-8") as f:
            f.write(smil_content)

        # ChapterInfo（階層的nav用）
        # nav用タイトルはプレーンテキスト（title_xhtmlはspan付きなのでnav不向き）
        chapter_info = ChapterInfo(
            id=chapter_id,
            title=section.title_text,
            duration=duration,
            level=heading_level,
            audio_filename=audio_filename
        )
        chapters.append(chapter_info)

        logger.info(msg("epub_chapter_done", id=chapter_id, title=section.title_text))

    if not chapters:
        raise NoContentError("処理できるセクションがありませんでした。")

    # 合計時間
    total_duration = sum(ch.duration for ch in chapters)

    # nav.xhtml の生成（階層構造）
    nav_content = generate_nav_xhtml_hierarchical(book_title, chapters, lang=epub_lang)
    with open(oebps / "text/nav.xhtml", "w", encoding="utf-8") as f:
        f.write(nav_content)

    # OPF生成（単一音声+複数セクション）
    opf_content = generate_opf_commonmark(
        book_title, chapters, total_duration,
        audio_filename=audio_filename,
        metadata=metadata,
        images=image_filenames,
        lang=epub_lang
    )
    with open(oebps / "content.opf", "w", encoding="utf-8") as f:
        f.write(opf_content)

    # container.xml 書き出し
    write_container_xml(meta_inf)

    # パッケージング (ZIP)
    package_epub(output_epub, oebps, meta_inf)

    logger.success(msg("epub_saved", file=output_epub))
    logger.info(msg("epub_section_count_done", count=len(chapters)))
    logger.info(msg("epub_duration", duration=total_duration))

    return output_epub


def build_complete_epub(
    book_title: str,
    adapter: "SourceAdapter",
    highlight_mode: str = "word",
    metadata: "BookMetadata | None" = None,
    output_epub: str | None = None,
    epub_lang: str | None = None
) -> str:
    """
    TextGridファイルと音声ファイルからMedia Overlay付きEPUB3を生成する。

    TextGridから単語の時間情報を抽出し、SMILファイルを生成することで、
    再生中のテキストハイライト表示を実現します。出力EPUBファイル名は
    入力ファイル名から自動的に派生します。

    Parameters
    ----------
    book_title : str
        完成したepub書籍のタイトル。
    adapter : SourceAdapter
        入力ソースのアダプター。
    highlight_mode : str
        ハイライトモード。"word"（単語単位）または"punctuation"（句読点単位）。
    metadata : BookMetadata | None
        書籍のメタデータ。Noneの場合はオプション項目を含めない。

    Returns
    -------
    None

    Raises
    ------
    FileNotFoundError
        音声ファイルまたはTextGridファイルが見つからない場合。
    """
    # EPUBファイル名を入力ファイル名から派生（指定がない場合）
    if output_epub is None:
        output_epub = Path(adapter.file_path).stem + ".epub"

    # XMLでセクション構造がある場合はセクション別処理に分岐
    if adapter.is_xml:
        return _build_xml_sections_epub(
            book_title, adapter, highlight_mode, metadata, output_epub, epub_lang
        )

    logger.section(msg("xml_epub_start"))

    # 1. フォルダ構造の作成
    oebps, meta_inf = create_epub_structure()

    # 2. 音声ファイルのコピー
    if not Path(SOURCE_AUDIO).exists():
        raise FileNotFoundError_(SOURCE_AUDIO, msg("file_type_audio"))
    shutil.copy(SOURCE_AUDIO, oebps / "audio/audio.mp3")

    # 3. CSSファイルの作成
    write_css_file(oebps)

    # 4. ソースファイルから段落情報を取得（アダプター経由）
    paragraphs = adapter.get_paragraphs()

    # 4.5. 画像ファイルの抽出とコピー
    source_dir = Path(adapter.file_path).parent
    image_filenames = extract_and_copy_images(paragraphs, source_dir, oebps)

    # 5. TextGridからタイミング情報を取得
    tg_intervals, total_sec = extract_textgrid_intervals(INPUT_TEXTGRID)

    # 6. 元テキストをベースにしてspanを生成
    xhtml_paragraphs: list[str] = []
    smil_pars: list[str] = []
    span_id: int = 0
    tg_index: int = 0

    for paragraph in paragraphs:
        xhtml_para, para_smil, span_id, tg_index = process_paragraph(
            paragraph,
            tg_intervals,
            tg_index,
            span_id,
            element_id_prefix="w",
            xhtml_path="../text/content.xhtml",
            audio_filename="../audio/audio.mp3",
            highlight_mode=highlight_mode,
            is_xml=False
        )
        if xhtml_para:
            xhtml_paragraphs.append(xhtml_para)
        smil_pars.extend(para_smil)

    # 7. XHTML生成
    xhtml_content = generate_xhtml_chapter(
        title=book_title,
        paragraphs=xhtml_paragraphs,
        lang=epub_lang
    )

    # 7.5. nav.xhtml生成
    nav_content = generate_nav_xhtml_single(
        book_title=book_title,
        content_filename="content.xhtml",
        lang=epub_lang
    )

    # 8. SMIL生成
    smil_content = generate_smil_document(
        chapter_id="chapter1",
        smil_pars=smil_pars,
        xhtml_path="../text/content.xhtml"
    )

    # 9. OPF生成
    opf_content = generate_opf_single_chapter(
        book_title=book_title,
        duration=total_sec,
        metadata=metadata,
        images=image_filenames if image_filenames else None,
        lang=epub_lang
    )

    with open(oebps / "text/nav.xhtml", "w", encoding="utf-8") as f:
        f.write(nav_content)
    with open(oebps / "text/content.xhtml", "w", encoding="utf-8") as f:
        f.write(xhtml_content)
    with open(oebps / "smil/chapter1.smil", "w", encoding="utf-8") as f:
        f.write(smil_content)
    with open(oebps / "content.opf", "w", encoding="utf-8") as f:
        f.write(opf_content)

    # 10. container.xml 書き出し
    write_container_xml(meta_inf)

    # 11. パッケージング (ZIP)
    package_epub(output_epub, oebps, meta_inf)

    logger.success(msg("epub_saved", file=output_epub))

    return output_epub
