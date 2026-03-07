"""数式処理モジュール。

TeX→MathML（pandoc経由）、MathML→音声テキスト（Speech Rule Engine経由）の変換、
およびプレースホルダー管理を提供します。
"""
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core import logger

# SRE言語マッピング（lang_code → SRE locale）
SRE_LANG_MAP: dict[str, str] = {
    "ja_JP": "ja",
    "en_US": "en",
    "de_DE": "de",
}

# 数式プレースホルダーパターン: \x02MATH{idx}\x02
# \x02 (STX制御文字) は通常テキストに現れないため安全なデリミタ
MATH_PLACEHOLDER_PATTERN = re.compile(r'\x02MATH(\d+)\x02')

# CommonMark数式パターン
# $$...$$ (ブロック数式) を先に検出してからインラインを検出
DISPLAY_MATH_PATTERN = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)
INLINE_MATH_PATTERN = re.compile(r'\$([^$\n]+?)\$')


@dataclass
class MathEntry:
    """数式エントリー。プレースホルダーに対応するMathMLと音声テキストを保持する。"""
    mathml: str    # MathML文字列（<math>要素全体）
    speech: str    # SREによる読み上げテキスト
    display: bool  # True=ブロック数式($$...$$), False=インライン数式($...$)


class MathProcessor:
    """数式処理クラス。

    CommonMarkテキスト中の TeX 数式 ($...$, $$...$$) を検出し、
    プレースホルダー \\x02MATH{idx}\\x02 に置換します。
    各数式に対してMathMLと音声テキストを事前計算します。
    """

    def __init__(self, sre_lang: str = "ja"):
        """
        Parameters
        ----------
        sre_lang : str
            Speech Rule Engineの言語コード（"ja", "en", "de"など）。
        """
        self.sre_lang = sre_lang
        self._entries: list[MathEntry] = []

    def substitute(self, text: str) -> str:
        """テキスト中の数式をプレースホルダーに置換する。

        $$ ... $$ (ブロック数式) と $ ... $ (インライン数式) を検出し、
        \\x02MATH{idx}\\x02 に置換します。TeX→MathML→音声変換を同時に行います。

        Parameters
        ----------
        text : str
            数式を含む元テキスト。

        Returns
        -------
        str
            プレースホルダーに置換されたテキスト。
        """
        def replace_display(m: re.Match) -> str:
            tex = m.group(1).strip()
            idx = self._add_entry(tex, display=True)
            return f'\x02MATH{idx}\x02'

        def replace_inline(m: re.Match) -> str:
            tex = m.group(1).strip()
            idx = self._add_entry(tex, display=False)
            return f'\x02MATH{idx}\x02'

        # ブロック数式を先に処理（インライン記法 $...$ より優先）
        result = DISPLAY_MATH_PATTERN.sub(replace_display, text)
        result = INLINE_MATH_PATTERN.sub(replace_inline, result)
        return result

    def _add_entry(self, tex: str, display: bool) -> int:
        """数式エントリーを追加してインデックスを返す。"""
        try:
            mathml = tex_to_mathml(tex, display)
        except Exception as e:
            logger.warning(f"TeX→MathML変換エラー: {e}. TeX: {tex[:50]}")
            mathml = f'<math xmlns="http://www.w3.org/1998/Math/MathML"><merror><mtext>{tex}</mtext></merror></math>'

        try:
            speech = mathml_to_speech(mathml, self.sre_lang)
        except Exception as e:
            logger.warning(f"MathML→音声変換エラー: {e}")
            speech = tex  # フォールバック: TeX文字列をそのまま使用

        idx = len(self._entries)
        self._entries.append(MathEntry(mathml=mathml, speech=speech, display=display))
        return idx

    def to_speech(self, text: str) -> str:
        """プレースホルダーを音声テキストに展開する。

        Parameters
        ----------
        text : str
            \\x02MATH{idx}\\x02 プレースホルダーを含むテキスト。

        Returns
        -------
        str
            プレースホルダーを対応する音声テキストに置換したテキスト。
        """
        def replace(m: re.Match) -> str:
            idx = int(m.group(1))
            if idx < len(self._entries):
                return self._entries[idx].speech
            return ''

        return MATH_PLACEHOLDER_PATTERN.sub(replace, text)

    def to_xhtml(self, text: str) -> str:
        """プレースホルダーをMathML XHTMLに展開する。

        Parameters
        ----------
        text : str
            \\x02MATH{idx}\\x02 プレースホルダーを含むテキスト。

        Returns
        -------
        str
            プレースホルダーを対応するMathML要素に置換したテキスト。
        """
        def replace(m: re.Match) -> str:
            idx = int(m.group(1))
            if idx < len(self._entries):
                return self._entries[idx].mathml
            return ''

        return MATH_PLACEHOLDER_PATTERN.sub(replace, text)

    def get_entry(self, idx: int) -> MathEntry | None:
        """インデックスでエントリーを取得する。"""
        if 0 <= idx < len(self._entries):
            return self._entries[idx]
        return None

    @property
    def has_math(self) -> bool:
        """数式エントリーが存在するかどうか。"""
        return len(self._entries) > 0

    def placeholder_len(self, idx: int) -> int:
        """指定インデックスのプレースホルダー文字列長を返す。"""
        return len(f'\x02MATH{idx}\x02')


