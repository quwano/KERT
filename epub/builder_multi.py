"""
複数テキストファイルからMedia Overlay付きEPUB3を生成するモジュール。

フォルダ内の複数テキストファイルを処理し、nav.xhtml（目次）付きの
EPUB3電子書籍を生成します。各テキストファイルの1行目が目次項目として使用されます。
"""
import shutil
from pathlib import Path
from html import escape
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
    generate_nav_xhtml,
    generate_nav_xhtml_hierarchical,
    generate_opf_multi_chapter,
    generate_opf_commonmark_multi,
)
from audio.textgrid.matcher import process_paragraph
from parsers.source_adapter import SourceAdapter

if TYPE_CHECKING:
    from core.metadata_reader import BookMetadata


def build_chapter_xhtml_and_smil(
    chapter_id: str,
    title: str,
    paragraphs: list[str],
    textgrid_path: Path,
    audio_filename: str,
    span_id_start: int = 0,
    highlight_mode: str = "word",
    is_xml: bool = False,
    lang: str | None = None
) -> tuple[str, str, int, float]:
    """
    単一チャプターのXHTMLとSMILコンテンツを生成する。

    タイトル（h1）と本文段落をTextGridのタイミング情報とマッチングし、
    XHTML/SMILを生成します。

    Parameters
    ----------
    chapter_id : str
        チャプターID。例: "chapter1"
    title : str
        チャプターのタイトル（h1見出しとして使用）。
    paragraphs : list[str]
        本文段落のリスト。
    textgrid_path : Path
        TextGridファイルのパス。
    audio_filename : str
        音声ファイル名。例: "chapter1.mp3"
    span_id_start : int, optional
        span IDの開始番号。デフォルトは0。
    highlight_mode : str
        ハイライトモード。"word"（単語単位）または"punctuation"（句読点単位）。

    Returns
    -------
    tuple[str, str, int, float]
        - xhtml_content : str
            生成されたXHTMLコンテンツ。
        - smil_content : str
            生成されたSMILコンテンツ。
        - next_span_id : int
            次に使用すべきspan ID番号。
        - duration : float
            音声の総再生時間（秒）。

    Notes
    -----
    TextGridファイルには、タイトルと本文の両方のタイミング情報が
    連続して含まれている必要があります。
    """
    # TextGridからタイミング情報を取得
    tg_intervals, total_sec = extract_textgrid_intervals(textgrid_path)

    xhtml_paragraphs: list[str] = []
    smil_pars: list[str] = []
    span_id: int = span_id_start
    tg_index: int = 0

    # パス設定
    xhtml_path = f"../text/{chapter_id}.xhtml"
    audio_path = f"../audio/{audio_filename}"
    element_prefix = f"{chapter_id}_w"

    # タイトル（見出し）の処理
    # タイトルはh1内に入れるため、<p>タグなしでコンテンツを生成
    title_p, title_smil, span_id, tg_index = process_paragraph(
        title, tg_intervals, tg_index, span_id,
        element_prefix, xhtml_path, audio_path,
        highlight_mode=highlight_mode,
        is_xml=is_xml
    )
    smil_pars.extend(title_smil)

    # h1_content: <p>タグを除去してh1用のコンテンツを取得
    if title_p:
        # process_paragraphは "        <p>content</p>" 形式で返すので、
        # 先頭の空白と<p>タグを除去
        h1_content = title_p.strip()
        if h1_content.startswith("<p>") and h1_content.endswith("</p>"):
            h1_content = h1_content[3:-4]
    else:
        h1_content = escape(title) if not is_xml else title

    # 本文段落の処理
    for paragraph in paragraphs:
        para_p, para_smil, span_id, tg_index = process_paragraph(
            paragraph, tg_intervals, tg_index, span_id,
            element_prefix, xhtml_path, audio_path,
            highlight_mode=highlight_mode,
            is_xml=is_xml
        )
        smil_pars.extend(para_smil)

        if para_p:
            xhtml_paragraphs.append(para_p)

    # XHTML生成
    xhtml_content = generate_xhtml_chapter(
        title=title,
        paragraphs=xhtml_paragraphs,
        h1_content=h1_content,
        lang=lang
    )

    # SMIL生成
    smil_content = generate_smil_document(
        chapter_id=chapter_id,
        smil_pars=smil_pars,
        xhtml_path=f"../text/{chapter_id}.xhtml"
    )

    return xhtml_content, smil_content, span_id, total_sec


