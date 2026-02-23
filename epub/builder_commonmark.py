"""
CommonMarkファイルからMedia Overlay付きEPUB3を生成するモジュール。

単一のCommonMarkファイルを見出しで分割し、階層的なnav.xhtml（目次）付きの
EPUB3電子書籍を生成します。
"""
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from core import logger
from core.messages import msg
from parsers.commonmark import Section
from epub.packaging import (
    create_epub_structure,
    write_css_file,
    write_container_xml,
    package_epub,
    extract_and_copy_images,
)
from core.exceptions import FileNotFoundError_, NoContentError
from parsers.source_adapter import CommonMarkSourceAdapter
from epub.templates import (
    ChapterInfo,
    generate_xhtml_chapter,
    generate_xhtml_chapter_with_heading_level,
    generate_smil_document,
    generate_nav_xhtml_single,
    generate_nav_xhtml_hierarchical,
    generate_opf_single_chapter,
    generate_opf_commonmark,
    generate_opf_commonmark_multi,
)
from text.processing import escape_with_formatting
from audio.textgrid.matcher import process_paragraph
from audio.textgrid.utils import extract_textgrid_intervals

if TYPE_CHECKING:
    from core.metadata_reader import BookMetadata


def build_section_xhtml_and_smil(
    section: Section,
    tg_intervals: list[tuple[str, float, float]],
    tg_index: int,
    span_id_start: int,
    audio_filename: str,
    highlight_mode: str = "punctuation",
    lang: str | None = None
) -> tuple[str, str, int, int, float, float]:
    """
    単一セクションのXHTMLとSMILコンテンツを生成する。

    Parameters
    ----------
    section : Section
        処理するセクション。
    tg_intervals : list[tuple[str, float, float]]
        TextGridのインターバルリスト。
    tg_index : int
        TextGridインターバルの開始インデックス。
    span_id_start : int
        span IDの開始番号。
    audio_filename : str
        音声ファイル名。例: "audio.mp3"
    highlight_mode : str
        ハイライトモード。"word"または"punctuation"。

    Returns
    -------
    tuple[str, str, int, int, float, float]
        - xhtml_content : str
            生成されたXHTMLコンテンツ。
        - smil_content : str
            生成されたSMILコンテンツ。
        - next_span_id : int
            次に使用すべきspan ID番号。
        - next_tg_index : int
            次に使用すべきTextGridインデックス。
        - start_time : float
            このセクションの開始時間（秒）。
        - end_time : float
            このセクションの終了時間（秒）。
    """
    chapter_id = section.id
    xhtml_path = f"../text/{chapter_id}.xhtml"
    audio_path = f"../audio/{audio_filename}"
    element_prefix = f"{chapter_id}_w"

    smil_pars: list[str] = []
    xhtml_paragraphs: list[str] = []
    span_id = span_id_start

    # セクション開始時間を記録
    start_time = tg_intervals[tg_index][1] if tg_index < len(tg_intervals) else 0.0

    # 見出しの処理（元のマークダウンテキストを使用してprocess_paragraphで変換）
    heading_raw = section.heading.title_raw or section.heading.title
    heading_p, heading_smil, span_id, tg_index = process_paragraph(
        heading_raw, tg_intervals, tg_index, span_id,
        element_prefix, xhtml_path, audio_path,
        highlight_mode=highlight_mode,
        is_xml=False
    )
    smil_pars.extend(heading_smil)

    # 見出しのコンテンツを抽出（<p>タグを除去）
    if heading_p:
        h_content = heading_p.strip()
        if h_content.startswith("<p>") and h_content.endswith("</p>"):
            h_content = h_content[3:-4]
    else:
        h_content = escape_with_formatting(heading_raw)

    # 本文段落の処理
    for paragraph in section.paragraphs:
        para_p, para_smil, span_id, tg_index = process_paragraph(
            paragraph, tg_intervals, tg_index, span_id,
            element_prefix, xhtml_path, audio_path,
            highlight_mode=highlight_mode,
            is_xml=False
        )
        smil_pars.extend(para_smil)

        if para_p:
            xhtml_paragraphs.append(para_p)

    # セクション終了時間を記録
    end_time = tg_intervals[tg_index - 1][2] if tg_index > 0 else 0.0

    # XHTML生成（見出しレベルに応じたタグを使用）
    xhtml_content = generate_xhtml_chapter_with_heading_level(
        title=section.heading.title,
        paragraphs=xhtml_paragraphs,
        heading_level=section.heading.level,
        heading_content=h_content,
        lang=lang
    )

    # SMIL生成
    smil_content = generate_smil_document(
        chapter_id=chapter_id,
        smil_pars=smil_pars,
        xhtml_path=xhtml_path
    )

    return xhtml_content, smil_content, span_id, tg_index, start_time, end_time


