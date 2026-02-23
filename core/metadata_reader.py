"""
書誌情報ファイル読み取りモジュール。

メタデータファイルから書籍のメタ情報を読み取り、EPUB生成に使用します。
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from core.messages import msg


class MetadataFileNotFoundError(Exception):
    """書誌情報ファイルが見つからない場合の例外。"""

    def __init__(self, metadata_path: str):
        self.metadata_path = metadata_path
        super().__init__(msg("metadata_not_found", path=metadata_path))


class MetadataTitleMissingError(Exception):
    """書誌情報にタイトルがない場合の例外。"""

    def __init__(self):
        super().__init__(msg("metadata_no_title"))


@dataclass
class BookMetadata:
    """書籍のメタデータを保持するデータクラス。"""

    title: str  # タイトル（必須）
    contributor: str | None = None  # 協力者（オプション）
    creator: str | None = None  # 制作者（オプション）
    publisher: str | None = None  # 発行元（オプション）
    rights: str | None = None  # 権利表記（オプション）
    subject: str | None = None  # ジャンル（オプション）
    date: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    accessibility_metadata: list[tuple[str, str]] = field(default_factory=list)


# フィールド名と日本語キーのマッピング
_FIELD_MAPPING: dict[str, str] = {
    "title": "title",
    "contributor": "contributor",
    "author": "creator",
    "publisher": "publisher",
    "rights": "rights",
    "subject": "subject",
}

# アクセシビリティ関連キー（同一キーの複数値をサポート）
_ACCESSIBILITY_KEYS: set[str] = {
    "accessMode",
    "accessModeSufficient",
    "accessibilityFeature",
    "accessibilityHazard",
    "accessibilitySummary",
}


def get_metadata_path_for_single_file(source_file: str | Path) -> Path:
    """
    単一ファイル処理用のメタデータファイルパスを取得する。

    Parameters
    ----------
    source_file : str | Path
        変換元ファイルのパス（例：/path/to/foo.txt）

    Returns
    -------
    Path
        メタデータファイルのパス（例：/path/to/foo_metadata.txt）
    """
    source_path = Path(source_file)
    metadata_filename = f"{source_path.stem}_metadata.txt"
    return source_path.parent / metadata_filename


def get_metadata_path_for_folder(source_folder: str | Path) -> Path:
    """
    複数ファイル処理用のメタデータファイルパスを取得する。

    Parameters
    ----------
    source_folder : str | Path
        変換元ファイルが格納されたフォルダのパス（例：/path/to/bar）

    Returns
    -------
    Path
        メタデータファイルのパス（例：/path/to/bar_metadata.txt）
    """
    folder_path = Path(source_folder)
    metadata_filename = f"{folder_path.name}_metadata.txt"
    return folder_path.parent / metadata_filename


def parse_metadata_file(metadata_path: Path) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """
    メタデータファイルをパースして辞書とアクセシビリティメタデータリストを返す。

    Parameters
    ----------
    metadata_path : Path
        メタデータファイルのパス

    Returns
    -------
    tuple[dict[str, str], list[tuple[str, str]]]
        通常メタデータ辞書とアクセシビリティメタデータリスト

    Notes
    -----
    ファイルフォーマット:
        title: 〇〇
        contributor: 〇〇
        author: 〇〇
        publisher: 〇〇
        rights: 〇〇
        subject: 〇〇
        accessMode: textual
        accessibilityFeature: index
        accessibilityHazard: noFlashingHazard
    """
    result: dict[str, str] = {}
    accessibility: list[tuple[str, str]] = []

    with open(metadata_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # 「:」または「：」で分割（半角コロン優先）
            if ":" in line:
                key, _, value = line.partition(":")
            elif "：" in line:
                key, _, value = line.partition("：")
            else:
                continue

            key = key.strip()
            value = value.strip()

            if not value:
                continue

            if key in _ACCESSIBILITY_KEYS:
                accessibility.append((key, value))
            elif key in _FIELD_MAPPING:
                result[_FIELD_MAPPING[key]] = value

    return result, accessibility


def _load_metadata(metadata_path: Path) -> BookMetadata:
    """
    メタデータファイルを読み込む共通処理。

    Parameters
    ----------
    metadata_path : Path
        メタデータファイルのパス

    Returns
    -------
    BookMetadata
        読み込んだメタデータ

    Raises
    ------
    MetadataFileNotFoundError
        メタデータファイルが見つからない場合
    MetadataTitleMissingError
        タイトルが記載されていない場合
    """
    if not metadata_path.exists():
        raise MetadataFileNotFoundError(str(metadata_path))

    fields, accessibility = parse_metadata_file(metadata_path)

    if "title" not in fields:
        raise MetadataTitleMissingError()

    return BookMetadata(
        title=fields["title"],
        contributor=fields.get("contributor"),
        creator=fields.get("creator"),
        publisher=fields.get("publisher"),
        rights=fields.get("rights"),
        subject=fields.get("subject"),
        accessibility_metadata=accessibility,
    )


def load_metadata_for_single_file(source_file: str | Path) -> BookMetadata:
    """
    単一ファイル処理用のメタデータを読み込む。

    Parameters
    ----------
    source_file : str | Path
        変換元ファイルのパス

    Returns
    -------
    BookMetadata
        読み込んだメタデータ

    Raises
    ------
    MetadataFileNotFoundError
        メタデータファイルが見つからない場合
    MetadataTitleMissingError
        タイトルが記載されていない場合
    """
    return _load_metadata(get_metadata_path_for_single_file(source_file))


def load_metadata_for_folder(source_folder: str | Path) -> BookMetadata:
    """
    複数ファイル処理用のメタデータを読み込む。

    Parameters
    ----------
    source_folder : str | Path
        変換元ファイルが格納されたフォルダのパス

    Returns
    -------
    BookMetadata
        読み込んだメタデータ

    Raises
    ------
    MetadataFileNotFoundError
        メタデータファイルが見つからない場合
    MetadataTitleMissingError
        タイトルが記載されていない場合
    """
    return _load_metadata(get_metadata_path_for_folder(source_folder))
