"""
EPUB生成ツールのメインモジュール。

テキスト/XML/CommonMarkファイルからMedia Overlay付きEPUB3を生成する。
"""
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from core import logger
from core.messages import msg, set_ui_language
from core.config import (
    AUDIO_BASE_NAME,
    PRIMARY_SOUND_SUFFIX,
    SECONDARY_SOUND_SUFFIX,
    LANGUAGE_CONFIGS,
    get_language_config,
    LanguageConfig,
)
from core.exceptions import EpubGenerationError
from core.metadata_reader import (
    load_metadata_for_single_file,
    load_metadata_for_folder,
    MetadataFileNotFoundError,
    MetadataTitleMissingError,
)
from audio.pipeline import generate_audio_with_textgrid
from epub.builder import build_complete_epub
from epub.builder_multi import build_multi_epub
from epub.builder_commonmark import build_commonmark_epub, build_commonmark_multi_epub
from parsers.commonmark import get_book_title
from parsers.source_adapter import SourceAdapter, CommonMarkSourceAdapter


# =============================================================================
# 列挙型
# =============================================================================

class InputFormat(Enum):
    """入力形式を表す列挙型。"""
    COMMONMARK_EXT = "commonmark_ext"
    XML = "xml"

    @property
    def display_name(self) -> str:
        """表示名を返す。"""
        names = {
            InputFormat.COMMONMARK_EXT: msg("display_commonmark"),
            InputFormat.XML: "XML",
        }
        return names[self]

    @property
    def file_type_name(self) -> str:
        """ファイルタイプ名を返す（処理モード選択用）。"""
        names = {
            InputFormat.COMMONMARK_EXT: msg("display_commonmark"),
            InputFormat.XML: "XML",
        }
        return names[self]

    @property
    def file_extension(self) -> str:
        """ファイル拡張子を返す。"""
        extensions = {
            InputFormat.COMMONMARK_EXT: ".txt/.md",
            InputFormat.XML: ".xml",
        }
        return extensions[self]

    @property
    def glob_pattern(self) -> str:
        """globパターンを返す。"""
        patterns = {
            InputFormat.COMMONMARK_EXT: "*.txt",  # .mdは別途追加
            InputFormat.XML: "*.xml",
        }
        return patterns[self]


class ProcessingMode(Enum):
    """処理モードを表す列挙型。"""
    SINGLE_FILE = "single"
    FOLDER = "folder"


# =============================================================================
# 定数
# =============================================================================

# 作業用ファイル名（予約済み）
RESERVED_FILENAMES: set[str] = {
    f"{AUDIO_BASE_NAME}.txt",
    f"{AUDIO_BASE_NAME}{PRIMARY_SOUND_SUFFIX}",
    f"{AUDIO_BASE_NAME}{SECONDARY_SOUND_SUFFIX}",
    f"{AUDIO_BASE_NAME}.TextGrid",
}

# 中間ファイル（単一ファイル処理用）
INTERMEDIATE_FILES_SINGLE: list[Path] = [
    Path("META-INF"),
    Path("OEBPS"),
    Path(f"{AUDIO_BASE_NAME}.txt"),
    Path(f"{AUDIO_BASE_NAME}{PRIMARY_SOUND_SUFFIX}"),
    Path(f"{AUDIO_BASE_NAME}{SECONDARY_SOUND_SUFFIX}"),
    Path(f"{AUDIO_BASE_NAME}.TextGrid"),
]

# 中間ファイル（複数ファイル処理用）
INTERMEDIATE_FILES_MULTI: list[Path] = [
    Path("META-INF"),
    Path("OEBPS"),
    Path("work_multi"),
]


# =============================================================================
# データクラス
# =============================================================================