def _build_commonmark_epub_no_headings(
    book_title: str,
    adapter: CommonMarkSourceAdapter,
    output_epub: str,
    textgrid_path: Path,
    audio_path: Path,
    highlight_mode: str = "punctuation",
    metadata: "BookMetadata | None" = None,
    epub_lang: str | None = None
) -> None:
    """
    見出しがないCommonMarkファイルから単一ファイルEPUB3を生成する。

    Parameters
    ----------
    book_title : str
        書籍のタイトル（メタデータから取得）。
    adapter : CommonMarkSourceAdapter
        CommonMarkファイルのアダプター。
    output_epub : str
        出力EPUBファイル名。
    textgrid_path : Path
        TextGridファイルのパス。
    audio_path : Path
        MP3ファイルのパス。
    highlight_mode : str
        ハイライトモード。"word"または"punctuation"。
    metadata : BookMetadata | None
        書籍のメタデータ。
    epub_lang : str | None
        EPUB3ドキュメントの言語コード。
    """
    paragraphs = adapter.get_paragraphs()

    if not paragraphs:
        raise NoContentError("処理する段落がありません。")

    logger.section(msg("commonmark_epub_no_headings_start"))
    logger.info(msg("epub_paragraph_count", count=len(paragraphs)))

    # 必要なファイルの存在確認
    if not textgrid_path.exists():
        raise FileNotFoundError_(str(textgrid_path), msg("file_type_textgrid"))
    if not audio_path.exists():
        raise FileNotFoundError_(str(audio_path), msg("file_type_audio"))

    # フォルダ構造の作成
    oebps, meta_inf = create_epub_structure()

    # CSSファイルの作成
    write_css_file(oebps)

    # 画像ファイルの抽出とコピー
    source_dir = Path(adapter.file_path).parent
    image_filenames = extract_and_copy_images(paragraphs, source_dir, oebps)

    # 音声ファイルのコピー
    audio_filename = "audio.mp3"
    shutil.copy(audio_path, oebps / "audio" / audio_filename)

    # TextGridからタイミング情報を取得
    tg_intervals, total_duration = extract_textgrid_intervals(textgrid_path)

    # 各段落の処理（build_complete_epub.pyと同様）
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

    # XHTML生成
    xhtml_content = generate_xhtml_chapter(
        title=book_title,
        paragraphs=xhtml_paragraphs,
        lang=epub_lang
    )

    # nav.xhtml生成（タイトルのみ）
    nav_content = generate_nav_xhtml_single(
        book_title=book_title,
        content_filename="content.xhtml",
        lang=epub_lang
    )

    # SMIL生成
    smil_content = generate_smil_document(
        chapter_id="chapter1",
        smil_pars=smil_pars,
        xhtml_path="../text/content.xhtml"
    )

    # OPF生成
    opf_content = generate_opf_single_chapter(
        book_title=book_title,
        duration=total_duration,
        metadata=metadata,
        images=image_filenames,
        lang=epub_lang
    )

    # ファイル書き出し
    with open(oebps / "text/nav.xhtml", "w", encoding="utf-8") as f:
        f.write(nav_content)
    with open(oebps / "text/content.xhtml", "w", encoding="utf-8") as f:
        f.write(xhtml_content)
    with open(oebps / "smil/chapter1.smil", "w", encoding="utf-8") as f:
        f.write(smil_content)
    with open(oebps / "content.opf", "w", encoding="utf-8") as f:
        f.write(opf_content)

    # container.xml 書き出し
    write_container_xml(meta_inf)

    # パッケージング (ZIP)
    package_epub(output_epub, oebps, meta_inf)

    logger.success(msg("epub_saved", file=output_epub))
    logger.info(msg("epub_paragraph_count_done", count=len(xhtml_paragraphs)))
    logger.info(msg("epub_duration", duration=total_duration))