def _build_multi_xml_sections_epub(
    book_title: str,
    adapters: list[SourceAdapter],
    output_epub: str,
    textgrid_folder: Path,
    audio_folder: Path,
    highlight_mode: str,
    metadata: "BookMetadata | None",
    epub_lang: str | None,
    oebps: Path,
    meta_inf: Path,
    image_filenames: list[str]
) -> None:
    """
    複数XMLファイルのセクション構造をサポートするEPUB生成。

    各ファイルのtitle1-title5セクションを個別XHTMLに分割し、
    階層的nav.xhtmlを生成する。
    """
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
            chapter_id = f"{file_prefix}_chapter{section_idx}"
            xhtml_path = f"../text/{chapter_id}.xhtml"
            audio_path_rel = f"../audio/{audio_filename}"
            element_prefix = f"{chapter_id}_w"

            smil_pars: list[str] = []
            xhtml_paragraphs: list[str] = []

            # セクション開始時間を記録
            start_time = tg_intervals[tg_index][1] if tg_index < len(tg_intervals) else 0.0

            # 見出しの処理（XSLT由来のspan付きXHTML）
            if section.title_xhtml:
                heading_p, heading_smil, span_id, tg_index = process_paragraph(
                    section.title_xhtml, tg_intervals, tg_index, span_id,
                    element_prefix, xhtml_path, audio_path_rel,
                    highlight_mode=highlight_mode,
                    is_xml=True
                )
                smil_pars.extend(heading_smil)

                # 見出しのコンテンツを抽出
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
                    element_prefix, xhtml_path, audio_path_rel,
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
            all_chapters.append(chapter_info)

        logger.info(msg("epub_file_done", name=base_name))

    if not all_chapters:
        raise NoContentError("処理できるセクションがありませんでした。")

    # 合計時間
    total_duration = sum(ch.duration for ch in all_chapters)

    # nav.xhtml の生成（階層構造）
    nav_content = generate_nav_xhtml_hierarchical(book_title, all_chapters, lang=epub_lang)
    with open(oebps / "text/nav.xhtml", "w", encoding="utf-8") as f:
        f.write(nav_content)

    # OPF生成（複数音声ファイル）
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


