"""
音声生成パイプラインモジュール。

テキスト→WAV→MP3→TextGridの変換パイプラインを提供します。
言語に応じてVOICEVOXまたはmacOS sayを使用して音声を生成します。
"""
from core import logger
from core.config import PRIMARY_SOUND_RATE, LanguageConfig
from audio.tts import (
    gen_sound_file,
    convert_wav_to_mp3,
    get_user_dict,
    add_user_dict_word,
    generate_audio,
)
from audio.textgrid.generator import generate_textgrid_from_files_auto
from parsers.source_adapter import SourceAdapter

# VOICEVOXユーザー辞書に登録する単語（surface, pronunciation）
VOICEVOX_DICT_WORDS = [
    ("①", "イチ"),
    ("②", "ニ"),
    ("③", "サン"),
    ("④", "ヨン"),
    ("⑤", "ゴ"),
    ("⑥", "ロク"),
    ("⑦", "ナナ"),
    ("⑧", "ハチ"),
    ("⑨", "キュウ"),
    ("Ⅰ", "イチ"),
    ("Ⅱ", "ニ"),
    ("Ⅲ", "サン"),
    ("Ⅳ", "ヨン"),
    ("Ⅴ", "ゴ"),
    ("Ⅵ", "ロク"),
    ("Ⅶ", "ナナ"),
    ("Ⅷ", "ハチ"),
    ("Ⅸ", "キュウ"),
    ("Ⅹ", "ジュウ"),
    ("ⓐ", "エイ"),
    ("ⓑ", "ビイ"),
    ("ⓒ", "シイ"),
    ("ⓓ", "ディー"),
    ("ⓔ", "イー"),
    ("ⓕ", "エフ"),
    ("〜", "カラ"),
    ("～", "カラ")
]


def _ensure_voicevox_dict() -> None:
    """VOICEVOXユーザー辞書に必要な単語が登録されているか確認し、なければ追加する。"""
    try:
        current_dict = get_user_dict()
        # 現在登録されているsurfaceを取得
        registered_surfaces = {word_info['surface'] for word_info in current_dict.values()}

        for surface, pronunciation in VOICEVOX_DICT_WORDS:
            if surface not in registered_surfaces:
                add_user_dict_word(surface, pronunciation)
                logger.debug(f"  辞書登録: {surface} → {pronunciation}")
    except Exception as e:
        logger.warning(f"VOICEVOXユーザー辞書の確認に失敗しました: {e}")


def generate_audio_with_textgrid(
        adapter: SourceAdapter,
        reading_text_path: str,
        wav_path: str,
        mp3_path: str,
        rate: int = PRIMARY_SOUND_RATE,
        lang_config: LanguageConfig | None = None
) -> None:
    """
    音声生成パイプラインを実行する。

    ソースファイルから読み上げテキストを生成し、言語に応じたTTSエンジンで
    音声ファイルを作成、MP3に変換後、TextGridを生成します。

    Parameters
    ----------
    adapter : SourceAdapter
        入力ソースのアダプター。
    reading_text_path : str
        読み上げ用テキストファイルの出力パス。
    wav_path : str
        WAV音声ファイルの出力パス。
    mp3_path : str
        MP3音声ファイルの出力パス。
    rate : int, optional
        読み上げ速度（パーセント）。デフォルトはPRIMARY_SOUND_RATE。
        VOICEVOXのみで使用。
    lang_config : LanguageConfig | None, optional
        言語設定。Noneの場合はデフォルト（日本語/VOICEVOX）を使用。

    Raises
    ------
    FileNotFoundError_
        入力ファイルが存在しない場合。
    AudioGenerationError
        音声生成に失敗した場合。
    ConversionError
        MP3変換に失敗した場合。
    TextGridError
        TextGrid生成に失敗した場合。
    """
    # 1. 読み上げ用テキストを生成
    adapter.generate_reading_text(reading_text_path)

    # 2. 言語に応じた音声生成
    if lang_config is None or lang_config.tts_engine == "voicevox":
        # VOICEVOXの場合：ユーザー辞書を確認・登録してから音声生成
        _ensure_voicevox_dict()
        gen_sound_file(reading_text_path, wav_path, rate)
    else:
        # その他のTTSエンジン（sayなど）
        generate_audio(reading_text_path, wav_path, lang_config)

    # 3. WAVをMP3に変換
    convert_wav_to_mp3(wav_path, mp3_path)

    # 4. TextGridを生成（言語に応じたMFAモデルを使用）
    generate_textgrid_from_files_auto(reading_text_path, mp3_path, lang_config)