def build_commonmark_epub(
    book_title: str,
    adapter: CommonMarkSourceAdapter,
    output_epub: str,
    textgrid_path: Path,
    audio_path: Path,
    highlight_mode: str = "punctuation",
    metadata: "BookMetadata | None" = None,
    epub_lang: str | None = None
) -> None:
    """
    CommonMarkファイルからMedia Overlay付きEPUB3を生成する。

    Parameters
    ----------
    book_title : str
        書籍のタイトル。OPFメタデータとnav.xhtmlで使用されます。
    adapter : CommonMarkSourceAdapter
        CommonMarkファイルのアダプター。
    output_epub : str
        出力EPUBファイル名。
    textgrid_path : Path
        TextGridファイルのパス。
    audio_path : Path
        MP3ファイルのパス。
    highlight_mode : str
        ハイライトモード。"word"（単語単位）または"punctuation"（句読点単位）。
    metadata : BookMetadata | None
        書籍のメタデータ。Noneの場合はオプション項目を含めない。

    Notes
    -----
    生成されるEPUB3の構造::

        my_book.epub/
        ├── mimetype
        ├── META-INF/
        │   └── container.xml
        └── OEBPS/
            ├── content.opf
            ├── text/
            │   ├── nav.xhtml
            │   ├── chapter1.xhtml (見出しあり) / content.xhtml (見出しなし)
            │   ├── chapter2.xhtml
            │   └── ...
            ├── smil/
            │   ├── chapter1.smil
            │   ├── chapter2.smil
            │   └── ...
            ├── audio/
            │   └── audio.mp3    (単一音声ファイル)
            └── styles/
                └── style.css
    """
    # 見出しがない場合は単一ファイルモードで処理
    if not adapter.has_headings():
        _build_commonmark_epub_no_headings(
            book_title, adapter, output_epub, textgrid_path, audio_path,
            highlight_mode, metadata, epub_lang
        )
        return

    sections = adapter.get_sections()

    if not sections:
        raise NoContentError("処理するセクションがありません。")

    logger.section(msg("commonmark_epub_start"))
    logger.info(msg("epub_section_count", count=len(sections)))

    # 必要なファイルの存在確認
    if not textgrid_path.exists():
        raise FileNotFoundError_(str(textgrid_path), msg("file_type_textgrid"))
    if not audio_path.exists():
        raise FileNotFoundError_(str(audio_path), msg("file_type_audio"))

    # フォルダ構造の作成
    oebps, meta_inf = create_epub_structure()

    # CSSファイルの作成
    write_css_file(oebps)

    # 画像ファイルの抽出とコピー
    source_dir = Path(adapter.file_path).parent
    all_paragraphs = adapter.get_paragraphs()
    image_filenames = extract_and_copy_images(all_paragraphs, source_dir, oebps)

    # 音声ファイルのコピー
    audio_filename = "audio.mp3"
    shutil.copy(audio_path, oebps / "audio" / audio_filename)

    # TextGridからタイミング情報を取得
    tg_intervals, total_duration = extract_textgrid_intervals(textgrid_path)

    # 各セクションの処理
    chapters: list[ChapterInfo] = []
    span_id = 0
    tg_index = 0

    for section in sections:
        logger.info(msg("epub_section_processing", id=section.id, title=section.heading.title))

        # XHTML と SMIL の生成
        xhtml_content, smil_content, span_id, tg_index, start_time, end_time = (
            build_section_xhtml_and_smil(
                section, tg_intervals, tg_index, span_id,
                audio_filename, highlight_mode, lang=epub_lang
            )
        )

        # セクションの再生時間を計算
        duration = end_time - start_time

        # ファイル書き出し
        with open(oebps / "text" / f"{section.id}.xhtml", "w", encoding="utf-8") as f:
            f.write(xhtml_content)
        with open(oebps / "smil" / f"{section.id}.smil", "w", encoding="utf-8") as f:
            f.write(smil_content)

        # ChapterInfo（階層的nav用にlevelとtitle_xhtmlを含む）
        chapter_info = ChapterInfo(
            id=section.id,
            title=section.heading.title,
            duration=duration,
            level=section.heading.level,
            title_xhtml=section.heading.title_xhtml,
            audio_filename=audio_filename  # 全セクションで同じ音声ファイルを使用
        )
        chapters.append(chapter_info)

        logger.info(msg("epub_section_done", id=section.id))

    if not chapters:
        raise NoContentError("処理できるセクションがありませんでした。")

    # 合計時間を章のdurationから計算（EPUB3仕様: 合計 = 各章のdurationの合計）
    total_duration = sum(ch.duration for ch in chapters)

    # nav.xhtml の生成（階層構造）
    nav_content = generate_nav_xhtml_hierarchical(book_title, chapters, lang=epub_lang)
    with open(oebps / "text/nav.xhtml", "w", encoding="utf-8") as f:
        f.write(nav_content)

    # OPF (パッケージドキュメント) の生成
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