def build_multi_epub(
    book_title: str,
    adapters: list[SourceAdapter],
    output_epub: str,
    textgrid_folder: Path,
    audio_folder: Path,
    highlight_mode: str = "word",
    metadata: "BookMetadata | None" = None,
    epub_lang: str | None = None
) -> None:
    """
    複数テキストファイルからMedia Overlay付きEPUB3を生成する。

    複数のソースアダプターを処理し、目次（nav.xhtml）付きの
    EPUB3電子書籍を生成します。

    Parameters
    ----------
    book_title : str
        書籍のタイトル。OPFメタデータとnav.xhtmlで使用されます。
    adapters : list[SourceAdapter]
        入力ソースのアダプターリスト（処理順にソート済み）。
    output_epub : str
        出力EPUBファイル名。
    textgrid_folder : Path
        TextGridファイルが格納されたフォルダ。
        各テキストファイルと同名（拡張子.TextGrid）のファイルが必要。
    audio_folder : Path
        MP3ファイルが格納されたフォルダ。
        各テキストファイルと同名（拡張子.mp3）のファイルが必要。
    highlight_mode : str
        ハイライトモード。"word"（単語単位）または"punctuation"（句読点単位）。
    metadata : BookMetadata | None
        書籍のメタデータ。Noneの場合はオプション項目を含めない。

    Returns
    -------
    None

    See Also
    --------
    build_complete_epub.build_complete_epub : 単一ファイルからEPUBを生成する場合。
    """
    if not adapters:
        raise NoContentError("処理するアダプターがありません。")

    is_xml = adapters[0].is_xml
    file_type = "XML" if is_xml else msg("file_type_text")
    logger.section(msg("multi_epub_start", file_type=file_type))
    logger.info(msg("epub_file_count_progress", count=len(adapters)))

    # フォルダ構造の作成
    oebps, meta_inf = create_epub_structure()

    # CSSファイルの作成
    write_css_file(oebps)

    # 画像ファイルの抽出とコピー（複数ファイルのときは包含フォルダを起点）
    # 包含フォルダ = adaptersの最初のファイルの親フォルダ
    base_folder = Path(adapters[0].file_path).parent
    image_filenames: list[str] = []

    for adapter in adapters:
        paragraphs = adapter.get_paragraphs()
        new_images = extract_and_copy_images(paragraphs, base_folder, oebps)
        for img in new_images:
            if img not in image_filenames:
                image_filenames.append(img)

    # XMLの場合はセクション対応の処理に分岐
    if is_xml:
        _build_multi_xml_sections_epub(
            book_title, adapters, output_epub,
            textgrid_folder, audio_folder, highlight_mode,
            metadata, epub_lang, oebps, meta_inf, image_filenames
        )
        return

    # 各チャプターの処理（非XML）
    chapters: list[ChapterInfo] = []
    total_duration: float = 0.0

    for idx, adapter in enumerate(adapters, 1):
        chapter_id = f"chapter{idx}"
        base_name = Path(adapter.file_path).stem

        # ファイルパスの構築
        textgrid_path = textgrid_folder / f"{base_name}.TextGrid"
        audio_path = audio_folder / f"{base_name}.mp3"

        if not textgrid_path.exists():
            raise FileNotFoundError_(str(textgrid_path), msg("file_type_textgrid"))
        if not audio_path.exists():
            raise FileNotFoundError_(str(audio_path), msg("file_type_audio"))

        # アダプターからデータ取得
        title = adapter.get_title_xhtml()
        paragraphs = adapter.get_body_paragraphs()
        title_text = adapter.get_title()

        # 音声ファイルのコピー
        audio_filename = f"{chapter_id}.mp3"
        shutil.copy(audio_path, oebps / "audio" / audio_filename)

        # XHTML と SMIL の生成
        xhtml_content, smil_content, _, duration = build_chapter_xhtml_and_smil(
            chapter_id, title, paragraphs, textgrid_path, audio_filename,
            highlight_mode=highlight_mode,
            is_xml=False,
            lang=epub_lang
        )

        # ファイル書き出し
        with open(oebps / "text" / f"{chapter_id}.xhtml", "w", encoding="utf-8") as f:
            f.write(xhtml_content)
        with open(oebps / "smil" / f"{chapter_id}.smil", "w", encoding="utf-8") as f:
            f.write(smil_content)

        # ChapterInfoを使用（タイトルはプレーンテキスト）
        chapter_info = ChapterInfo(
            id=chapter_id,
            title=title_text,
            duration=duration
        )
        chapters.append(chapter_info)
        total_duration += duration

        logger.info(msg("epub_chapter_done", id=chapter_id, title=title_text))

    if not chapters:
        raise NoContentError("処理できるチャプターがありませんでした。")

    # nav.xhtml の生成
    nav_content = generate_nav_xhtml(book_title, chapters, lang=epub_lang)
    with open(oebps / "text/nav.xhtml", "w", encoding="utf-8") as f:
        f.write(nav_content)

    # OPF (パッケージドキュメント) の生成
    opf_content = generate_opf_multi_chapter(
        book_title, chapters, total_duration,
        metadata=metadata,
        images=image_filenames if image_filenames else None,
        lang=epub_lang
    )
    with open(oebps / "content.opf", "w", encoding="utf-8") as f:
        f.write(opf_content)

    # container.xml 書き出し
    write_container_xml(meta_inf)

    # パッケージング (ZIP)
    package_epub(output_epub, oebps, meta_inf)

    logger.success(msg("epub_saved", file=output_epub))
    logger.info(msg("epub_chapter_count_done", count=len(chapters)))
    logger.info(msg("epub_duration", duration=total_duration))
