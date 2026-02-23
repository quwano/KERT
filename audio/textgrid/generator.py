import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from core import logger
from core.messages import msg
from text.common import change_suffix, strip_formatting, TextNormalizer
from core.config import (
    MFA_DICTIONARY_MODEL,
    MFA_ACOUSTIC_MODEL,
    MFA_ENV_NAME,
    LanguageConfig,
)


def _find_conda_executable() -> str:
    """
    condaの実行ファイルパスを検出して返す。

    以下の順序で検索する:
    1. PATHに存在する場合（shutil.which）
    2. 環境変数 CONDA_EXE
    3. Windowsの一般的なインストールパス

    Returns
    -------
    str
        condaの実行ファイルパス。

    Raises
    ------
    FileNotFoundError
        condaが見つからない場合。
    """
    # 1. PATHから検索
    conda_path = shutil.which("conda")
    if conda_path:
        return conda_path

    # 2. 環境変数 CONDA_EXE
    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe and Path(conda_exe).is_file():
        return conda_exe

    # 3. Windowsの一般的なインストールパス
    if sys.platform == "win32":
        user_profile = os.environ.get("USERPROFILE", "")
        if user_profile:
            candidates = [
                Path(user_profile) / "miniforge3" / "Scripts" / "conda.exe",
                Path(user_profile) / "miniconda3" / "Scripts" / "conda.exe",
                Path(user_profile) / "Anaconda3" / "Scripts" / "conda.exe",
            ]
            for candidate in candidates:
                if candidate.is_file():
                    return str(candidate)

    raise FileNotFoundError(
        "conda が見つかりません。以下のいずれかの方法で対処してください:\n"
        "  - conda を PATH に追加する\n"
        "  - 環境変数 CONDA_EXE に conda の実行ファイルパスを設定する\n"
        "  - Miniforge / Miniconda をインストールする\n"
        "    https://github.com/conda-forge/miniforge"
    )


def _normalize_text_for_mfa(text: str) -> str:
    """
    MFA用にテキストを正規化する。

    MFAの辞書に存在しない記号を、認識可能な形式に変換します。
    書式記法（太字、下線など）も除去します。
    """
    # まず書式記法を除去（**太字**、[下線]{.underline}など）
    result = strip_formatting(text)
    # TextNormalizerで一括正規化（括弧は含めない - MFAでは不要）
    result = TextNormalizer.normalize_all(result, include_brackets=False)
    # ハイフンをスペースに置換（"a-毛織物"等の複合トークンを分割してMFAが個別認識可能にする）
    result = result.replace('-', ' ')
    return result


def generate_textgrid_from_files_auto(
    txt_full_path: str,
    sound_full_path: str,
    lang_config: LanguageConfig | None = None
) -> None:
    """
    テキストファイルと音声ファイルからMFAを使用してTextGridファイルを自動生成する。

    MFA (Montreal Forced Aligner) をConda環境経由で実行し、アライメント結果を
    TextGridとして出力します。処理中に一時ディレクトリを作成し、終了時にクリーンアップ
    を行います。

    Parameters
    ----------
    txt_full_path : str
        読み上げテキストファイルのフルパス。
    sound_full_path : str
        対応する音声ファイルのフルパス。
    lang_config : LanguageConfig | None
        言語設定。Noneの場合はデフォルト（日本語）を使用。

    Returns
    -------
    None

    Notes
    -----
    - テキストファイルと音声ファイルのベース名（拡張子を除く部分）が一致している必要があります。
    - 内部で `conda run -n mfa` コマンドを使用するため、適切なConda環境が構築されている必要があります。
    """
    # 言語設定からMFAモデルを取得（Noneの場合はデフォルト値を使用）
    if lang_config is not None:
        mfa_dictionary = lang_config.mfa_dictionary
        mfa_acoustic = lang_config.mfa_acoustic
    else:
        mfa_dictionary = MFA_DICTIONARY_MODEL
        mfa_acoustic = MFA_ACOUSTIC_MODEL

    logger.section(msg("textgrid_start"))
    txt_path: Path = Path(txt_full_path)
    sound_path: Path = Path(sound_full_path)

    if txt_path.stem != sound_path.stem:
        logger.error(msg("mfa_stem_mismatch"))
        return

    base_name: str = txt_path.stem
    final_textgrid_path_str: str = change_suffix(sound_full_path, '.TextGrid')
    final_textgrid_path: Path = Path(final_textgrid_path_str)

    if not txt_path.exists() or not sound_path.exists():
        logger.error(msg("mfa_files_missing", txt=txt_path.exists(), wav=sound_path.exists()))
        return

    # MFAの処理に必要な一時ディレクトリのセットアップ
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path: Path = Path(tmp_dir)
        corpus_dir: Path = tmp_dir_path / "mfa_corpus"
        corpus_dir.mkdir()
        output_dir: Path = tmp_dir_path / "mfa_output"
        output_dir.mkdir()

        # テキストファイルをMFA用に正規化してコピー
        with open(txt_path, 'r', encoding='utf-8') as f:
            original_text = f.read()
        normalized_text = _normalize_text_for_mfa(original_text)
        with open(corpus_dir / txt_path.name, 'w', encoding='utf-8') as f:
            f.write(normalized_text)

        shutil.copy(sound_path, corpus_dir / sound_path.name)
        logger.info(msg("textgrid_files_placed"))

        # MFAコマンドの構築と実行 (conda run を使用)
        try:
            conda_exe = _find_conda_executable()
            mfa_command: list[str] = [
                conda_exe, "run", "-n", MFA_ENV_NAME,
                "mfa", "align",
                str(corpus_dir),
                mfa_dictionary,
                mfa_acoustic,
                str(output_dir),
                "--clean",
                "--disable_check_version",
                "--generate_intermediate_tier",
                "--beam", "100",
                "--retry_beam", "400",
            ]

            logger.info(msg("mfa_align_start", env=MFA_ENV_NAME))
            logger.info(msg("mfa_dict_model", model=mfa_dictionary))
            logger.info(msg("mfa_acoustic_model", model=mfa_acoustic))

            result = subprocess.run(
                mfa_command,
                capture_output=True,
                text=True,
                check=True
            )

            temp_textgrid = output_dir / f"{base_name}.TextGrid"

            if temp_textgrid.exists():
                shutil.move(temp_textgrid, final_textgrid_path)
                logger.success(msg("textgrid_saved", file=final_textgrid_path))

            else:
                logger.error(msg("mfa_no_output"))
                logger.debug(result.stderr)

        except subprocess.CalledProcessError as e:
            logger.error(msg("mfa_failed"))
            if e.stderr:
                logger.error(msg("mfa_output_label", output=e.stderr.strip()))
        except FileNotFoundError as e:
            logger.error(str(e))
        except Exception as e:
            logger.error(msg("unexpected_error", error=e))