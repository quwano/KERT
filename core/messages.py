"""
UIメッセージ国際化モジュール。

OSのロケールに基づいて日本語/英語のUIメッセージを自動切替する。
"""
import locale
import os
import sys

MESSAGES: dict[str, dict[str, str]] = {
    "ja": {
        # ツールタイトル
        "tool_title": "KERT - EPUB3 & DAISY4 Support Tool",

        # 言語選択
        "select_language": "言語を選択してください / Select language:",
        "language_prompt": "言語 / Language (1-{n}, デフォルト: 1): ",
        "selected_language": "選択された言語: {name}",
        "default_language": "デフォルト言語を使用: {name}",

        # 入力形式選択
        "select_input_format": "入力形式を選択してください:",
        "opt_commonmark": "CommonMark拡張テキストファイル（.txt/.md）",
        "opt_xml": "XMLファイル（.xml）",

        # 処理モード選択
        "select_processing_mode": "処理モードを選択してください:",
        "opt_single": "単一{type}ファイルからEPUB生成",
        "opt_folder": "フォルダ内の複数{type}ファイルからEPUB生成",

        # 共通選択UI
        "choice_prompt": "選択 (1-{n}, デフォルト: {d}): ",
        "invalid_value": "無効な値です。1-{n}の範囲で入力してください。デフォルト値({d})を使用します。",
        "invalid_input": "無効な入力です。数値を入力してください。デフォルト値({d})を使用します。",

        # パス入力
        "prompt_folder_path": "{type}ファイルが格納されたフォルダのパスを指定してください\n",
        "prompt_file_path": "{type}ファイル（{ext}）のパスを指定してください\n",

        # 中間ファイル
        "keep_intermediate_question": "中間ファイル（META-INF, OEBPS, audio.*）を残しますか？",
        "keep_intermediate_dest": "残す場合の出力先: {path}",
        "opt_keep_no": "残さない（デフォルト）",
        "opt_keep_yes": "残す",

        # 処理ログ
        "processing_start": "処理開始: {time}",
        "processing_end": "処理終了: {time}",
        "elapsed_time": "所要時間: {time}",
        "output_file": "生成ファイル: {path}",
        "intermediate_saved": "中間ファイルを保存しました: {path}",
        "highlight_fixed": "ハイライトモードは句読点単位に固定されます。",
        "audio_start": "音声生成を開始します: {file}",
        "processing_file": "処理中: {name}",
        "file_count": "{count} 個の{ext}ファイルを処理します。",
        "file_count_commonmark": "{count} 個のCommonMarkファイルを処理します。",
        "processing_aborted": "処理を中断しました。",

        # エラー・バリデーション
        "file_not_found": "ファイルが見つかりません: {path}",
        "folder_not_found": "フォルダが見つかりません: {path}",
        "reserved_filename": "ファイル名 '{name}' は作業用ファイル名として予約されています。\n別のファイル名を使用してください。",
        "reserved_filenames_in_list": "作業用ファイル名として予約されているファイルが含まれています: {names}\nこれらのファイル名を変更してください。",
        "no_files_in_folder": "{folder} に{ext}ファイルが見つかりません。",
        "no_commonmark_in_folder": "{folder} に.txtまたは.mdファイルが見つかりません。",

        # 表示名
        "display_commonmark": "CommonMark拡張",

        # メタデータエラー
        "metadata_not_found": "エラー：書誌情報がありません\n期待されるファイル: {path}\n処理を中断しました。",
        "metadata_no_title": "エラー：書誌情報にタイトルがありません\n処理を中断しました。",

        # ロガープレフィックス
        "log_warning": "警告: {message}",
        "log_success": "成功: {message}",
        "log_progress": "処理中: {message} {current}/{total}",

        # 例外メッセージ
        "exception_file_not_found": "{file_type}が見つかりません: {file_path}",

        # ファイル種別名（FileNotFoundError_ の file_type 引数用）
        "file_type_audio": "音声ファイル",
        "file_type_textgrid": "TextGridファイル",
        "file_type_input_text": "入力テキストファイル",
        "file_type_input_wav": "入力WAVファイル",
        "file_type_text": "テキスト",

        # TTS（音声生成）ログ
        "tts_voicevox_start": "VOICEVOXを使用して、テキストファイルから音声ファイルを生成します。",
        "tts_speaker_id": "  スピーカーID: {id}",
        "tts_speed": "  速度: {rate}%",
        "tts_paragraph_count": "  段落数: {count}",
        "tts_paragraph_label": "段落",
        "tts_audio_saved": "音声ファイルを生成しました: {file}",
        "tts_say_start": "macOS sayを使用して、テキストファイルから音声ファイルを生成します。",
        "tts_say_voice": "  音声: {voice}",
        "tts_sapi_start": "Windows SAPIを使用して、テキストファイルから音声ファイルを生成します。",
        "tts_sapi_culture": "  Culture: {culture}",
        "sapi_voice_not_found": "{culture} の言語パックがインストールされていません。\nWindows の設定 > 時刻と言語 > 言語 から言語パックを追加し、音声機能を有効にしてください。",
        "sapi_error": "Windows SAPI でエラーが発生しました。\n標準エラー: {stderr}",
        "ffmpeg_start": "FFmpegを使用して、WAVファイルをMP3に変換します。",
        "ffmpeg_mp3_saved": "MP3ファイルを生成しました: {file}",

        # TextGrid生成ログ
        "textgrid_start": "mp3形式の音声ファイルからTextGridファイルを生成します。",
        "textgrid_files_placed": "一時ディレクトリにファイルを配置しました（テキストは正規化済み）。",
        "mfa_align_start": "Conda環境 '{env}' 内で MFAアライメントを開始します...",
        "mfa_dict_model": "  辞書モデル: {model}",
        "mfa_acoustic_model": "  音響モデル: {model}",
        "textgrid_saved": "TextGridファイルを生成しました: {file}",
        "mfa_stem_mismatch": "テキストファイルと音声ファイルの拡張子を除いたファイル名が一致しません。",
        "mfa_files_missing": "必要なファイルが見つかりません。TXT: {txt}, WAV: {wav}",
        "mfa_no_output": "MFAがTextGridファイルを出力しませんでした。",
        "mfa_failed": "MFAコマンドの実行中に失敗しました。",
        "mfa_output_label": "MFA出力:\n{output}",
        "unexpected_error": "予期せぬエラー: {error}",

        # EPUBビルダー共通ログ
        "epub_saved": "EPUBファイルを生成しました: {file}",
        "epub_section_count": "{count} 個のセクションを処理します。",
        "epub_file_count_progress": "{count} 個のファイルを処理します。",
        "epub_paragraph_count": "{count} 個の段落を処理します。",
        "epub_section_count_done": "   セクション数: {count}",
        "epub_file_count_done": "   ファイル数: {count}",
        "epub_chapter_count_done": "   チャプター数: {count}",
        "epub_paragraph_count_done": "   段落数: {count}",
        "epub_duration": "   総再生時間: {duration:.1f}秒",
        "epub_section_processing": "  処理中: {id}: {title}",
        "epub_section_done": "    処理完了: {id}",
        "epub_file_processing": "  処理中: {name} ({count} セクション)",
        "epub_file_done": "    処理完了: {name}",
        "epub_chapter_done": "  処理完了: {id}: {title}",

        # EPUBビルダー固有ログ
        "xml_sections_epub_start": "XMLファイル（セクション構造）からEPUBファイルを生成します。",
        "xml_epub_start": "TextGridファイルとmp3ファイルを元に、EPUBファイルを生成します。",
        "commonmark_epub_no_headings_start": "CommonMarkファイル（見出しなし）からEPUBファイルを生成します。",
        "commonmark_epub_start": "CommonMarkファイルからEPUBファイルを生成します。",
        "commonmark_multi_epub_start": "複数CommonMarkファイルからEPUBファイルを生成します。",
        "multi_epub_start": "複数{file_type}ファイルからEPUBファイルを生成します。",
    },
    "en": {
        # Tool title
        "tool_title": "KERT - EPUB3 & DAISY4 Support Tool",

        # Language selection
        "select_language": "Select language:",
        "language_prompt": "Language (1-{n}, default: 1): ",
        "selected_language": "Selected language: {name}",
        "default_language": "Using default language: {name}",

        # Input format selection
        "select_input_format": "Select input format:",
        "opt_commonmark": "CommonMark extended text file (.txt/.md)",
        "opt_xml": "XML file (.xml)",

        # Processing mode selection
        "select_processing_mode": "Select processing mode:",
        "opt_single": "Generate EPUB from a single {type} file",
        "opt_folder": "Generate EPUB from multiple {type} files in a folder",

        # Common selection UI
        "choice_prompt": "Selection (1-{n}, default: {d}): ",
        "invalid_value": "Invalid value. Enter a number between 1-{n}. Using default ({d}).",
        "invalid_input": "Invalid input. Enter a number. Using default ({d}).",

        # Path input
        "prompt_folder_path": "Specify the path to the folder containing {type} files\n",
        "prompt_file_path": "Specify the path to the {type} file ({ext})\n",

        # Intermediate files
        "keep_intermediate_question": "Keep intermediate files (META-INF, OEBPS, audio.*)?",
        "keep_intermediate_dest": "Output destination if kept: {path}",
        "opt_keep_no": "Do not keep (default)",
        "opt_keep_yes": "Keep",

        # Processing log
        "processing_start": "Processing started: {time}",
        "processing_end": "Processing finished: {time}",
        "elapsed_time": "Elapsed time: {time}",
        "output_file": "Output file: {path}",
        "intermediate_saved": "Intermediate files saved: {path}",
        "highlight_fixed": "Highlight mode is fixed to punctuation-based.",
        "audio_start": "Starting audio generation: {file}",
        "processing_file": "Processing: {name}",
        "file_count": "Processing {count} {ext} file(s).",
        "file_count_commonmark": "Processing {count} CommonMark file(s).",
        "processing_aborted": "Processing aborted.",

        # Error / validation
        "file_not_found": "File not found: {path}",
        "folder_not_found": "Folder not found: {path}",
        "reserved_filename": "Filename '{name}' is reserved for internal use.\nPlease use a different filename.",
        "reserved_filenames_in_list": "Reserved filenames found: {names}\nPlease rename these files.",
        "no_files_in_folder": "No {ext} files found in {folder}.",
        "no_commonmark_in_folder": "No .txt or .md files found in {folder}.",

        # Display names
        "display_commonmark": "CommonMark extended",

        # Metadata errors
        "metadata_not_found": "Error: Metadata file not found\nExpected file: {path}\nProcessing aborted.",
        "metadata_no_title": "Error: No title found in metadata\nProcessing aborted.",

        # Logger prefixes
        "log_warning": "Warning: {message}",
        "log_success": "Success: {message}",
        "log_progress": "Processing: {message} {current}/{total}",

        # Exception messages
        "exception_file_not_found": "{file_type} not found: {file_path}",

        # File type names (for FileNotFoundError_ file_type argument)
        "file_type_audio": "audio file",
        "file_type_textgrid": "TextGrid file",
        "file_type_input_text": "input text file",
        "file_type_input_wav": "input WAV file",
        "file_type_text": "text",

        # TTS (audio generation) log
        "tts_voicevox_start": "Generating audio from text file using VOICEVOX.",
        "tts_speaker_id": "  Speaker ID: {id}",
        "tts_speed": "  Speed: {rate}%",
        "tts_paragraph_count": "  Paragraphs: {count}",
        "tts_paragraph_label": "paragraph",
        "tts_audio_saved": "Audio file generated: {file}",
        "tts_say_start": "Generating audio from text file using macOS say.",
        "tts_say_voice": "  Voice: {voice}",
        "tts_sapi_start": "Generating audio from text file using Windows SAPI.",
        "tts_sapi_culture": "  Culture: {culture}",
        "sapi_voice_not_found": "Language pack for {culture} is not installed.\nGo to Windows Settings > Time & Language > Language to add the language pack and enable speech.",
        "sapi_error": "Windows SAPI error.\nStderr: {stderr}",
        "ffmpeg_start": "Converting WAV to MP3 using FFmpeg.",
        "ffmpeg_mp3_saved": "MP3 file generated: {file}",

        # TextGrid generation log
        "textgrid_start": "Generating TextGrid from MP3 audio file.",
        "textgrid_files_placed": "Files placed in temporary directory (text normalized).",
        "mfa_align_start": "Starting MFA alignment in Conda environment '{env}'...",
        "mfa_dict_model": "  Dictionary model: {model}",
        "mfa_acoustic_model": "  Acoustic model: {model}",
        "textgrid_saved": "TextGrid file generated: {file}",
        "mfa_stem_mismatch": "Text and audio file names (without extension) do not match.",
        "mfa_files_missing": "Required files not found. TXT: {txt}, WAV: {wav}",
        "mfa_no_output": "MFA did not output a TextGrid file.",
        "mfa_failed": "MFA command execution failed.",
        "mfa_output_label": "MFA output:\n{output}",
        "unexpected_error": "Unexpected error: {error}",

        # EPUB builder common log
        "epub_saved": "EPUB file generated: {file}",
        "epub_section_count": "Processing {count} section(s).",
        "epub_file_count_progress": "Processing {count} file(s).",
        "epub_paragraph_count": "Processing {count} paragraph(s).",
        "epub_section_count_done": "   Sections: {count}",
        "epub_file_count_done": "   Files: {count}",
        "epub_chapter_count_done": "   Chapters: {count}",
        "epub_paragraph_count_done": "   Paragraphs: {count}",
        "epub_duration": "   Total duration: {duration:.1f}s",
        "epub_section_processing": "  Processing: {id}: {title}",
        "epub_section_done": "    Done: {id}",
        "epub_file_processing": "  Processing: {name} ({count} section(s))",
        "epub_file_done": "    Done: {name}",
        "epub_chapter_done": "  Done: {id}: {title}",

        # EPUB builder specific log
        "xml_sections_epub_start": "Generating EPUB from XML file (section structure).",
        "xml_epub_start": "Generating EPUB from TextGrid and MP3 files.",
        "commonmark_epub_no_headings_start": "Generating EPUB from CommonMark file (no headings).",
        "commonmark_epub_start": "Generating EPUB from CommonMark file.",
        "commonmark_multi_epub_start": "Generating EPUB from multiple CommonMark files.",
        "multi_epub_start": "Generating EPUB from multiple {file_type} files.",
    },
}