@dataclass
class ProcessingContext:
    """処理コンテキストを保持するデータクラス。"""
    start_time: datetime
    timestamp_str: str
    output_dir: Path
    output_epub: str
    epub_lang: str
    keep_intermediate: bool

    @classmethod
    def create(
        cls,
        source_path: Path,
        lang_config: LanguageConfig | None,
        keep_intermediate: bool,
        is_folder: bool = False,
        mode_string: str = ""
    ) -> "ProcessingContext":
        """処理コンテキストを生成する。"""
        start_time = datetime.now()
        timestamp_str = start_time.strftime("%Y%m%d%H%M%S")

        if is_folder:
            output_dir = source_path.parent
            epub_name = f"{source_path.name}_{mode_string}_{timestamp_str}.epub"
        else:
            output_dir = source_path.parent
            epub_name = f"{source_path.stem}_{mode_string}_{timestamp_str}.epub"

        return cls(
            start_time=start_time,
            timestamp_str=timestamp_str,
            output_dir=output_dir,
            output_epub=str(output_dir / epub_name),
            epub_lang=lang_config.epub_lang if lang_config else "ja",
            keep_intermediate=keep_intermediate,
        )


# =============================================================================
# ユーティリティ関数
# =============================================================================

def natural_sort_key(path: Path) -> list:
    """
    自然順ソートのためのキー関数。

    ファイル名内の数字を数値として扱い、人間が期待する順序でソートする。
    例: file1, file2, file10 → file1, file2, file10 (文字列だと file1, file10, file2)
    """
    def convert(text: str):
        return int(text) if text.isdigit() else text.lower()
    return [convert(c) for c in re.split(r'(\d+)', path.name)]


def _log_processing_start(start_time: datetime) -> None:
    """処理開始ログを出力する。"""
    logger.info(msg("processing_start", time=start_time.strftime('%Y-%m-%d %H:%M:%S')))


def _log_processing_end(ctx: ProcessingContext) -> None:
    """処理終了ログを出力する。"""
    end_time = datetime.now()
    elapsed_time = end_time - ctx.start_time
    logger.separator("=", 50)
    logger.info(msg("processing_end", time=end_time.strftime('%Y-%m-%d %H:%M:%S')))
    logger.info(msg("elapsed_time", time=elapsed_time))
    logger.info(msg("output_file", path=ctx.output_epub))


# =============================================================================
# バリデーション関数
# =============================================================================

def _validate_file_exists(file_path: Path) -> None:
    """ファイルの存在をチェックする。"""
    if not file_path.exists():
        raise EpubGenerationError(msg("file_not_found", path=file_path))


def _validate_folder_exists(folder_path: Path) -> None:
    """フォルダの存在をチェックする。"""
    if not folder_path.exists() or not folder_path.is_dir():
        raise EpubGenerationError(msg("folder_not_found", path=folder_path))


def _validate_not_reserved(filename: str) -> None:
    """作業用ファイル名との衝突をチェックする。"""
    if filename in RESERVED_FILENAMES:
        raise EpubGenerationError(msg("reserved_filename", name=filename))


def _validate_no_reserved_files(files: list[Path]) -> None:
    """ファイルリスト内に予約済みファイル名がないかチェックする。"""
    reserved = [f for f in files if f.name in RESERVED_FILENAMES]
    if reserved:
        names = ", ".join(f.name for f in reserved)
        raise EpubGenerationError(msg("reserved_filenames_in_list", names=names))


# =============================================================================
# 中間ファイル処理
# =============================================================================

def _handle_intermediate_files(
    output_dir: Path,
    keep: bool,
    items: list[Path]
) -> None:
    """
    中間ファイルを処理する（保存または削除）。

    Parameters
    ----------
    output_dir : Path
        出力先ディレクトリ
    keep : bool
        残す場合はTrue
    items : list[Path]
        処理対象の中間ファイル/フォルダのリスト
    """
    if keep:
        intermediate_dir = output_dir / "intermediate_products"
        if intermediate_dir.exists():
            shutil.rmtree(intermediate_dir)
        intermediate_dir.mkdir()

        for item in items:
            if item.exists():
                shutil.move(str(item), str(intermediate_dir / item.name))
        logger.info(msg("intermediate_saved", path=intermediate_dir))
    else:
        for item in items:
            if item.exists():
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()


