"""
ロギングユーティリティモジュール。

アプリケーション全体で一貫したログ出力を提供します。
"""
import io
import logging
import sys
from enum import IntEnum

from core.messages import msg


class LogLevel(IntEnum):
    """ログレベル定義。"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR


# Windows cp932 環境でのUnicodeEncodeError対策
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# アプリケーション用のロガーを作成
_logger = logging.getLogger("KERT")
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(message)s"))
_logger.addHandler(_handler)
_logger.setLevel(logging.INFO)


def set_log_level(level: LogLevel) -> None:
    """ログレベルを設定する。"""
    _logger.setLevel(level)


def debug(message: str) -> None:
    """デバッグメッセージを出力する。"""
    _logger.debug(message)


def info(message: str) -> None:
    """情報メッセージを出力する。"""
    _logger.info(message)


def warning(message: str) -> None:
    """警告メッセージを出力する。"""
    _logger.warning(msg("log_warning", message=message))


def error(message: str) -> None:
    """エラーメッセージを出力する。"""
    _logger.error(f"❌ {message}")


def success(message: str) -> None:
    """成功メッセージを出力する。"""
    _logger.info(f"✅ {msg('log_success', message=message)}")


def section(title: str) -> None:
    """セクション見出しを出力する。"""
    _logger.info("-" * 30)
    _logger.info(f"★{title}")


def separator(char: str = "=", length: int = 60) -> None:
    """区切り線を出力する。"""
    _logger.info(char * length)


def progress(current: int, total: int, message: str = "") -> None:
    """進捗状況を出力する（改行なし）。"""
    print(f"  {msg('log_progress', message=message, current=current, total=total)}", end='\r', flush=True)


def progress_done() -> None:
    """進捗表示の終了（改行を出力）。"""
    print()