def build_commonmark_multi_epub(
    book_title: str,
    adapters: list[CommonMarkSourceAdapter],
    output_epub: str,
    textgrid_folder: Path,
    audio_folder: Path,
    highlight_mode: str = "punctuation",
    metadata: "BookMetadata | None" = None,
    epub_lang: str | None = None
) -> None:
    """
    複数CommonMarkファイルからMedia Overlay付きEPUB3を生成する。

    各ファイルの見出し階層を保持しつつ、ファイル間も階層構造で
    nav.xhtmlを生成します。

    Parameters
    ----------
    book_title : str
        書籍のタイトル。OPFメタデータとnav.xhtmlで使用されます。
    adapters : list[CommonMarkSourceAdapter]
        CommonMarkファイルのアダプターリスト（処理順にソート済み）。
    output_epub : str
        出力EPUBファイル名。
    textgrid_folder : Path
        TextGridファイルが格納されたフォルダ。
    audio_folder : Path
        MP3ファイルが格納されたフォルダ。
    highlight_mode : str
        ハイライトモード。"word"または"punctuation"。
    metadata : BookMetadata | None
        書籍のメタデータ。
    epub_lang : str | None
        EPUB3ドキュメントの言語コード。

    Notes
    -----
    生成されるEPUB3の構造::

        my_book.epub/
        ├── mimetype
        ├── META-INF/
        │   └── container.xml
        └── OEBPS/
            ├── content.opf
            ├── text/
            │   ├── nav.xhtml
            │   ├── file1_chapter1.xhtml
            │   ├── file1_chapter2.xhtml
            │   ├── file2_chapter1.xhtml
            │   └── ...
            ├── smil/
            │   ├── file1_chapter1.smil
            │   └── ...
            ├── audio/
            │   ├── file1.mp3
            │   ├── file2.mp3
            │   └── ...
            └── styles/
                └── style.css
    """
    if not adapters:
        raise NoContentError("処理するアダプターがありません。")

    logger.section(msg("commonmark_multi_epub_start"))
    logger.info(msg("epub_file_count_progress", count=len(adapters)))

    # フォルダ構造の作成
    oebps, meta_inf = create_epub_structure()

    # CSSファイルの作成
    write_css_file(oebps)

    # 画像ファイルの抽出とコピー（複数ファイルのときは包含フォルダを起点）
    base_folder = Path(adapters[0].file_path).parent
    image_filenames: list[str] = []
    for adapter in adapters:
        paragraphs = adapter.get_paragraphs()
        new_images = extract_and_copy_images(paragraphs, base_folder, oebps)
        for img in new_images:
            if img not in image_filenames:
                image_filenames.append(img)

    # 各ファイルの処理
    all_chapters: list[ChapterInfo] = []

    for file_idx, adapter in enumerate(adapters, 1):
        base_name = Path(adapter.file_path).stem
        file_prefix = f"file{file_idx}"

        # ファイルパスの構築
        textgrid_path = textgrid_folder / f"{base_name}.TextGrid"
        audio_path = audio_folder / f"{base_name}.mp3"

        if not textgrid_path.exists():
            raise FileNotFoundError_(str(textgrid_path), msg("file_type_textgrid"))
        if not audio_path.exists():
            raise FileNotFoundError_(str(audio_path), msg("file_type_audio"))

        # 音声ファイルのコピー
        audio_filename = f"{file_prefix}.mp3"
        shutil.copy(audio_path, oebps / "audio" / audio_filename)

        # TextGridからタイミング情報を取得
        tg_intervals, _ = extract_textgrid_intervals(textgrid_path)

        # このファイルのセクションを処理
        sections = adapter.get_sections()
        span_id = 0
        tg_index = 0

        logger.info(msg("epub_file_processing", name=base_name, count=len(sections)))

        for section_idx, section in enumerate(sections, 1):
            # ファイルごとに一意なchapter_idを生成
            chapter_id = f"{file_prefix}_chapter{section_idx}"

            # XHTML と SMIL の生成（IDプレフィックスにchapter_idを使用）
            xhtml_path = f"../text/{chapter_id}.xhtml"
            audio_path_rel = f"../audio/{audio_filename}"
            element_prefix = f"{chapter_id}_w"

            smil_pars: list[str] = []
            xhtml_paragraphs: list[str] = []

            # セクション開始時間を記録
            start_time = tg_intervals[tg_index][1] if tg_index < len(tg_intervals) else 0.0

            # 見出しの処理（元のマークダウンテキストを使用してprocess_paragraphで変換）
            heading_raw = section.heading.title_raw or section.heading.title
            heading_p, heading_smil, span_id, tg_index = process_paragraph(
                heading_raw, tg_intervals, tg_index, span_id,
                element_prefix, xhtml_path, audio_path_rel,
                highlight_mode=highlight_mode,
                is_xml=False
            )
            smil_pars.extend(heading_smil)

            # 見出しのコンテンツを抽出
            if heading_p:
                h_content = heading_p.strip()
                if h_content.startswith("<p>") and h_content.endswith("</p>"):
                    h_content = h_content[3:-4]
            else:
                h_content = escape_with_formatting(heading_raw)

            # 本文段落の処理
            for paragraph in section.paragraphs:
                para_p, para_smil, span_id, tg_index = process_paragraph(
                    paragraph, tg_intervals, tg_index, span_id,
                    element_prefix, xhtml_path, audio_path_rel,
                    highlight_mode=highlight_mode,
                    is_xml=False
                )
                smil_pars.extend(para_smil)
                if para_p:
                    xhtml_paragraphs.append(para_p)

            # セクション終了時間を記録
            end_time = tg_intervals[tg_index - 1][2] if tg_index > 0 else 0.0
            duration = end_time - start_time

            # XHTML生成
            xhtml_content = generate_xhtml_chapter_with_heading_level(
                title=section.heading.title,
                paragraphs=xhtml_paragraphs,
                heading_level=section.heading.level,
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

            # ChapterInfo（階層的nav用にlevelとtitle_xhtmlを含む）
            chapter_info = ChapterInfo(
                id=chapter_id,
                title=section.heading.title,
                duration=duration,
                level=section.heading.level,
                title_xhtml=section.heading.title_xhtml,
                audio_filename=audio_filename
            )
            all_chapters.append(chapter_info)

        logger.info(msg("epub_file_done", name=base_name))

    if not all_chapters:
        raise NoContentError("処理できるセクションがありませんでした。")

    # 合計時間を章のdurationから計算（EPUB3仕様: 合計 = 各章のdurationの合計）
    total_duration = sum(ch.duration for ch in all_chapters)

    # nav.xhtml の生成（階層構造）
    nav_content = generate_nav_xhtml_hierarchical(book_title, all_chapters, lang=epub_lang)
    with open(oebps / "text/nav.xhtml", "w", encoding="utf-8") as f:
        f.write(nav_content)

    # OPF (パッケージドキュメント) の生成
    # 複数ファイルの場合は音声ファイルも複数あるので、generate_opf_commonmark_multiを使用
    opf_content = generate_opf_commonmark_multi(
        book_title, all_chapters, total_duration,
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
    logger.info(msg("epub_file_count_done", count=len(adapters)))
    logger.info(msg("epub_section_count_done", count=len(all_chapters)))
    logger.info(msg("epub_duration", duration=total_duration))