# =============================================================================
# UI入力ヘルパー関数
# =============================================================================

def _prompt_choice(
    prompt: str,
    options: list[str],
    default: int = 1
) -> int:
    """
    選択肢を表示してユーザー入力を取得する。

    Parameters
    ----------
    prompt : str
        質問文
    options : list[str]
        選択肢のリスト
    default : int
        デフォルト値（1始まり）

    Returns
    -------
    int
        選択されたインデックス（1始まり）
    """
    print(prompt)
    for i, option in enumerate(options, 1):
        print(f"  {i}: {option}")
    logger.separator("-")

    choice = input(msg("choice_prompt", n=len(options), d=default)).strip()

    if not choice:
        return default

    try:
        value = int(choice)
        if 1 <= value <= len(options):
            return value
        print(msg("invalid_value", n=len(options), d=default))
    except ValueError:
        print(msg("invalid_input", n=len(options), d=default))

    return default


def _prompt_language() -> tuple[LanguageConfig, int]:
    """言語選択を行う。"""
    print(msg("select_language"))
    lang_options = list(LANGUAGE_CONFIGS.keys())

    for i, lang_code in enumerate(lang_options, 1):
        config = LANGUAGE_CONFIGS[lang_code]
        print(f"  {i}: {config.display_name} ({lang_code})")
    logger.separator("-")

    choice = input(msg("language_prompt", n=len(lang_options))).strip()

    try:
        index = int(choice) - 1 if choice else 0
        if not (0 <= index < len(lang_options)):
            index = 0
        lang_config = get_language_config(lang_options[index])
        set_ui_language(lang_config.code)
        logger.info(msg("selected_language", name=lang_config.display_name))
        return lang_config, index + 1
    except ValueError:
        lang_config = get_language_config("ja_JP")
        set_ui_language(lang_config.code)
        logger.info(msg("default_language", name=lang_config.display_name))
        return lang_config, 1


def _prompt_input_format() -> tuple[InputFormat, int]:
    """入力形式選択を行う。"""
    options = [
        msg("opt_commonmark"),
        msg("opt_xml"),
    ]
    choice = _prompt_choice(msg("select_input_format"), options, default=1)

    format_map = {
        1: InputFormat.COMMONMARK_EXT,
        2: InputFormat.XML,
    }
    return format_map.get(choice, InputFormat.COMMONMARK_EXT), choice


def _get_highlight_mode(input_format: InputFormat) -> str:
    """入力形式に応じてハイライトモードを取得する。"""
    # すべての形式で句読点モード固定
    logger.info(msg("highlight_fixed"))
    logger.separator("-")
    return "punctuation"


def _prompt_processing_mode(file_type: str) -> tuple[ProcessingMode, int]:
    """処理モード選択を行う。"""
    options = [
        msg("opt_single", type=file_type),
        msg("opt_folder", type=file_type),
    ]
    choice = _prompt_choice(msg("select_processing_mode"), options, default=1)

    mode = ProcessingMode.SINGLE_FILE if choice == 1 else ProcessingMode.FOLDER
    return mode, choice


def _prompt_source_path(file_type: str, file_ext: str, is_folder: bool) -> str:
    """ソースパス入力を行う。"""
    logger.separator("-")
    if is_folder:
        return input(msg("prompt_folder_path", type=file_type))
    else:
        return input(msg("prompt_file_path", type=file_type, ext=file_ext))


def _prompt_keep_intermediate(output_dir: Path) -> bool:
    """中間ファイル保存の選択を行う。"""
    intermediate_dir = output_dir / "intermediate_products"
    logger.separator("-")
    print(msg("keep_intermediate_question"))
    print(f"  {msg('keep_intermediate_dest', path=intermediate_dir)}")

    options = [msg("opt_keep_no"), msg("opt_keep_yes")]
    choice = _prompt_choice("", options, default=1)
    return choice == 2


# =============================================================================
# 作業用フォルダ管理
# =============================================================================