# OS言語判定
def _detect_ui_language() -> str:
    """OSのロケールから UI 言語を判定する。"""
    # macOS: システム言語設定（AppleLanguages）を最優先
    # LANG=C.UTF-8 等はシステム言語と無関係なため、macOS設定を先にチェック
    if sys.platform == "darwin":
        try:
            import subprocess
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleLanguages"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                # 出力例: ("ja-JP", "en-US", ...) → 先頭の言語コードを取得
                for line in result.stdout.splitlines():
                    line = line.strip().strip('",() ')
                    if line:
                        return "ja" if line.startswith("ja") else "en"
        except Exception:
            pass
    # 環境変数をチェック（LC_ALL, LC_MESSAGES, LANG）
    # C / C.UTF-8 / POSIX はデフォルト値のため言語指定なしとして除外
    for env_var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(env_var, "")
        if value and not value.startswith("C") and value != "POSIX":
            return "ja" if value.startswith("ja") else "en"
    # フォールバック: locale.getlocale()
    # Windows では "Japanese_Japan" のように返るため、大文字小文字を無視して判定
    try:
        loc = locale.getlocale()[0] or ""
    except ValueError:
        loc = ""
    return "ja" if loc.lower().startswith("ja") else "en"

_ui_lang = _detect_ui_language()


def set_ui_language(lang_code: str) -> None:
    """
    UIメッセージ言語を手動で設定する。

    言語選択UIでユーザーが選択した言語に合わせて呼び出す。

    Parameters
    ----------
    lang_code : str
        言語コード（例: "ja_JP", "en_US", "de_DE"）。
        "ja" で始まる場合は日本語、それ以外は英語を使用する。
    """
    global _ui_lang
    _ui_lang = "ja" if lang_code.startswith("ja") else "en"


def msg(key: str, **kwargs) -> str:
    """
    指定キーのUIメッセージを現在のロケールに応じて返す。

    Parameters
    ----------
    key : str
        メッセージキー
    **kwargs
        メッセージ内のプレースホルダーに渡す値

    Returns
    -------
    str
        ロケールに応じたメッセージ文字列
    """
    template = MESSAGES[_ui_lang].get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template
