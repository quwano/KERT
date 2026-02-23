"""
EPUB3生成ツールの設定定数モジュール。

プロジェクト全体で使用される設定値を一元管理します。
"""
from dataclasses import dataclass


# --- 言語設定 ---
@dataclass
class LanguageConfig:
    """言語ごとの設定を保持するデータクラス。"""
    code: str                    # 言語コード（例: "ja", "en"）
    display_name: str            # 表示名
    epub_lang: str               # EPUB言語タグ
    mfa_dictionary: str          # MFA辞書モデル名
    mfa_acoustic: str            # MFA音響モデル名
    tts_engine: str              # TTS engine ("voicevox" or "say")
    tts_voice: str | None        # TTS音声名（sayの場合）


# 対応言語の設定
LANGUAGE_CONFIGS: dict[str, LanguageConfig] = {
    "ja_JP": LanguageConfig(
        code="ja_JP",
        display_name="日本語",
        epub_lang="ja",
        mfa_dictionary="japanese_mfa",
        mfa_acoustic="japanese_mfa",
        tts_engine="voicevox",
        tts_voice=None,
    ),
    "en_US": LanguageConfig(
        code="en_US",
        display_name="English (US)",
        epub_lang="en",
        mfa_dictionary="english_us_arpa",
        mfa_acoustic="english_us_arpa",
        tts_engine="say",
        tts_voice="Samantha",
    ),
    "de_DE": LanguageConfig(
        code="de_DE",
        display_name="Deutsch",
        epub_lang="de",
        mfa_dictionary="german_mfa",
        mfa_acoustic="german_mfa",
        tts_engine="say",
        tts_voice="Anna",
    ),
}

# デフォルト言語
DEFAULT_LANGUAGE = "ja_JP"

# EPUB3ドキュメントのデフォルト言語（後方互換性のため残す）
LANG = "ja"

# --- 句読点文字設定 ---
PUNCTUATION_CHARS = "。、．，.,!！?？"  # XSLT分割・matcher共通

# --- 音声ファイル設定 ---
AUDIO_BASE_NAME = "audio"  # 音声ファイルのベース名（MFAの要件）
PRIMARY_SOUND_SUFFIX = ".wav"  # 生成される一次音声ファイルの拡張子（VOICEVOX出力）
SECONDARY_SOUND_SUFFIX = ".mp3"  # 変換後の音声ファイルの拡張子
PRIMARY_SOUND_RATE = 100  # VOICEVOXの読み上げ速度（パーセント、100=標準）

# --- TextGrid設定 ---
INPUT_TEXTGRID = "audio.TextGrid"  # デフォルトのTextGridファイル名
SOURCE_AUDIO = "audio.mp3"  # デフォルトの音声ファイル名

# --- MFA (Montreal Forced Aligner) 設定 ---
# 以下は後方互換性のため残す（日本語デフォルト）
MFA_DICTIONARY_MODEL = "japanese_mfa"  # MFA辞書モデル名
MFA_ACOUSTIC_MODEL = "japanese_mfa"  # MFA音響モデル名
MFA_ENV_NAME = "mfa"  # Conda環境名

# --- VOICEVOX設定 ---
VOICEVOX_BASE_URL = "http://localhost:50021"  # VOICEVOXエンジンのベースURL
DEFAULT_SPEAKER_ID = 109  # デフォルトのスピーカーID（109 = 東北イタコ）


def get_language_config(lang_code: str) -> LanguageConfig:
    """言語コードから設定を取得する。

    Parameters
    ----------
    lang_code : str
        言語コード（例: "ja_JP", "en_US"）

    Returns
    -------
    LanguageConfig
        言語設定

    Raises
    ------
    ValueError
        未対応の言語コードの場合
    """
    if lang_code not in LANGUAGE_CONFIGS:
        available = ", ".join(LANGUAGE_CONFIGS.keys())
        raise ValueError(f"未対応の言語コード: {lang_code}（対応言語: {available}）")
    return LANGUAGE_CONFIGS[lang_code]
