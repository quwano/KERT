"""
コアモジュール。

共通の例外、ロガー、設定、メタデータ読み込みを提供する。
"""
from core.exceptions import EpubGenerationError, AudioGenerationError
from core.logger import (
    debug, info, warning, error, success, section, separator, progress, progress_done,
    set_log_level, LogLevel
)
from core.config import (
    AUDIO_BASE_NAME,
    PRIMARY_SOUND_SUFFIX,
    SECONDARY_SOUND_SUFFIX,
    LANGUAGE_CONFIGS,
    get_language_config,
    LanguageConfig,
)
from core.metadata_reader import (
    BookMetadata,
    load_metadata_for_single_file,
    load_metadata_for_folder,
    MetadataFileNotFoundError,
    MetadataTitleMissingError,
)

__all__ = [
    # exceptions
    "EpubGenerationError",
    "AudioGenerationError",
    # logger
    "debug", "info", "warning", "error", "success", "section", "separator",
    "progress", "progress_done", "set_log_level", "LogLevel",
    # config
    "AUDIO_BASE_NAME", "PRIMARY_SOUND_SUFFIX", "SECONDARY_SOUND_SUFFIX",
    "LANGUAGE_CONFIGS", "get_language_config", "LanguageConfig",
    # metadata_reader
    "BookMetadata", "load_metadata_for_single_file", "load_metadata_for_folder",
    "MetadataFileNotFoundError", "MetadataTitleMissingError",
]