def _setup_work_directory() -> tuple[Path, Path, Path]:
    """
    作業用フォルダを作成する。

    Returns
    -------
    tuple[Path, Path, Path]
        (work_dir, textgrid_folder, audio_folder)
    """
    work_dir = Path("work_multi")
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir()

    textgrid_folder = work_dir / "textgrid"
    audio_folder = work_dir / "audio"
    textgrid_folder.mkdir()
    audio_folder.mkdir()

    return work_dir, textgrid_folder, audio_folder


# =============================================================================
# 処理関数
# =============================================================================

def process_single_file(
    source_file: str,
    highlight_mode: str,
    is_xml: bool,
    lang_config: LanguageConfig | None,
    keep_intermediate: bool,
    mode_string: str = ""
) -> None:
    """単一ファイル（テキストまたはXML）からEPUBを生成する。"""
    source_path = Path(source_file)

    # バリデーション
    _validate_file_exists(source_path)
    _validate_not_reserved(source_path.name)

    # コンテキスト生成
    ctx = ProcessingContext.create(source_path, lang_config, keep_intermediate, mode_string=mode_string)
    _log_processing_start(ctx.start_time)

    # メタデータとアダプター
    metadata = load_metadata_for_single_file(source_file)
    adapter = SourceAdapter.create(source_file, is_xml)

    # 音声生成
    audio_txt = f"{AUDIO_BASE_NAME}.txt"
    wav_file = f"{AUDIO_BASE_NAME}{PRIMARY_SOUND_SUFFIX}"
    mp3_file = f"{AUDIO_BASE_NAME}{SECONDARY_SOUND_SUFFIX}"

    logger.info(msg("audio_start", file=source_file))
    generate_audio_with_textgrid(adapter, audio_txt, wav_file, mp3_file, lang_config=lang_config)

    # EPUB生成
    build_complete_epub(
        metadata.title,
        adapter,
        highlight_mode,
        metadata=metadata,
        output_epub=ctx.output_epub,
        epub_lang=ctx.epub_lang
    )

    # 後処理
    _handle_intermediate_files(ctx.output_dir, ctx.keep_intermediate, INTERMEDIATE_FILES_SINGLE)
    _log_processing_end(ctx)


def process_folder(
    source_folder: str,
    highlight_mode: str,
    is_xml: bool,
    lang_config: LanguageConfig | None,
    keep_intermediate: bool,
    mode_string: str = ""
) -> None:
    """フォルダ内の複数ファイル（テキストまたはXML）からEPUBを生成する。"""
    folder_path = Path(source_folder)

    # バリデーション
    _validate_folder_exists(folder_path)

    # コンテキスト生成
    ctx = ProcessingContext.create(folder_path, lang_config, keep_intermediate, is_folder=True, mode_string=mode_string)
    _log_processing_start(ctx.start_time)

    # メタデータ
    metadata = load_metadata_for_folder(source_folder)

    # ソースファイル収集
    file_ext = "*.xml" if is_xml else "*.txt"
    source_files = sorted(folder_path.glob(file_ext), key=natural_sort_key)

    if not source_files:
        raise EpubGenerationError(msg("no_files_in_folder", folder=source_folder, ext=file_ext))

    _validate_no_reserved_files(source_files)
    logger.info(msg("file_count", count=len(source_files), ext=file_ext))

    # 作業用フォルダ
    work_dir, textgrid_folder, audio_folder = _setup_work_directory()

    # 各ファイル処理
    adapters: list[SourceAdapter] = []
    for src_file in source_files:
        base_name = src_file.stem
        logger.separator("=", 50)
        logger.info(msg("processing_file", name=src_file.name))

        adapter = SourceAdapter.create(str(src_file), is_xml)
        adapters.append(adapter)

        work_txt = work_dir / f"{base_name}.txt"
        work_wav = work_dir / f"{base_name}.wav"
        work_mp3 = audio_folder / f"{base_name}.mp3"

        generate_audio_with_textgrid(adapter, str(work_txt), str(work_wav), str(work_mp3), lang_config=lang_config)

        # TextGrid移動、WAV削除
        tg_src = audio_folder / f"{base_name}.TextGrid"
        if tg_src.exists():
            shutil.move(tg_src, textgrid_folder / f"{base_name}.TextGrid")
        if work_wav.exists():
            work_wav.unlink()

    # EPUB生成
    build_multi_epub(
        book_title=metadata.title,
        adapters=adapters,
        output_epub=ctx.output_epub,
        textgrid_folder=textgrid_folder,
        audio_folder=audio_folder,
        highlight_mode=highlight_mode,
        metadata=metadata,
        epub_lang=ctx.epub_lang
    )

    # 後処理
    _handle_intermediate_files(ctx.output_dir, ctx.keep_intermediate, INTERMEDIATE_FILES_MULTI)
    _log_processing_end(ctx)


