"""
EPUB生成処理用のカスタム例外クラス。

処理パイプラインの各段階で発生するエラーを明確に分類し、
適切なエラーハンドリングを可能にします。
"""
from core.messages import msg


class EpubGenerationError(Exception):
    """EPUB生成処理の基底例外クラス。"""
    pass


class FileNotFoundError_(EpubGenerationError):
    """必要なファイルが見つからない場合の例外。"""

    def __init__(self, file_path: str, file_type: str = ""):
        self.file_path = file_path
        self.file_type = file_type
        super().__init__(msg("exception_file_not_found", file_type=file_type, file_path=file_path))


class AudioGenerationError(EpubGenerationError):
    """音声ファイル生成時のエラー。"""

    def __init__(self, message: str, source_file: str = ""):
        self.source_file = source_file
        super().__init__(message)


class TextGridError(EpubGenerationError):
    """TextGrid生成・処理時のエラー。"""

    def __init__(self, message: str, textgrid_path: str = ""):
        self.textgrid_path = textgrid_path
        super().__init__(message)


class ConversionError(EpubGenerationError):
    """ファイル形式変換時のエラー（AIFF→MP3、XML→XHTMLなど）。"""

    def __init__(self, message: str, input_file: str = "", output_file: str = ""):
        self.input_file = input_file
        self.output_file = output_file
        super().__init__(message)


class SourceParsingError(EpubGenerationError):
    """入力ソース（テキスト/XML）のパースエラー。"""

    def __init__(self, message: str, source_file: str = ""):
        self.source_file = source_file
        super().__init__(message)


class NoContentError(EpubGenerationError):
    """処理対象のコンテンツが存在しない場合のエラー。"""

    def __init__(self, message: str):
        super().__init__(message)
