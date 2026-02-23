"""
音声ファイル生成モジュール。

対応TTS:
- VOICEVOX: 日本語用。ローカルで起動している必要があります。
- macOS say: 英語等の他言語用。
- Windows SAPI: macOS say の代替として Windows 上で自動使用。
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
import urllib.parse
import wave
from pathlib import Path

from core import logger
from core.config import VOICEVOX_BASE_URL, DEFAULT_SPEAKER_ID, LanguageConfig
from core.exceptions import AudioGenerationError, FileNotFoundError_
from core.messages import msg


def gen_sound_file(text_source_file: str, sound_file: str, rate: int = 100,
                   speaker_id: int = DEFAULT_SPEAKER_ID) -> None:
    """
    VOICEVOXを使用して、テキストファイルから音声ファイルを生成する。

    テキストは段落ごとに分割して処理し、最終的に1つのWAVファイルに結合します。

    Parameters
    ----------
    text_source_file : str
        読み上げ元のテキストファイルのパス。
    sound_file : str
        生成される音声ファイルの保存パス（例: output.wav）。
        WAV形式で出力されます。
    rate : int, optional
        音声の読み上げ速度（パーセント）。デフォルトは100。
        100が標準速度、50で半分、200で2倍の速度。
    speaker_id : int, optional
        VOICEVOXのスピーカーID。デフォルトは109。

    Raises
    ------
    FileNotFoundError_
        入力ファイルが存在しない場合。
    AudioGenerationError
        VOICEVOXエンジンへの接続や音声合成に失敗した場合。
    """
    # 入力ファイルの存在確認
    if not Path(text_source_file).exists():
        raise FileNotFoundError_(text_source_file, msg("file_type_input_text"))

    # テキストファイルを読み込む
    with open(text_source_file, 'r', encoding='utf-8') as f:
        text = f.read()

    # 段落ごとに分割（空行で分割）
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

    logger.section(msg("tts_voicevox_start"))
    logger.info(msg("tts_speaker_id", id=speaker_id))
    logger.info(msg("tts_speed", rate=rate))
    logger.info(msg("tts_paragraph_count", count=len(paragraphs)))

    try:
        wav_segments: list[bytes] = []

        for i, paragraph in enumerate(paragraphs):
            logger.progress(i + 1, len(paragraphs), msg("tts_paragraph_label"))

            # 音声合成クエリを作成
            audio_query = _create_audio_query(paragraph, speaker_id)

            # 速度を調整（rateをspeedScaleに変換）
            audio_query['speedScale'] = rate / 100.0

            # 音声を合成
            wav_data = _synthesize(audio_query, speaker_id)
            wav_segments.append(wav_data)

        logger.progress_done()

        # WAVファイルを結合
        combined_wav = _combine_wav_files(wav_segments)

        # WAVファイルを保存
        with open(sound_file, 'wb') as f:
            f.write(combined_wav)

        logger.success(msg("tts_audio_saved", file=sound_file))

    except urllib.error.HTTPError as e:
        raise AudioGenerationError(
            f"VOICEVOXエンジンでエラーが発生しました。\n"
            f"エラー: HTTP {e.code} - {e.reason}",
            source_file=text_source_file
        )
    except urllib.error.URLError as e:
        raise AudioGenerationError(
            f"VOICEVOXエンジンに接続できません。VOICEVOXが起動しているか確認してください。\n"
            f"エラー: {e}",
            source_file=text_source_file
        )
    except Exception as e:
        raise AudioGenerationError(
            f"音声合成エラー: {e}",
            source_file=text_source_file
        )


def _combine_wav_files(wav_segments: list[bytes]) -> bytes:
    """
    複数のWAVデータを1つのWAVファイルに結合する。

    Parameters
    ----------
    wav_segments : list[bytes]
        結合するWAVデータのリスト。

    Returns
    -------
    bytes
        結合されたWAVデータ。
    """
    if not wav_segments:
        raise ValueError("結合するWAVデータがありません")

    if len(wav_segments) == 1:
        return wav_segments[0]

    # 最初のWAVからパラメータを取得
    with wave.open(io.BytesIO(wav_segments[0]), 'rb') as first_wav:
        params = first_wav.getparams()
        sample_width = first_wav.getsampwidth()
        framerate = first_wav.getframerate()
        n_channels = first_wav.getnchannels()

    # すべてのWAVから生データを抽出して結合
    all_frames = b''
    for wav_data in wav_segments:
        with wave.open(io.BytesIO(wav_data), 'rb') as wav_file:
            all_frames += wav_file.readframes(wav_file.getnframes())

    # 結合したWAVを作成
    output = io.BytesIO()
    with wave.open(output, 'wb') as out_wav:
        out_wav.setnchannels(n_channels)
        out_wav.setsampwidth(sample_width)
        out_wav.setframerate(framerate)
        out_wav.writeframes(all_frames)

    return output.getvalue()


def _create_audio_query(text: str, speaker_id: int) -> dict:
    """
    VOICEVOXの音声合成クエリを作成する。

    Parameters
    ----------
    text : str
        読み上げるテキスト。
    speaker_id : int
        スピーカーID。

    Returns
    -------
    dict
        音声合成クエリ（JSON）。
    """
    url = f"{VOICEVOX_BASE_URL}/audio_query"
    params = urllib.parse.urlencode({'text': text, 'speaker': speaker_id})

    req = urllib.request.Request(f"{url}?{params}", method='POST')
    req.add_header('Content-Type', 'application/json')

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))


def _synthesize(audio_query: dict, speaker_id: int) -> bytes:
    """
    音声合成クエリから音声を合成する。

    Parameters
    ----------
    audio_query : dict
        音声合成クエリ。
    speaker_id : int
        スピーカーID。

    Returns
    -------
    bytes
        WAV形式の音声データ。
    """
    url = f"{VOICEVOX_BASE_URL}/synthesis"
    params = urllib.parse.urlencode({'speaker': speaker_id})

    req = urllib.request.Request(
        f"{url}?{params}",
        data=json.dumps(audio_query).encode('utf-8'),
        method='POST'
    )
    req.add_header('Content-Type', 'application/json')

    with urllib.request.urlopen(req) as response:
        return response.read()


def convert_wav_to_mp3(wav_file: str, mp3_file: str) -> None:
    """
    WAVファイルをMP3に変換する。

    Parameters
    ----------
    wav_file : str
        入力WAVファイルのパス。
    mp3_file : str
        出力MP3ファイルのパス。

    Raises
    ------
    AudioGenerationError
        FFmpegの実行に失敗した場合。
    """
    if not Path(wav_file).exists():
        raise FileNotFoundError_(wav_file, msg("file_type_input_wav"))

    command = [
        "ffmpeg", "-y",
        "-i", wav_file,
        "-codec:a", "libmp3lame",
        "-b:a", "64k",  # 64kbps固定。このソースならこれで十分すぎるほど高品質です
        "-ar", "24000",  # 元のサンプリングレートを維持（無駄なリサンプリングを避ける）
        "-ac", "1",  # 明示的にモノラル指定
        mp3_file
    ]

    logger.section(msg("ffmpeg_start"))

    try:
        subprocess.run(
            command, check=True, capture_output=True, text=True
        )
        logger.success(msg("ffmpeg_mp3_saved", file=mp3_file))

    except subprocess.CalledProcessError as e:
        raise AudioGenerationError(
            f"FFmpeg実行エラー: {e}\n標準エラー: {e.stderr}",
            source_file=wav_file
        )
    except FileNotFoundError:
        raise AudioGenerationError(
            "FFmpegが見つかりません。FFmpegをインストールしてください。",
            source_file=wav_file
        )


# ユーザー辞書API関連の関数

def get_user_dict() -> dict:
    """
    VOICEVOXのユーザー辞書を取得する。

    Returns
    -------
    dict
        ユーザー辞書の内容。キーは単語UUID、値は単語情報。
    """
    url = f"{VOICEVOX_BASE_URL}/user_dict"
    req = urllib.request.Request(url)

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode('utf-8'))


def add_user_dict_word(surface: str, pronunciation: str, accent_type: int = 1,
                       word_type: str = "PROPER_NOUN", priority: int = 5) -> str:
    """
    ユーザー辞書に単語を追加する。

    Parameters
    ----------
    surface : str
        表記（例: "Ⅰ"）。
    pronunciation : str
        読み方（カタカナ、例: "イチ"）。
    accent_type : int, optional
        アクセント型。デフォルトは1。
    word_type : str, optional
        単語の種類。デフォルトは"PROPER_NOUN"（固有名詞）。
        選択肢: PROPER_NOUN, COMMON_NOUN, VERB, ADJECTIVE, SUFFIX
    priority : int, optional
        優先度（1-10）。デフォルトは5。数字が大きいほど優先。

    Returns
    -------
    str
        追加された単語のUUID。
    """
    url = f"{VOICEVOX_BASE_URL}/user_dict_word"
    params = urllib.parse.urlencode({
        'surface': surface,
        'pronunciation': pronunciation,
        'accent_type': accent_type,
        'word_type': word_type,
        'priority': priority
    })

    req = urllib.request.Request(f"{url}?{params}", method='POST')

    with urllib.request.urlopen(req) as response:
        return response.read().decode('utf-8').strip('"')


def delete_user_dict_word(word_uuid: str) -> None:
    """
    ユーザー辞書から単語を削除する。

    Parameters
    ----------
    word_uuid : str
        削除する単語のUUID。
    """
    url = f"{VOICEVOX_BASE_URL}/user_dict_word/{word_uuid}"
    req = urllib.request.Request(url, method='DELETE')

    with urllib.request.urlopen(req) as response:
        pass


# --- macOS say コマンドによる音声生成 ---

def gen_sound_file_say(text_source_file: str, sound_file: str, voice: str = "Samantha") -> None:
    """
    macOSのsayコマンドを使用して、テキストファイルから音声ファイルを生成する。

    テキストは段落ごとに分割して処理し、最終的に1つのWAVファイルに結合します。

    Parameters
    ----------
    text_source_file : str
        読み上げ元のテキストファイルのパス。
    sound_file : str
        生成される音声ファイルの保存パス（例: output.wav）。
        WAV形式で出力されます。
    voice : str, optional
        sayコマンドの音声名。デフォルトは"Samantha"。

    Raises
    ------
    FileNotFoundError_
        入力ファイルが存在しない場合。
    AudioGenerationError
        音声生成に失敗した場合。
    """
    # 入力ファイルの存在確認
    if not Path(text_source_file).exists():
        raise FileNotFoundError_(text_source_file, msg("file_type_input_text"))

    # テキストファイルを読み込む
    with open(text_source_file, 'r', encoding='utf-8') as f:
        text = f.read()

    # 段落ごとに分割（空行で分割）
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

    logger.section(msg("tts_say_start"))
    logger.info(msg("tts_say_voice", voice=voice))
    logger.info(msg("tts_paragraph_count", count=len(paragraphs)))

    try:
        wav_segments: list[bytes] = []

        for i, paragraph in enumerate(paragraphs):
            logger.progress(i + 1, len(paragraphs), msg("tts_paragraph_label"))

            # sayコマンドで音声を生成
            wav_data = _synthesize_with_say(paragraph, voice)
            wav_segments.append(wav_data)

        logger.progress_done()

        # WAVファイルを結合
        combined_wav = _combine_wav_files(wav_segments)

        # WAVファイルを保存
        with open(sound_file, 'wb') as f:
            f.write(combined_wav)

        logger.success(msg("tts_audio_saved", file=sound_file))

    except subprocess.CalledProcessError as e:
        raise AudioGenerationError(
            f"sayコマンドでエラーが発生しました。\nエラー: {e}\n標準エラー: {e.stderr}",
            source_file=text_source_file
        )
    except Exception as e:
        raise AudioGenerationError(
            f"音声合成エラー: {e}",
            source_file=text_source_file
        )


def _synthesize_with_say(text: str, voice: str) -> bytes:
    """
    macOSのsayコマンドで音声を合成する。

    Parameters
    ----------
    text : str
        読み上げるテキスト。
    voice : str
        sayコマンドの音声名。

    Returns
    -------
    bytes
        WAV形式の音声データ。
    """
    # 一時ファイルを作成
    with tempfile.NamedTemporaryFile(suffix='.aiff', delete=False) as tmp_aiff:
        tmp_aiff_path = tmp_aiff.name

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
        tmp_wav_path = tmp_wav.name

    try:
        # sayコマンドでAIFFを生成
        command_say = [
            "say",
            "-v", voice,
            "-o", tmp_aiff_path,
            text
        ]
        subprocess.run(command_say, check=True, capture_output=True, text=True)

        # FFmpegでAIFFをWAVに変換（サンプリングレート24000Hz、モノラル）
        command_ffmpeg = [
            "ffmpeg", "-y",
            "-i", tmp_aiff_path,
            "-ar", "24000",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            tmp_wav_path
        ]
        subprocess.run(command_ffmpeg, check=True, capture_output=True, text=True)

        # WAVデータを読み込んで返す
        with open(tmp_wav_path, 'rb') as f:
            return f.read()

    finally:
        # 一時ファイルを削除
        if os.path.exists(tmp_aiff_path):
            os.remove(tmp_aiff_path)
        if os.path.exists(tmp_wav_path):
            os.remove(tmp_wav_path)


# --- Windows SAPI による音声生成 ---

def gen_sound_file_sapi(text_source_file: str, sound_file: str, culture: str = "en-US") -> None:
    """
    Windows SAPI (System.Speech.Synthesis) を使用して、テキストファイルから音声ファイルを生成する。

    テキストは段落ごとに分割して処理し、最終的に1つのWAVファイルに結合します。

    Parameters
    ----------
    text_source_file : str
        読み上げ元のテキストファイルのパス。
    sound_file : str
        生成される音声ファイルの保存パス（例: output.wav）。
        WAV形式で出力されます。
    culture : str, optional
        CultureInfo 文字列（例: "en-US", "de-DE"）。デフォルトは "en-US"。

    Raises
    ------
    FileNotFoundError_
        入力ファイルが存在しない場合。
    AudioGenerationError
        音声生成に失敗した場合。
    """
    if not Path(text_source_file).exists():
        raise FileNotFoundError_(text_source_file, msg("file_type_input_text"))

    with open(text_source_file, 'r', encoding='utf-8') as f:
        text = f.read()

    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

    logger.section(msg("tts_sapi_start"))
    logger.info(msg("tts_sapi_culture", culture=culture))
    logger.info(msg("tts_paragraph_count", count=len(paragraphs)))

    try:
        wav_segments: list[bytes] = []

        for i, paragraph in enumerate(paragraphs):
            logger.progress(i + 1, len(paragraphs), msg("tts_paragraph_label"))

            wav_data = _synthesize_with_sapi(paragraph, culture)
            wav_segments.append(wav_data)

        logger.progress_done()

        combined_wav = _combine_wav_files(wav_segments)

        with open(sound_file, 'wb') as f:
            f.write(combined_wav)

        logger.success(msg("tts_audio_saved", file=sound_file))

    except subprocess.CalledProcessError as e:
        if "No voice found" in (e.stderr or ""):
            raise AudioGenerationError(
                msg("sapi_voice_not_found", culture=culture),
                source_file=text_source_file
            )
        raise AudioGenerationError(
            msg("sapi_error", stderr=e.stderr),
            source_file=text_source_file
        )
    except Exception as e:
        raise AudioGenerationError(
            f"音声合成エラー: {e}",
            source_file=text_source_file
        )


def _escape_for_powershell(text: str) -> str:
    """
    PowerShell の文字列リテラル用にテキストをエスケープする。

    シングルクォート文字列内ではシングルクォートを二重にするだけで安全。

    Parameters
    ----------
    text : str
        エスケープするテキスト。

    Returns
    -------
    str
        エスケープ済みテキスト。
    """
    return text.replace("'", "''")


def _synthesize_with_sapi(text: str, culture: str) -> bytes:
    """
    Windows SAPI (System.Speech.Synthesis.SpeechSynthesizer) で音声を合成する。

    Parameters
    ----------
    text : str
        読み上げるテキスト。
    culture : str
        CultureInfo 文字列（例: "en-US"）。

    Returns
    -------
    bytes
        WAV形式の音声データ（24000Hz, モノラル, pcm_s16le）。
    """
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_raw:
        tmp_raw_path = tmp_raw.name

    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_conv:
        tmp_conv_path = tmp_conv.name

    try:
        escaped_text = _escape_for_powershell(text)
        escaped_culture = _escape_for_powershell(culture)
        escaped_wav_path = tmp_raw_path.replace("'", "''")

        ps_script = (
            "$ErrorActionPreference = 'Stop'; "
            "Add-Type -AssemblyName System.Speech; "
            f"$culture = [System.Globalization.CultureInfo]::new('{escaped_culture}'); "
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$available = $synth.GetInstalledVoices() | "
            "  Where-Object { $_.VoiceInfo.Culture.Name -eq $culture.Name }; "
            "if (-not $available) { "
            "  Write-Error ('No voice found for ' + $culture.Name + "
            "    '. Install the language pack: Windows Settings > Time & Language > Language.'); "
            "  exit 1 "
            "}; "
            "$synth.SelectVoiceByHints("
            "[System.Speech.Synthesis.VoiceGender]::NotSet, "
            "[System.Speech.Synthesis.VoiceAge]::NotSet, "
            "0, $culture); "
            f"$synth.SetOutputToWaveFile('{escaped_wav_path}'); "
            f"$synth.Speak('{escaped_text}'); "
            "$synth.Dispose()"
        )

        command_ps = [
            "powershell", "-NoProfile", "-NonInteractive",
            "-Command", ps_script
        ]
        subprocess.run(command_ps, check=True, capture_output=True, text=True)

        # FFmpegで24000Hz、モノラル、pcm_s16leに変換（MFA互換）
        command_ffmpeg = [
            "ffmpeg", "-y",
            "-i", tmp_raw_path,
            "-ar", "24000",
            "-ac", "1",
            "-acodec", "pcm_s16le",
            tmp_conv_path
        ]
        subprocess.run(command_ffmpeg, check=True, capture_output=True, text=True)

        with open(tmp_conv_path, 'rb') as f:
            return f.read()

    finally:
        if os.path.exists(tmp_raw_path):
            os.remove(tmp_raw_path)
        if os.path.exists(tmp_conv_path):
            os.remove(tmp_conv_path)


# --- 言語対応の音声生成関数 ---

def generate_audio(text_source_file: str, sound_file: str, lang_config: LanguageConfig) -> None:
    """
    言語設定に基づいて適切なTTSエンジンで音声ファイルを生成する。

    Parameters
    ----------
    text_source_file : str
        読み上げ元のテキストファイルのパス。
    sound_file : str
        生成される音声ファイルの保存パス（例: output.wav）。
    lang_config : LanguageConfig
        言語設定。

    Raises
    ------
    FileNotFoundError_
        入力ファイルが存在しない場合。
    AudioGenerationError
        音声生成に失敗した場合。
    """
    if lang_config.tts_engine == "voicevox":
        gen_sound_file(text_source_file, sound_file)
    elif lang_config.tts_engine == "say":
        if sys.platform == "win32":
            # Windows: SAPI にフォールバック
            culture = lang_config.code.replace("_", "-")  # "en_US" → "en-US"
            gen_sound_file_sapi(text_source_file, sound_file, culture=culture)
        else:
            voice = lang_config.tts_voice or "Samantha"
            gen_sound_file_say(text_source_file, sound_file, voice=voice)
    else:
        raise AudioGenerationError(
            f"未対応のTTSエンジン: {lang_config.tts_engine}",
            source_file=text_source_file
        )