def process_commonmark_file(
    source_file: str,
    highlight_mode: str,
    lang_config: LanguageConfig | None,
    keep_intermediate: bool,
    mode_string: str = ""
) -> None:
    """CommonMarkファイルからEPUBを生成する。"""
    source_path = Path(source_file)

    # バリデーション
    _validate_file_exists(source_path)
    _validate_not_reserved(source_path.name)

    # コンテキスト生成
    ctx = ProcessingContext.create(source_path, lang_config, keep_intermediate, mode_string=mode_string)
    _log_processing_start(ctx.start_time)

    # メタデータとアダプター
    metadata = load_metadata_for_single_file(source_file)
    adapter = CommonMarkSourceAdapter(source_file)

    # 書籍タイトル
    if adapter.has_headings():
        book_title = get_book_title(adapter.get_heading_hierarchy())
    else:
        book_title = metadata.title if metadata else "Untitled"

    # 音声生成
    audio_txt = f"{AUDIO_BASE_NAME}.txt"
    wav_file = f"{AUDIO_BASE_NAME}{PRIMARY_SOUND_SUFFIX}"
    mp3_file = f"{AUDIO_BASE_NAME}{SECONDARY_SOUND_SUFFIX}"
    textgrid_file = Path(f"{AUDIO_BASE_NAME}.TextGrid")

    logger.info(msg("audio_start", file=source_file))
    generate_audio_with_textgrid(adapter, audio_txt, wav_file, mp3_file, lang_config=lang_config)

    # EPUB生成
    build_commonmark_epub(
        book_title=book_title,
        adapter=adapter,
        output_epub=ctx.output_epub,
        textgrid_path=textgrid_file,
        audio_path=Path(mp3_file),
        highlight_mode=highlight_mode,
        metadata=metadata,
        epub_lang=ctx.epub_lang
    )

    # 後処理
    _handle_intermediate_files(ctx.output_dir, ctx.keep_intermediate, INTERMEDIATE_FILES_SINGLE)
    _log_processing_end(ctx)