# =============================================================================
# 変換関数
# =============================================================================

def tex_to_mathml(tex: str, display: bool = False) -> str:
    """TeXをMathMLに変換する（pandoc使用）。

    Parameters
    ----------
    tex : str
        LaTeX数式文字列（デリミタなし。例: "x^2 + y^2 = r^2"）。
    display : bool
        True=ブロック数式（display="block"）, False=インライン数式。

    Returns
    -------
    str
        MathML文字列（<math>要素全体）。

    Raises
    ------
    RuntimeError
        pandocが失敗した場合、またはMathML要素を抽出できない場合。
    """
    if display:
        latex_input = f"$$\n{tex}\n$$"
    else:
        latex_input = f"${tex}$"

    result = subprocess.run(
        ["pandoc", "-f", "latex", "-t", "html", "--mathml", "--no-highlight"],
        input=latex_input,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(f"pandoc失敗: {result.stderr.strip()}")

    output = result.stdout.strip()

    # pandoc出力から<math>要素を抽出
    math_match = re.search(r'<math[^>]*>.*?</math>', output, re.DOTALL)
    if math_match:
        return math_match.group(0)

    raise RuntimeError(f"pandoc出力からmath要素を抽出できませんでした: {output[:200]}")


def mathml_to_speech(mathml: str, sre_lang: str = "ja") -> str:
    """MathMLを音声テキストに変換する（Speech Rule Engine使用）。

    Node.js経由でspeech-rule-engineパッケージを呼び出します。
    プロジェクトルートで `npm install speech-rule-engine` 済みであること。

    Parameters
    ----------
    mathml : str
        MathML文字列（<math>要素全体）。
    sre_lang : str
        SREの言語コード（"ja", "en", "de"など）。

    Returns
    -------
    str
        音声テキスト。

    Raises
    ------
    RuntimeError
        Node.jsまたはSREの実行に失敗した場合。
    """
    mathml_json = json.dumps(mathml)
    lang_json = json.dumps(sre_lang)

    js_script = f"""
const sre = require('speech-rule-engine');
sre.setupEngine({{
    locale: {lang_json},
    domain: 'mathspeak',
    style: 'default',
    modality: 'speech'
}});
sre.engineReady().then(() => {{
    const speech = sre.toSpeech({mathml_json});
    process.stdout.write(speech);
}}).catch(e => {{
    process.stderr.write(String(e));
    process.exit(1);
}});
"""

    result = subprocess.run(
        ["node", "-e", js_script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        cwd=str(Path(__file__).parent.parent),
    )

    if result.returncode != 0:
        raise RuntimeError(f"SRE失敗: {result.stderr.strip()}")

    return result.stdout.strip()


def mathml_to_speech_xml(mathml: str, sre_lang: str = "ja") -> str:
    """XMLソース用MathML音声変換（エラー時は空文字列を返す）。

    XML入力パス専用。エラー時にスタックトレースではなく空文字列を返します。
    """
    try:
        return mathml_to_speech(mathml, sre_lang)
    except Exception as e:
        logger.warning(f"MathML音声変換エラー（XML入力）: {e}")
        return ""


# =============================================================================
# モジュールレベルシングルトン
# =============================================================================

_current_processor: MathProcessor | None = None


def set_current_processor(proc: MathProcessor | None) -> None:
    """現在のMathProcessorをモジュールレベルで設定する。

    パイプライン開始時に呼び出し、処理全体で共有します。
    """
    global _current_processor
    _current_processor = proc


def get_current_processor() -> MathProcessor | None:
    """現在のMathProcessorを取得する。未設定の場合はNoneを返す。"""
    return _current_processor


def detect_math_in_commonmark(text: str) -> bool:
    """CommonMarkテキスト中の数式パターンを検出する（外部ツール呼び出しなし）。"""
    return bool(DISPLAY_MATH_PATTERN.search(text) or INLINE_MATH_PATTERN.search(text))


def detect_math_in_xml(text: str) -> bool:
    """XMLテキスト中のMathML要素を検出する。"""
    return bool(re.search(r'<math\b', text))


def check_math_tools() -> dict[str, bool]:
    """数式処理に必要な外部ツールの利用可否を確認する。

    Returns
    -------
    dict[str, bool]
        {"pandoc": bool, "node": bool, "sre": bool}
    """
    import shutil as _shutil
    pandoc_ok = _shutil.which("pandoc") is not None
    node_ok = _shutil.which("node") is not None
    sre_path = Path(__file__).parent.parent / "node_modules" / "speech-rule-engine"
    sre_ok = sre_path.exists()
    return {"pandoc": pandoc_ok, "node": node_ok, "sre": sre_ok}


def init_math_support(lang_code: str) -> MathProcessor:
    """言語コードからMathProcessorを初期化してシングルトンに設定する。

    Parameters
    ----------
    lang_code : str
        言語コード（例: "ja_JP", "en_US", "de_DE"）。

    Returns
    -------
    MathProcessor
        初期化されたMathProcessor。
    """
    sre_lang = SRE_LANG_MAP.get(lang_code, "en")
    proc = MathProcessor(sre_lang=sre_lang)
    set_current_processor(proc)
    return proc