def process_commonmark_folder(
    source_folder: str,
    highlight_mode: str,
    lang_config: LanguageConfig | None,
    keep_intermediate: bool,
    mode_string: str = ""
) -> None:
    """フォルダ内の複数CommonMarkファイルからEPUBを生成する。"""
    folder_path = Path(source_folder)

    # バリデーション
    _validate_folder_exists(folder_path)

    # コンテキスト生成
    ctx = ProcessingContext.create(folder_path, lang_config, keep_intermediate, is_folder=True, mode_string=mode_string)
    _log_processing_start(ctx.start_time)

    # メタデータ
    metadata = load_metadata_for_folder(source_folder)

    # ソースファイル収集（.txt と .md）
    txt_files = list(folder_path.glob("*.txt"))
    md_files = list(folder_path.glob("*.md"))
    source_files = sorted(set(txt_files + md_files), key=natural_sort_key)

    if not source_files:
        raise EpubGenerationError(msg("no_commonmark_in_folder", folder=source_folder))

    _validate_no_reserved_files(source_files)
    logger.info(msg("file_count_commonmark", count=len(source_files)))

    # 作業用フォルダ
    work_dir, textgrid_folder, audio_folder = _setup_work_directory()

    # 各ファイル処理
    adapters: list[CommonMarkSourceAdapter] = []
    for src_file in source_files:
        base_name = src_file.stem
        logger.separator("=", 50)
        logger.info(msg("processing_file", name=src_file.name))

        adapter = CommonMarkSourceAdapter(str(src_file))
        adapters.append(adapter)

        work_txt = work_dir / f"{base_name}.txt"
        work_wav = work_dir / f"{base_name}.wav"
        work_mp3 = audio_folder / f"{base_name}.mp3"

        generate_audio_with_textgrid(adapter, str(work_txt), str(work_wav), str(work_mp3), lang_config=lang_config)

        # TextGrid移動、WAV削除
        tg_src = audio_folder / f"{base_name}.TextGrid"
        if tg_src.exists():
            shutil.move(tg_src, textgrid_folder / f"{base_name}.TextGrid")
        if work_wav.exists():
            work_wav.unlink()

    # EPUB生成
    build_commonmark_multi_epub(
        book_title=metadata.title,
        adapters=adapters,
        output_epub=ctx.output_epub,
        textgrid_folder=textgrid_folder,
        audio_folder=audio_folder,
        highlight_mode=highlight_mode,
        metadata=metadata,
        epub_lang=ctx.epub_lang
    )

    # 後処理
    _handle_intermediate_files(ctx.output_dir, ctx.keep_intermediate, INTERMEDIATE_FILES_MULTI)
    _log_processing_end(ctx)


# =============================================================================
# メイン関数
# =============================================================================

def _execute_processing(
    input_format: InputFormat,
    processing_mode: ProcessingMode,
    highlight_mode: str,
    lang_config: LanguageConfig,
    mode_string: str = ""
) -> None:
    """入力形式と処理モードに応じて処理を実行する。"""
    is_folder = processing_mode == ProcessingMode.FOLDER
    file_type = input_format.file_type_name
    file_ext = input_format.file_extension

    # ソースパス取得（引用符付き入力への対応: "path" や 'path' をトリム）
    source = _prompt_source_path(file_type, file_ext, is_folder=is_folder)
    source = source.strip().strip('"').strip("'")
    keep = _prompt_keep_intermediate(Path(source).parent)

    # 入力形式と処理モードに応じた処理を実行
    if input_format == InputFormat.COMMONMARK_EXT:
        if is_folder:
            process_commonmark_folder(source, highlight_mode, lang_config, keep, mode_string=mode_string)
        else:
            process_commonmark_file(source, highlight_mode, lang_config, keep, mode_string=mode_string)
    else:  # XML
        if is_folder:
            process_folder(source, highlight_mode, is_xml=True, lang_config=lang_config, keep_intermediate=keep, mode_string=mode_string)
        else:
            process_single_file(source, highlight_mode, is_xml=True, lang_config=lang_config, keep_intermediate=keep, mode_string=mode_string)


def main() -> None:
    """EPUB生成ツールのメイン処理。"""
    logger.separator("=")
    print(msg("tool_title"))
    logger.separator("=")

    # 言語選択
    lang_config, lang_choice = _prompt_language()
    logger.separator("-")

    # 入力形式選択
    input_format, format_choice = _prompt_input_format()
    logger.separator("-")

    # ハイライトモード選択（入力形式に応じて）
    highlight_mode = _get_highlight_mode(input_format)

    # 処理モード選択
    processing_mode, mode_choice = _prompt_processing_mode(input_format.file_type_name)

    # モード文字列構築（選択番号の連結）
    mode_string = f"{lang_choice}{format_choice}{mode_choice}"

    try:
        _execute_processing(input_format, processing_mode, highlight_mode, lang_config, mode_string=mode_string)
    except (MetadataFileNotFoundError, MetadataTitleMissingError) as e:
        logger.error(str(e))
    except EpubGenerationError as e:
        logger.error(str(e))
        print(msg("processing_aborted"))


if __name__ == "__main__":
    main()
