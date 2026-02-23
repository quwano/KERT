"""
TextGridとテキストのマッチング処理モジュール。

Montreal Forced Aligner (MFA) が生成したTextGridファイルの単語タイミング情報と
元テキストをマッチングし、XHTML用のspan要素とSMIL用のpar要素を生成します。
"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable

from text.processing import (
    normalize_text,
    escape_with_formatting,
    reading_pos_to_original,
    get_original_range,
)
from text.xhtml import (
    normalize_xhtml_text,
    xhtml_reading_pos_to_original,
    get_xhtml_original_range,
)
from text.common import (
    RUBY_PATTERN,
    UNDERLINE_PATTERN,
    STRONG_PATTERN,
    FRAME_PATTERN,
    IMAGE_PATTERN,
    READING_SUB_PATTERN,
    strip_formatting,
)
from core.config import PUNCTUATION_CHARS

# 句読点・記号のセット（単語の後に付加してspan化する）
PUNCTUATION = set(PUNCTUATION_CHARS)

# 区切り文字（句読点単位モードで使用）
# 日本語: 。、，  英語等: .,
SENTENCE_DELIMITERS = set("。、，.,")

# マッチング時にスキップする文字（スペース・句読点・括弧等）
_MATCHING_SKIP_RE = re.compile(r'[\s。、．，.,!！?？：:；;（）()「」『』\[\]【】｛｝{}・\-]')


def _normalize_for_matching(text: str) -> str:
    """マッチング用にテキストからスペース・句読点を除去する。"""
    return _MATCHING_SKIP_RE.sub('', text)


@dataclass
class MatchContext:
    """TextGridマッチング処理のコンテキスト情報。

    マッチング関数で共通して使用されるパラメータをグループ化します。

    Attributes
    ----------
    element_id_prefix : str
        要素IDのプレフィックス。例: "w" → "w0001"
    xhtml_path : str
        SMILから参照するXHTMLファイルの相対パス。
    audio_filename : str
        SMILから参照する音声ファイルの相対パス。
    """
    element_id_prefix: str
    xhtml_path: str
    audio_filename: str


@dataclass
class MatchingState:
    """マッチング処理の状態を保持するデータクラス。

    Attributes
    ----------
    text : str
        処理対象の元テキスト。
    text_reading : str
        正規化された読みテキスト。
    tg_intervals : list[tuple[str, float, float]]
        TextGridインターバルのリスト。
    reading_pos : int
        読みテキストでの現在位置。
    tg_index : int
        TextGridインターバルの現在インデックス。
    span_id : int
        次に使用するspan ID。
    spans : list[str]
        生成されたspan要素のリスト。
    smil_pars : list[str]
        生成されたSMIL par要素のリスト。
    is_xml : bool
        入力がXMLファイルからの場合True。
    """
    text: str
    text_reading: str
    tg_intervals: list[tuple[str, float, float]]
    reading_pos: int = 0
    tg_index: int = 0
    span_id: int = 0
    spans: list[str] = field(default_factory=list)
    smil_pars: list[str] = field(default_factory=list)
    is_xml: bool = False

    def get_range_func(self) -> Callable:
        """位置変換関数を返す。"""
        return get_xhtml_original_range if self.is_xml else get_original_range

    def get_pos_to_orig_func(self) -> Callable:
        """読み位置→元位置変換関数を返す。"""
        return xhtml_reading_pos_to_original if self.is_xml else reading_pos_to_original


class MatchingStrategy(ABC):
    """マッチング戦略の基底クラス。

    単語単位・句読点単位の両モードで共通するインターフェースを定義。
    """

    def __init__(self, context: MatchContext):
        self.context = context

    @abstractmethod
    def match(self, state: MatchingState) -> None:
        """マッチング処理を実行する。

        Parameters
        ----------
        state : MatchingState
            マッチング処理の状態。処理後に更新される。
        """
        pass

    def generate_element_id(self, span_id: int) -> str:
        """要素IDを生成する。"""
        return f"{self.context.element_id_prefix}{span_id:04d}"

    def add_span_with_timing(
        self,
        state: MatchingState,
        text: str,
        clip_begin: float,
        clip_end: float
    ) -> None:
        """タイミング付きspanを追加する。"""
        el_id = self.generate_element_id(state.span_id)
        state.spans.append(_generate_span_element(el_id, text, state.is_xml))
        state.smil_pars.append(_generate_smil_par(
            el_id, self.context.xhtml_path, self.context.audio_filename,
            clip_begin, clip_end
        ))
        state.span_id += 1

    def add_span_without_timing(self, state: MatchingState, text: str) -> None:
        """タイミングなしテキストを追加する。"""
        if text.strip():
            if state.is_xml:
                state.spans.append(text)
            else:
                state.spans.append(escape_with_formatting(text))


class UnkTokenProcessor:
    """<unk>トークンを処理するクラス。

    MFAが認識できなかった単語（<unk>）を処理します。
    連続する<unk>は次の認識済み単語までのテキストとしてまとめて処理されます。
    """

    def __init__(self, context: MatchContext):
        self.context = context

    def process(
        self,
        state: MatchingState,
        clip_begin: float,
        clip_end: float
    ) -> None:
        """<unk>トークンを処理する。

        Parameters
        ----------
        state : MatchingState
            マッチング処理の状態。処理後に更新される。
        clip_begin : float
            <unk>の開始時間。
        clip_end : float
            <unk>の終了時間。
        """
        get_range_func = state.get_range_func()
        pos_to_orig_func = state.get_pos_to_orig_func()

        # 連続する<unk>の最後のタイミングを取得
        unk_end_time = clip_end
        next_known_idx = state.tg_index + 1
        while next_known_idx < len(state.tg_intervals):
            if state.tg_intervals[next_known_idx][0] != "<unk>":
                break
            unk_end_time = state.tg_intervals[next_known_idx][2]
            next_known_idx += 1

        remaining = state.text_reading[state.reading_pos:]

        # 次の認識済み単語を読みテキストから探す
        if next_known_idx < len(state.tg_intervals):
            next_known_word = normalize_text(state.tg_intervals[next_known_idx][0]).lower()
            next_word_pos = remaining.find(next_known_word)

            if next_word_pos > 0:
                self._process_text_before_known_word(
                    state, get_range_func, next_word_pos,
                    clip_begin, unk_end_time
                )
                state.tg_index = next_known_idx
            elif next_word_pos == -1:
                self._process_entire_remaining_text(
                    state, pos_to_orig_func, clip_begin, clip_end
                )
                # 1つの<unk>のみ消費
                state.tg_index += 1
            else:
                # next_word_pos == 0: 次の認識済み単語がremaining先頭にある
                state.tg_index = next_known_idx
        else:
            # 残りのTextGrid全て<unk>の場合
            self._process_entire_remaining_text(
                state, pos_to_orig_func, clip_begin, unk_end_time
            )
            state.tg_index = next_known_idx

    def _process_text_before_known_word(
        self,
        state: MatchingState,
        get_range_func: Callable,
        next_word_pos: int,
        clip_begin: float,
        clip_end: float
    ) -> None:
        """次の認識済み単語までのテキストをspan化する。"""
        orig_start, orig_end = get_range_func(state.text, state.reading_pos, next_word_pos)
        unk_text = state.text[orig_start:orig_end]
        if unk_text.strip():
            el_id = f"{self.context.element_id_prefix}{state.span_id:04d}"
            state.spans.append(_generate_span_element(el_id, unk_text, state.is_xml))
            state.smil_pars.append(_generate_smil_par(
                el_id, self.context.xhtml_path, self.context.audio_filename,
                clip_begin, clip_end
            ))
            state.span_id += 1
        state.reading_pos += next_word_pos

    def _process_entire_remaining_text(
        self,
        state: MatchingState,
        pos_to_orig_func: Callable,
        clip_begin: float,
        clip_end: float
    ) -> None:
        """残りのテキスト全体をspan化する。"""
        orig_start = pos_to_orig_func(state.text, state.reading_pos)
        unk_text = state.text[orig_start:]
        if unk_text.strip():
            el_id = f"{self.context.element_id_prefix}{state.span_id:04d}"
            state.spans.append(_generate_span_element(el_id, unk_text, state.is_xml))
            state.smil_pars.append(_generate_smil_par(
                el_id, self.context.xhtml_path, self.context.audio_filename,
                clip_begin, clip_end
            ))
            state.span_id += 1
        state.reading_pos = len(state.text_reading)


def _generate_span_element(el_id: str, text: str, is_xml: bool = False) -> str:
    """span要素を生成する。"""
    if is_xml:
        # XMLの場合、すでにXHTMLタグを含んでいるのでそのまま使用
        return f'<span id="{el_id}">{text}</span>'
    else:
        return f'<span id="{el_id}">{escape_with_formatting(text)}</span>'


def _generate_smil_par(
    el_id: str,
    xhtml_path: str,
    audio_filename: str,
    clip_begin: float,
    clip_end: float
) -> str:
    """SMIL par要素を生成する。"""
    return f'''        <par id="par_{el_id}">
            <text src="{xhtml_path}#{el_id}"/>
            <audio src="{audio_filename}" clipBegin="{clip_begin:.3f}s" clipEnd="{clip_end:.3f}s"/>
        </par>'''


def _adjust_orig_start_for_bracket(text: str, orig_start: int) -> int:
    """orig_startが[...]{.frame/underline}構文の内部（[の直後）にある場合、[の位置まで戻す。

    reading_pos_to_original()は[...]{.frame/underline}構文の開始位置に到達すると、
    [の直後（構文内部）の位置を返す。テキストスライスで使用する場合、
    [を含めるために位置を調整する必要がある。
    """
    if orig_start > 0 and text[orig_start - 1] == '[':
        remaining = text[orig_start - 1:]
        if FRAME_PATTERN.match(remaining) or UNDERLINE_PATTERN.match(remaining):
            return orig_start - 1
    return orig_start


def has_unclosed_formatting(text: str) -> bool:
    """
    テキストに未閉じの書式記法があるかどうかをチェックする。

    句読点区切りモードで、書式記法の途中で区切りが発生しないようにするために使用。

    Parameters
    ----------
    text : str
        チェック対象のテキスト

    Returns
    -------
    bool
        未閉じの書式記法がある場合はTrue
    """
    # ルビ記法を除去（ルビは必ず閉じているので）
    temp = RUBY_PATTERN.sub('', text)

    # 読み替え記法を除去（2026-01-28追加）
    # CommonMarkで読み替え記法 [表示](+読み) を使用した場合、
    # この記法の [ が残ると「未閉じ」と誤判定され、
    # 句読点での区切りが機能しなくなる問題を修正。
    temp = READING_SUB_PATTERN.sub('', temp)

    # Underline記法を除去
    temp = UNDERLINE_PATTERN.sub('', temp)

    # Frame記法を除去
    temp = FRAME_PATTERN.sub('', temp)

    # Strong記法を除去
    temp = STRONG_PATTERN.sub('', temp)

    # 残っている [ があれば、書式記法が未閉じ
    # ただし、]{.underline} や ]{.frame} の一部である ] だけが残っている場合は除外
    if '[' in temp and ']{.underline}' not in temp and ']{.frame}' not in temp:
        return True

    # ** の数が奇数なら、Strong記法が未閉じ
    if temp.count('**') % 2 != 0:
        return True

    # ~ の数が奇数なら、Subscript記法 (~text~) が未閉じ
    if temp.count('~') % 2 != 0:
        return True

    # ^ の数が奇数なら、Superscript記法 (^text^) が未閉じ
    if temp.count('^') % 2 != 0:
        return True

    return False


def _process_underline_span(
    text: str,
    text_reading: str,
    reading_pos: int,
    tg_intervals: list[tuple[str, float, float]],
    tg_index: int,
    span_id: int,
    element_id_prefix: str,
    xhtml_path: str,
    audio_filename: str,
) -> tuple[str, str, int, int, int] | None:
    """
    現在位置が傍線記法の開始であれば、傍線全体を1つのspanとして処理する。

    傍線記法 [内容]{.underline} を検出し、内容全体を1つのspanにまとめる。
    複数のTextGridインターバルを消費し、clipBeginは最初、clipEndは最後の時刻を使用。

    Parameters
    ----------
    text : str
        元テキスト（書式記法を含む）。
    text_reading : str
        正規化された読みテキスト。
    reading_pos : int
        読みテキストでの現在位置。
    tg_intervals : list[tuple[str, float, float]]
        TextGridインターバルのリスト。
    tg_index : int
        現在のTextGridインデックス。
    span_id : int
        現在のspan ID。
    element_id_prefix : str
        要素IDのプレフィックス。
    xhtml_path : str
        XHTMLファイルの相対パス。
    audio_filename : str
        音声ファイルの相対パス。

    Returns
    -------
    tuple[str, str, int, int, int] | None
        傍線記法が見つかった場合:
        - span : 生成されたspan要素
        - smil_par : 生成されたSMIL par要素
        - next_span_id : 次のspan ID
        - next_tg_index : 次のTextGridインデックス
        - next_reading_pos : 次の読みテキスト位置
        傍線記法でない場合はNone。
    """
    # 現在の読みテキスト位置に対応する元テキスト位置を取得
    orig_pos = reading_pos_to_original(text, reading_pos)
    remaining_orig = text[orig_pos:]

    # 傍線記法のチェック
    underline_match = UNDERLINE_PATTERN.match(remaining_orig)
    if not underline_match:
        return None

    # 傍線の内容と読みテキスト長を取得
    underline_full = underline_match.group(0)  # [内容]{.underline}
    underline_inner = underline_match.group(1)  # 内容
    underline_reading = strip_formatting(underline_inner).lower()
    underline_reading_len = len(underline_reading)

    # 傍線の読みテキストに対応するTextGridインターバルを消費
    clip_begin: float | None = None
    clip_end: float = 0.0
    matched_reading_len = 0

    while tg_index < len(tg_intervals) and matched_reading_len < underline_reading_len:
        tg_word, tg_begin, tg_end = tg_intervals[tg_index]
        tg_word_normalized = normalize_text(tg_word).lower()

        # 空のインターバルや<unk>はスキップ
        if not tg_word_normalized or tg_word == "<unk>":
            if clip_begin is None:
                clip_begin = tg_begin
            clip_end = tg_end
            tg_index += 1
            continue

        # このTextGrid単語が傍線の読みテキストに含まれるかチェック
        remaining_underline_reading = underline_reading[matched_reading_len:]
        if remaining_underline_reading.startswith(tg_word_normalized):
            if clip_begin is None:
                clip_begin = tg_begin
            clip_end = tg_end
            matched_reading_len += len(tg_word_normalized)
            tg_index += 1
        else:
            # マッチしない場合、ループを抜ける
            break

    # spanを生成
    if clip_begin is not None:
        el_id = f"{element_id_prefix}{span_id:04d}"
        span = _generate_span_element(el_id, underline_full, is_xml=False)
        smil_par = _generate_smil_par(el_id, xhtml_path, audio_filename, clip_begin, clip_end)

        # 傍線の後の句読点も含める
        orig_end = orig_pos + len(underline_full)
        while orig_end < len(text) and text[orig_end] in PUNCTUATION:
            orig_end += 1
        punct_count = orig_end - (orig_pos + len(underline_full))

        next_reading_pos = reading_pos + underline_reading_len + punct_count
        return span, smil_par, span_id + 1, tg_index, next_reading_pos

    return None


def match_text_to_textgrid(
    text: str,
    tg_intervals: list[tuple[str, float, float]],
    tg_index: int,
    span_id: int,
    element_id_prefix: str,
    xhtml_path: str,
    audio_filename: str,
    is_xml: bool = False
) -> tuple[list[str], list[str], int, int]:
    """
    テキストをTextGridのインターバルにマッチングしてspanとSMILを生成する。

    元テキストの各単語をTextGridのタイミング情報とマッチングし、
    XHTML用のspan要素とSMIL用のpar要素を生成します。
    ルビ記法を含むテキストにも対応しています。

    Parameters
    ----------
    text : str
        マッチング対象のテキスト。ルビ記法 ``[漢字](-ふりがな)`` を含む場合があります。
    tg_intervals : list[tuple[str, float, float]]
        TextGridから抽出したインターバルのリスト。
        各要素は (単語, 開始時間, 終了時間) のタプル。
    tg_index : int
        処理を開始するtg_intervalsのインデックス。
    span_id : int
        span要素のID番号の開始値。
    element_id_prefix : str
        要素IDのプレフィックス。例: "w" → "w0001", "chapter1_w" → "chapter1_w0001"
    xhtml_path : str
        SMILから参照するXHTMLファイルの相対パス。例: "../text/content.xhtml"
    audio_filename : str
        SMILから参照する音声ファイルの相対パス。例: "../audio/audio.mp3"

    Returns
    -------
    tuple[list[str], list[str], int, int]
        - spans : list[str]
            生成されたspan要素のリスト。
        - smil_pars : list[str]
            生成されたSMIL par要素のリスト。
        - next_span_id : int
            次に使用すべきspan ID番号。
        - next_tg_index : int
            次に処理すべきtg_intervalsのインデックス。

    Notes
    -----
    マッチングアルゴリズム:
    1. テキストを正規化（ルビ→読み、全角→半角）してマッチング用テキストを作成
    2. TextGridの各単語を正規化してマッチング用テキストから検索
    3. マッチ位置を元テキストの位置に変換してspan要素を生成
    4. 単語の後の句読点は同じspanに含める

    <unk>トークンの処理:
    MFAが認識できなかった単語は<unk>として出力されます。
    連続する<unk>は次の認識済み単語までのテキストとしてまとめて処理されます。
    """
    spans: list[str] = []
    smil_pars: list[str] = []

    # テキスト全体の読みテキストを作成（XMLの場合はXHTMLタグを除去）
    if is_xml:
        text_reading: str = normalize_xhtml_text(text).lower()
        get_range_func = get_xhtml_original_range
        pos_to_orig_func = xhtml_reading_pos_to_original
    else:
        text_reading = normalize_text(text).lower()
        get_range_func = get_original_range
        pos_to_orig_func = reading_pos_to_original

    reading_pos: int = 0  # 読みテキストでの現在位置

    while reading_pos < len(text_reading) and tg_index < len(tg_intervals):
        # 傍線記法のチェック（テキストファイルの場合のみ）
        if not is_xml:
            underline_result = _process_underline_span(
                text, text_reading, reading_pos,
                tg_intervals, tg_index, span_id,
                element_id_prefix, xhtml_path, audio_filename
            )
            if underline_result:
                span, smil_par, span_id, tg_index, reading_pos = underline_result
                spans.append(span)
                smil_pars.append(smil_par)
                continue

        tg_word, clip_begin, clip_end = tg_intervals[tg_index]

        # 正規化してマッチング
        remaining = text_reading[reading_pos:]
        tg_word_normalized = normalize_text(tg_word).lower()

        # 空のインターバルはスキップ（テキスト消費なし）
        if not tg_word_normalized:
            tg_index += 1
            continue

        # <unk>の場合の特別処理
        if tg_word == "<unk>":
            spans_unk, smil_unk, span_id, tg_index, reading_pos = _process_unk_tokens(
                text, text_reading, reading_pos,
                tg_intervals, tg_index, clip_begin, clip_end,
                span_id, element_id_prefix, xhtml_path, audio_filename,
                is_xml=is_xml
            )
            spans.extend(spans_unk)
            smil_pars.extend(smil_unk)
            continue

        idx = remaining.find(tg_word_normalized)

        if idx != -1:
            # マッチ位置より前にテキストがあれば、spanなしで追加
            if idx > 0:
                orig_skip_start, orig_skip_end = get_range_func(text, reading_pos, idx)
                skipped_text = text[orig_skip_start:orig_skip_end]
                if skipped_text.strip():
                    if is_xml:
                        spans.append(skipped_text)
                    else:
                        spans.append(escape_with_formatting(skipped_text))

            # マッチした単語の元テキストでの範囲を計算
            word_reading_start = reading_pos + idx
            word_reading_len = len(tg_word_normalized)
            orig_word_start, orig_word_end = get_range_func(text, word_reading_start, word_reading_len)

            # 単語の後に続く句読点と空白を取得（元テキストで）
            # 【修正 2026-02-08】全角スペース・半角スペースも含める
            end_pos = orig_word_end
            while end_pos < len(text) and (text[end_pos] in PUNCTUATION or text[end_pos] in ' \t　'):
                end_pos += 1

            # spanに含めるテキスト（単語＋句読点＋空白）
            span_text = text[orig_word_start:end_pos]

            el_id = f"{element_id_prefix}{span_id:04d}"
            spans.append(_generate_span_element(el_id, span_text, is_xml))
            smil_pars.append(_generate_smil_par(el_id, xhtml_path, audio_filename, clip_begin, clip_end))

            span_id += 1
            # 読みテキストでの位置を更新（句読点も含めて）
            punct_count = end_pos - orig_word_end
            reading_pos = word_reading_start + word_reading_len + punct_count
            tg_index += 1
        else:
            # マッチしない場合、次のTextGrid単語を先読みしてスキップ範囲を決定
            next_reading_match_pos = _find_next_match_position(
                remaining, reading_pos, tg_intervals, tg_index
            )

            # 次のマッチが見つかった場合、その手前までを音声付きspanとして追加
            # 【修正】元は音声なしでテキストのみ追加していたが、音声付きに変更
            if next_reading_match_pos != -1 and next_reading_match_pos > reading_pos:
                orig_skip_start, orig_skip_end = get_range_func(
                    text, reading_pos, next_reading_match_pos - reading_pos
                )
                skipped_text = text[orig_skip_start:orig_skip_end]
                if skipped_text.strip():
                    # 現在のtg_intervalの音声を使用してspan生成
                    el_id = f"{element_id_prefix}{span_id:04d}"
                    spans.append(_generate_span_element(el_id, skipped_text, is_xml))
                    smil_pars.append(_generate_smil_par(
                        el_id, xhtml_path, audio_filename, clip_begin, clip_end
                    ))
                    span_id += 1
                reading_pos = next_reading_match_pos
                tg_index += 1
            else:
                # 現在のテキスト内に今後のマッチがない場合
                # 【修正】残りテキストがあれば、音声付きspanを生成してからループを抜ける
                # 元のコード: break
                if reading_pos < len(text_reading) and tg_index < len(tg_intervals):
                    orig_start = pos_to_orig_func(text, reading_pos)
                    orig_start = _adjust_orig_start_for_bracket(text, orig_start)
                    remaining_text = text[orig_start:]
                    if remaining_text.strip():
                        # 残りテキストに対応する音声範囲を推定
                        # 現在のtg_intervalのclip_beginから、数個先のclip_endまで
                        remaining_clip_begin = clip_begin
                        # 残りのtg_intervalsから終了時間を取得（最大5個先まで）
                        end_idx = min(tg_index + 5, len(tg_intervals) - 1)
                        remaining_clip_end = tg_intervals[end_idx][2]

                        el_id = f"{element_id_prefix}{span_id:04d}"
                        spans.append(_generate_span_element(el_id, remaining_text, is_xml))
                        smil_pars.append(_generate_smil_par(
                            el_id, xhtml_path, audio_filename,
                            remaining_clip_begin, remaining_clip_end
                        ))
                        span_id += 1
                        tg_index = end_idx + 1
                break

    # テキストの残りがあれば音声付きspanとして追加
    # 【修正】元は最後のspanにテキストを追加するだけだったが、音声同期も追加
    if reading_pos < len(text_reading):
        orig_start = pos_to_orig_func(text, reading_pos)
        orig_start = _adjust_orig_start_for_bracket(text, orig_start)
        remaining_text = text[orig_start:]
        if remaining_text.strip():
            if smil_pars:
                # 最後のSMILから終了時間を取得し、残りテキストに対応する音声範囲を推定
                # 最後のSMILのclipEndを延長するか、tg_indexから数個先のclip_endを使用
                if tg_index < len(tg_intervals):
                    # まだtg_intervalsが残っている場合
                    end_idx = min(tg_index + 5, len(tg_intervals) - 1)
                    remaining_clip_begin = tg_intervals[tg_index][1]
                    remaining_clip_end = tg_intervals[end_idx][2]
                else:
                    # tg_intervalsの終端に達している場合、最後のintervalを使用
                    remaining_clip_begin = tg_intervals[-1][1]
                    remaining_clip_end = tg_intervals[-1][2]

                el_id = f"{element_id_prefix}{span_id:04d}"
                spans.append(_generate_span_element(el_id, remaining_text, is_xml))
                smil_pars.append(_generate_smil_par(
                    el_id, xhtml_path, audio_filename,
                    remaining_clip_begin, remaining_clip_end
                ))
                span_id += 1
            else:
                # smil_parsが空の場合は音声なしで追加（フォールバック）
                if is_xml:
                    spans.append(remaining_text)
                else:
                    spans.append(escape_with_formatting(remaining_text))
    else:
        # 読みテキストは全て消費されたが、元テキストの末尾に発音されない文字（括弧など）が残っている可能性
        # 【修正 2026-02-08】句読点単位モードと同様に、元テキストの末尾までをチェック
        orig_start = pos_to_orig_func(text, len(text_reading))
        orig_start = _adjust_orig_start_for_bracket(text, orig_start)
        remaining_text = text[orig_start:]
        if remaining_text.strip():
            # 発音されない記号のみなので、テキストのみ追加（音声なし）
            if is_xml:
                spans.append(remaining_text)
            else:
                spans.append(escape_with_formatting(remaining_text))

    return spans, smil_pars, span_id, tg_index


def match_text_to_textgrid_punctuation(
    text: str,
    tg_intervals: list[tuple[str, float, float]],
    tg_index: int,
    span_id: int,
    element_id_prefix: str,
    xhtml_path: str,
    audio_filename: str,
    is_xml: bool = False
) -> tuple[list[str], list[str], int, int]:
    """
    句読点単位でテキストをTextGridにマッチングしてspanとSMILを生成する。

    「。」または「、」までの複数単語を1つのspanにグループ化し、
    clipBeginは最初の単語の開始時間、clipEndは最後の単語の終了時間とします。

    Parameters
    ----------
    text : str
        マッチング対象のテキスト。ルビ記法を含む場合があります。
    tg_intervals : list[tuple[str, float, float]]
        TextGridから抽出したインターバルのリスト。
    tg_index : int
        処理を開始するtg_intervalsのインデックス。
    span_id : int
        span要素のID番号の開始値。
    element_id_prefix : str
        要素IDのプレフィックス。
    xhtml_path : str
        SMILから参照するXHTMLファイルの相対パス。
    audio_filename : str
        SMILから参照する音声ファイルの相対パス。

    Returns
    -------
    tuple[list[str], list[str], int, int]
        - spans : 生成されたspan要素のリスト
        - smil_pars : 生成されたSMIL par要素のリスト
        - next_span_id : 次に使用すべきspan ID番号
        - next_tg_index : 次に処理すべきtg_intervalsのインデックス
    """
    spans: list[str] = []
    smil_pars: list[str] = []

    # XMLの場合はXHTMLタグを除去した関数を使用
    if is_xml:
        text_reading: str = normalize_xhtml_text(text).lower()
        get_range_func = get_xhtml_original_range
        pos_to_orig_func = xhtml_reading_pos_to_original
    else:
        text_reading = normalize_text(text).lower()
        get_range_func = get_original_range
        pos_to_orig_func = reading_pos_to_original

    reading_pos: int = 0

    # グループ用の状態変数
    group_orig_start: int = 0
    group_clip_begin: float | None = None
    group_clip_end: float = 0.0

    def _flush_group(orig_end: int) -> None:
        """現在のグループをspanとして出力する。"""
        nonlocal span_id, group_orig_start, group_clip_begin, group_clip_end

        if group_clip_begin is not None and orig_end > group_orig_start:
            group_text = text[group_orig_start:orig_end]
            if group_text.strip():
                el_id = f"{element_id_prefix}{span_id:04d}"
                spans.append(_generate_span_element(el_id, group_text, is_xml))
                smil_pars.append(_generate_smil_par(el_id, xhtml_path, audio_filename, group_clip_begin, group_clip_end))
                span_id += 1

        # グループをリセット
        group_clip_begin = None

    while reading_pos < len(text_reading) and tg_index < len(tg_intervals):
        tg_word, clip_begin, clip_end = tg_intervals[tg_index]

        # 正規化してマッチング
        remaining = text_reading[reading_pos:]
        tg_word_normalized = normalize_text(tg_word).lower()

        # 空のインターバルはスキップ（テキスト消費なし）
        if not tg_word_normalized:
            tg_index += 1
            continue

        # <unk>の場合の特別処理
        if tg_word == "<unk>":
            # 連続する<unk>の最後のタイミングを取得
            unk_end_time = clip_end
            next_known_idx = tg_index + 1
            while next_known_idx < len(tg_intervals):
                if tg_intervals[next_known_idx][0] != "<unk>":
                    break
                unk_end_time = tg_intervals[next_known_idx][2]
                next_known_idx += 1

            # 次の認識済み単語を探す
            if next_known_idx < len(tg_intervals):
                next_known_word = normalize_text(tg_intervals[next_known_idx][0]).lower()
                next_word_pos = remaining.find(next_known_word)
                if next_word_pos > 0:
                    # 現在位置から次の単語までのテキストを処理
                    orig_start, orig_end = get_range_func(text, reading_pos, next_word_pos)
                    unk_text = text[orig_start:orig_end]

                    # グループ開始時刻を記録
                    if group_clip_begin is None:
                        group_clip_begin = clip_begin
                        group_orig_start = orig_start

                    group_clip_end = unk_end_time
                    reading_pos += next_word_pos

                    # 区切り文字で終わっているかチェック
                    # ただし、未閉じの書式記法がある場合は区切らない（XMLは除く）
                    # また、]{.frame}や]{.underline}内の'.'は区切り文字として扱わない
                    if unk_text and unk_text[-1] in SENTENCE_DELIMITERS and not (
                        unk_text[-1] == '.' and len(unk_text) >= 2 and unk_text[-2] == '{'
                    ):
                        group_text = text[group_orig_start:orig_end]
                        if is_xml or not has_unclosed_formatting(group_text):
                            _flush_group(orig_end)
                    # 連続する全角スペースがある場合も区切る（選択肢グループ間の区切り）
                    # 例: ①　a－毛織物　b－綿織物　c－原綿　　　②　a－毛織物　...
                    # 「　　　」で区切ることで各選択肢グループに個別のタイミングを付与
                    elif not is_xml and unk_text and '\u3000\u3000' in unk_text:
                        group_text = text[group_orig_start:orig_end]
                        if not has_unclosed_formatting(group_text):
                            # 次の認識済み単語の開始時刻でclipEndを設定（連続タイミング）
                            group_clip_end = tg_intervals[next_known_idx][1]
                            _flush_group(orig_end)
                elif next_word_pos == -1:
                    # 次の認識済み単語がこの段落内に存在しない場合
                    # 残りのテキスト全体を処理して終了
                    # ただし、1つの<unk>トークンのみ消費（次の段落用に残す）
                    # 次の認識済み単語の開始時間を使用（音声が途中で切れないように）
                    next_known_clip_begin = tg_intervals[next_known_idx][1]
                    orig_start = pos_to_orig_func(text, reading_pos)
                    orig_start = _adjust_orig_start_for_bracket(text, orig_start)
                    if group_clip_begin is None:
                        group_clip_begin = clip_begin
                        group_orig_start = orig_start
                    group_clip_end = next_known_clip_begin  # 次の認識済み単語の開始時間を使用
                    # 段落末尾までをグループに含めて終了
                    _flush_group(len(text))
                    reading_pos = len(text_reading)
                    # 1つの<unk>のみ消費
                    tg_index += 1
                    continue
            else:
                # TextGrid終端の場合、残りのテキスト全体を処理して終了
                orig_start = pos_to_orig_func(text, reading_pos)
                orig_start = _adjust_orig_start_for_bracket(text, orig_start)
                if group_clip_begin is None:
                    group_clip_begin = clip_begin
                    group_orig_start = orig_start
                group_clip_end = unk_end_time  # 連続する<unk>の最後のタイミングを使用
                # 段落末尾までをグループに含めて終了
                _flush_group(len(text))
                reading_pos = len(text_reading)
                tg_index = next_known_idx
                continue

            tg_index = next_known_idx
            continue

        idx = remaining.find(tg_word_normalized)

        if idx != -1:
            # マッチした単語の元テキストでの範囲を計算
            word_reading_start = reading_pos + idx
            word_reading_len = len(tg_word_normalized)
            orig_word_start, orig_word_end = get_range_func(text, word_reading_start, word_reading_len)

            # マッチ前にスキップテキストがある場合の処理
            if idx > 0 and group_clip_begin is None:
                orig_skip_start, orig_skip_end = get_range_func(text, reading_pos, idx)
                skipped_text = text[orig_skip_start:orig_skip_end]

                # スキップテキスト内の最後の区切り文字の位置を探す
                # ただし、]{.frame}や]{.underline}内の'.'は区切り文字として扱わない
                last_delim_idx = -1
                for i, ch in enumerate(skipped_text):
                    if ch in SENTENCE_DELIMITERS:
                        if ch == '.' and i > 0 and skipped_text[i - 1] == '{':
                            continue  # ]{.frame}や]{.underline}の一部
                        last_delim_idx = i

                if last_delim_idx != -1:
                    # 区切り文字までの部分を別のspan（タイミングなし）として出力
                    untimed_text = skipped_text[:last_delim_idx + 1]
                    if untimed_text.strip():
                        if is_xml:
                            spans.append(untimed_text)
                        else:
                            spans.append(escape_with_formatting(untimed_text))
                    # 区切り文字の後からグループを開始
                    remaining_skip = skipped_text[last_delim_idx + 1:]
                    if remaining_skip.strip():
                        # 残りのスキップテキストがある場合、それをグループの開始とする
                        group_orig_start = orig_skip_start + last_delim_idx + 1
                    else:
                        # 残りがない場合、マッチした単語からグループを開始
                        group_orig_start = orig_word_start
                else:
                    # 区切り文字がない場合、スキップテキスト全体をグループの開始とする
                    group_orig_start = orig_skip_start

                group_clip_begin = clip_begin
            elif group_clip_begin is None:
                # スキップテキストがない場合
                group_clip_begin = clip_begin
                group_orig_start = orig_word_start

            # 単語の後に続く句読点を取得（元テキストで）
            # ただし、]{.frame}や]{.underline}内の'.'は句読点として扱わない
            end_pos = orig_word_end
            while end_pos < len(text) and text[end_pos] in PUNCTUATION:
                if text[end_pos] == '.' and end_pos > 0 and text[end_pos - 1] == '{':
                    break  # ]{.frame}や]{.underline}の一部
                end_pos += 1

            group_clip_end = clip_end

            # 読みテキストでの位置を更新（句読点も含めて）
            punct_count = end_pos - orig_word_end
            reading_pos = word_reading_start + word_reading_len + punct_count
            tg_index += 1

            # 区切り文字（。、）で終わっているかチェック
            # ただし、未閉じの書式記法がある場合は区切らない（XMLは除く）
            # また、]{.frame}や]{.underline}内の'.'は区切り文字として扱わない
            if end_pos > orig_word_start and text[end_pos - 1] in SENTENCE_DELIMITERS and not (
                text[end_pos - 1] == '.' and end_pos >= 2 and text[end_pos - 2] == '{'
            ):
                group_text = text[group_orig_start:end_pos]
                if is_xml or not has_unclosed_formatting(group_text):
                    _flush_group(end_pos)
        else:
            # マッチしない場合、次のTextGrid単語を先読みしてスキップ範囲を決定
            next_reading_match_pos = _find_next_match_position(
                remaining, reading_pos, tg_intervals, tg_index
            )

            if next_reading_match_pos != -1 and next_reading_match_pos > reading_pos:
                # 次のマッチが見つかった場合、その手前までのテキストを処理
                skip_len = next_reading_match_pos - reading_pos
                orig_skip_start, orig_skip_end = get_range_func(text, reading_pos, skip_len)
                skipped_text = text[orig_skip_start:orig_skip_end]

                if group_clip_begin is not None:
                    # グループ進行中: スキップテキストをグループに含める
                    pass  # group_orig_start は変更しない（グループ継続）
                elif skipped_text.strip():
                    # グループ未開始: スキップテキストをタイミングなしで出力
                    if is_xml:
                        spans.append(skipped_text)
                    else:
                        spans.append(escape_with_formatting(skipped_text))

                reading_pos = next_reading_match_pos
                tg_index += 1
            else:
                # 現在のテキスト内に今後のマッチがない場合、ループを抜ける
                # （次のTextGrid単語は次の段落に属する）
                break

    # 段落末尾：残りのグループをフラッシュ
    # 残りテキストも含めて段落末尾までをspanに含める
    if group_clip_begin is not None:
        # 段落末尾までを含める（残りテキストもspanに含める）
        _flush_group(len(text))
    elif reading_pos < len(text_reading):
        # グループが開始されていない場合、残りテキストを処理
        orig_start = pos_to_orig_func(text, reading_pos)
        orig_start = _adjust_orig_start_for_bracket(text, orig_start)
        remaining_text = text[orig_start:]
        # 残りテキストの読みを正規化して、読み上げられる内容があるか確認
        remaining_reading = normalize_text(remaining_text).strip() if not is_xml else normalize_xhtml_text(remaining_text).strip()
        # 読み上げ可能な文字（ひらがな、カタカナ、漢字、英数字）が含まれるかチェック
        import re
        has_speakable = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF\u3400-\u4DBFa-zA-Z0-9]', remaining_reading))

        if remaining_text.strip():
            if has_speakable:
                # 読み上げられる内容がある場合、音声付きspanとして追加
                if tg_index < len(tg_intervals):
                    end_idx = min(tg_index + 5, len(tg_intervals) - 1)
                    remaining_clip_begin = tg_intervals[tg_index][1]
                    remaining_clip_end = tg_intervals[end_idx][2]
                elif len(tg_intervals) > 0:
                    # tg_intervalsの終端に達している場合、最後のintervalを使用
                    remaining_clip_begin = tg_intervals[-1][1]
                    remaining_clip_end = tg_intervals[-1][2]
                else:
                    remaining_clip_begin = 0.0
                    remaining_clip_end = 0.0

                el_id = f"{element_id_prefix}{span_id:04d}"
                spans.append(_generate_span_element(el_id, remaining_text, is_xml))
                smil_pars.append(_generate_smil_par(
                    el_id, xhtml_path, audio_filename,
                    remaining_clip_begin, remaining_clip_end
                ))
                span_id += 1
            else:
                # 記号のみ（読み上げられない）の場合、テキストのみ追加（音声なし）
                if is_xml:
                    spans.append(remaining_text)
                else:
                    spans.append(escape_with_formatting(remaining_text))
    else:
        # 読みテキストは全て消費されたが、元テキストの末尾に発音されない文字（括弧など）が残っている可能性
        # to_reading()で（）が除去されるため、元テキスト末尾の）等がここで処理される
        orig_start = pos_to_orig_func(text, len(text_reading))
        orig_start = _adjust_orig_start_for_bracket(text, orig_start)
        remaining_text = text[orig_start:]
        if remaining_text.strip():
            # 発音されない記号のみなので、テキストのみ追加（音声なし）
            if is_xml:
                spans.append(remaining_text)
            else:
                spans.append(escape_with_formatting(remaining_text))

    return spans, smil_pars, span_id, tg_index


def _process_unk_tokens(
    text: str,
    text_reading: str,
    reading_pos: int,
    tg_intervals: list[tuple[str, float, float]],
    tg_index: int,
    clip_begin: float,
    clip_end: float,
    span_id: int,
    element_id_prefix: str,
    xhtml_path: str,
    audio_filename: str,
    is_xml: bool = False
) -> tuple[list[str], list[str], int, int, int]:
    """
    連続する<unk>トークンを処理する。

    MFAが認識できなかった単語（<unk>）を処理します。
    連続する<unk>は次の認識済み単語までのテキストとしてまとめて
    1つのspan要素に変換されます。

    Parameters
    ----------
    text : str
        元テキスト。
    text_reading : str
        正規化された読みテキスト。
    reading_pos : int
        読みテキストでの現在位置。
    tg_intervals : list[tuple[str, float, float]]
        TextGridインターバルのリスト。
    tg_index : int
        現在の<unk>トークンのインデックス。
    clip_begin : float
        <unk>の開始時間。
    clip_end : float
        <unk>の終了時間。
    span_id : int
        現在のspan ID番号。
    element_id_prefix : str
        要素IDのプレフィックス。
    xhtml_path : str
        XHTMLファイルの相対パス。
    audio_filename : str
        音声ファイルの相対パス。

    Returns
    -------
    tuple[list[str], list[str], int, int, int]
        - spans : 生成されたspan要素のリスト
        - smil_pars : 生成されたSMIL par要素のリスト
        - next_span_id : 次のspan ID番号
        - next_tg_index : 次のTextGridインデックス
        - next_reading_pos : 次の読みテキスト位置
    """
    spans: list[str] = []
    smil_pars: list[str] = []

    # 位置変換関数の選択
    if is_xml:
        get_range_func = get_xhtml_original_range
        pos_to_orig_func = xhtml_reading_pos_to_original
    else:
        get_range_func = get_original_range
        pos_to_orig_func = reading_pos_to_original

    # 連続する<unk>の最後のタイミングを取得
    unk_end_time = clip_end
    next_known_idx = tg_index + 1
    while next_known_idx < len(tg_intervals):
        if tg_intervals[next_known_idx][0] != "<unk>":
            break
        unk_end_time = tg_intervals[next_known_idx][2]  # maxTime
        next_known_idx += 1

    remaining = text_reading[reading_pos:]

    # 次の認識済み単語を読みテキストから探す
    if next_known_idx < len(tg_intervals):
        next_known_word = normalize_text(tg_intervals[next_known_idx][0]).lower()
        next_word_pos = remaining.find(next_known_word)
        if next_word_pos > 0:
            # 現在位置から次の単語までのテキストを<unk>のタイミングでspan化
            orig_start, orig_end = get_range_func(text, reading_pos, next_word_pos)
            unk_text = text[orig_start:orig_end]
            if unk_text.strip():
                el_id = f"{element_id_prefix}{span_id:04d}"
                spans.append(_generate_span_element(el_id, unk_text, is_xml))
                smil_pars.append(_generate_smil_par(el_id, xhtml_path, audio_filename, clip_begin, unk_end_time))
                span_id += 1
            reading_pos += next_word_pos
        elif next_word_pos == -1:
            # 次の認識済み単語が現在のテキスト内にない場合、残り全体をspan化
            # ただし、1つの<unk>トークンのみ消費（次の段落用に残す）
            orig_start = pos_to_orig_func(text, reading_pos)
            orig_start = _adjust_orig_start_for_bracket(text, orig_start)
            unk_text = text[orig_start:]
            if unk_text.strip():
                el_id = f"{element_id_prefix}{span_id:04d}"
                spans.append(_generate_span_element(el_id, unk_text, is_xml))
                # この段落には最初の<unk>のタイミングのみを使用
                smil_pars.append(_generate_smil_par(el_id, xhtml_path, audio_filename, clip_begin, clip_end))
                span_id += 1
            reading_pos = len(text_reading)
            # 重要: 1つの<unk>のみ消費。next_known_idxではなくtg_index+1を返す
            return spans, smil_pars, span_id, tg_index + 1, reading_pos
        # next_word_pos == 0 の場合: 次の認識済み単語がremaining先頭にあるので、
        # <unk>は現在のテキスト内に対応する部分がない。何もしない。
    else:
        # 残りのTextGrid全て<unk>の場合、残りテキスト全体をspan化
        orig_start = pos_to_orig_func(text, reading_pos)
        orig_start = _adjust_orig_start_for_bracket(text, orig_start)
        unk_text = text[orig_start:]
        if unk_text.strip():
            el_id = f"{element_id_prefix}{span_id:04d}"
            spans.append(_generate_span_element(el_id, unk_text, is_xml))
            smil_pars.append(_generate_smil_par(el_id, xhtml_path, audio_filename, clip_begin, unk_end_time))
            span_id += 1
        reading_pos = len(text_reading)

    return spans, smil_pars, span_id, next_known_idx, reading_pos


def _resync_tg_index(
    paragraph: str,
    tg_intervals: list[tuple[str, float, float]],
    tg_index: int,
    is_xml: bool = False,
    max_backward_search: int = 50,
    max_forward_search: int = 150  # 前方検索も制限（遠くの同名単語への誤ジャンプ防止）
) -> int:
    """
    段落の最初の単語に基づいて tg_index を再同期する。

    tg_indexが遅れている場合は前方検索、進みすぎている場合は後方検索を行い、
    最も適切な位置を見つける。

    Parameters
    ----------
    paragraph : str
        処理対象の段落テキスト。
    tg_intervals : list[tuple[str, float, float]]
        TextGridインターバルのリスト。
    tg_index : int
        現在のTextGridインデックス。
    is_xml : bool
        入力がXMLの場合True。
    max_backward_search : int
        後方検索の最大範囲（エントリ数）。デフォルトは50。
    max_forward_search : int
        前方検索の最大範囲（エントリ数）。デフォルトは150。

    Returns
    -------
    int
        調整後のtg_index。マッチが見つからない場合は元のtg_indexを返す。
    """
    # 段落を正規化して最初の単語を抽出
    if is_xml:
        text_reading = normalize_xhtml_text(paragraph).lower()
    else:
        text_reading = normalize_text(paragraph).lower()

    if not text_reading.strip():
        return tg_index

    # 先頭の空白と箇条書き記号等を除去（◇・●■□▪▸►など）
    # これらの記号はTextGridには含まれないため、マッチング前に除去する
    import re
    # 先頭の空白（全角・半角）を除去
    text_reading = text_reading.lstrip()
    # 箇条書き記号を除去
    text_reading = re.sub(r'^[◇◆●○■□▪▫▸►・\-\*]+\s*', '', text_reading)

    if not text_reading.strip():
        return tg_index

    # 現在のtg_indexが既にマッチしているかチェック
    if tg_index < len(tg_intervals):
        current_word = normalize_text(tg_intervals[tg_index][0]).lower()
        if current_word and text_reading.startswith(current_word):
            return tg_index  # 既に正しい位置

    def _score_match(start_idx: int, distance_from_current: int) -> int:
        """指定位置からのマッチスコアを計算（距離ペナルティ付き）"""
        tg_word = tg_intervals[start_idx][0]

        # <unk>の場合、後続の単語でマッチングを試みる
        # 修正（2026-01-28）: 連続マッチを考慮してスコアを計算
        # 問題: 58行目「２　国は、すべての...」を処理する際、<unk>の後の「すべて」が
        # 57行目の<unk>([1439])の後にも存在するため、誤った位置にマッチしていた。
        # 正しい位置[1456]では「国」→「は」→「すべて」と連続マッチするため、
        # 連続マッチ数を考慮することで正しい位置を選択できるようにする。
        if tg_word == "<unk>":
            # <unk>の後の最初の認識済み単語を探す
            first_match_idx = -1
            for k in range(start_idx + 1, min(start_idx + 5, len(tg_intervals))):
                next_tg_word = tg_intervals[k][0]
                if next_tg_word and next_tg_word != "<unk>":
                    next_word_normalized = normalize_text(next_tg_word).lower()
                    # テキストの先頭付近（最初の10文字以内）にこの単語があるか
                    pos = text_reading[:20].find(next_word_normalized)
                    if pos != -1 and pos < 10:
                        first_match_idx = k
                        break

            if first_match_idx == -1:
                return 0

            # 連続マッチをチェックしてスコアを計算（通常の単語と同様の処理）
            first_word = tg_intervals[first_match_idx][0]
            first_word_normalized = normalize_text(first_word).lower()
            score = len(first_word_normalized)
            text_pos = text_reading.find(first_word_normalized)
            if text_pos == -1:
                return 0
            text_pos += len(first_word_normalized)

            # 後続の単語もチェック
            for j in range(first_match_idx + 1, min(first_match_idx + 8, len(tg_intervals))):
                next_word = tg_intervals[j][0]
                if not next_word or next_word == "<unk>":
                    continue
                next_word_normalized = normalize_text(next_word).lower()
                if not next_word_normalized:
                    continue
                remaining = text_reading[text_pos:text_pos + 30]
                pos = remaining.find(next_word_normalized)
                if pos != -1 and pos < 8:
                    score += len(next_word_normalized)
                    text_pos += pos + len(next_word_normalized)
                else:
                    break

            distance_penalty = max(0.1, 1.0 - (distance_from_current / 1000))
            return int(score * distance_penalty)

        if not tg_word:
            return 0
        tg_word_normalized = normalize_text(tg_word).lower()
        if not tg_word_normalized or not text_reading.startswith(tg_word_normalized):
            return 0

        score = len(tg_word_normalized)
        text_pos = len(tg_word_normalized)

        # 後続の単語もチェック（より多くの単語をチェックして精度向上）
        for j in range(start_idx + 1, min(start_idx + 8, len(tg_intervals))):
            next_word = tg_intervals[j][0]
            if not next_word or next_word == "<unk>":
                continue
            next_word_normalized = normalize_text(next_word).lower()
            if not next_word_normalized:
                continue
            remaining = text_reading[text_pos:text_pos + 30]
            pos = remaining.find(next_word_normalized)
            if pos != -1 and pos < 8:
                score += len(next_word_normalized)
                text_pos += pos + len(next_word_normalized)
            else:
                break

        # 距離ペナルティ：現在位置から遠いほどスコアを減らす
        # ただし、ペナルティは緩やかに（1000インターバルで0になる）
        # taimon2のような遠いジャンプを防ぎつつ、通常の処理に影響を与えない
        distance_penalty = max(0.1, 1.0 - (distance_from_current / 1000))
        return int(score * distance_penalty)

    best_match_idx = tg_index
    best_match_score = 0

    # 現在位置の開始時刻を取得（時間整合性チェック用）
    current_start_time = tg_intervals[tg_index][1] if tg_index < len(tg_intervals) else 0.0

    # 1. 後方検索（tg_indexが進みすぎている場合に対応）
    # 注意: 後方検索で見つかった位置の終了時刻が現在位置の開始時刻より前の場合のみ採用
    # これにより、時間の逆行を防ぐ
    #
    # 問題の背景（2026-01-28）:
    # 段落の先頭が<unk>（例: 「２」「３」などMFAが認識できない文字）の場合、
    # _resync_tg_indexは最初の認識可能な単語を探す。
    # しかし、その単語が前の段落にも存在する場合（例: 「国は」が複数段落に出現）、
    # 後方検索が前の段落の位置にジャンプしてしまい、SMILのタイミングが逆行する問題が発生。
    # 例: kenpou.txtの54-55行目、119-122行目で発生。
    # 時間整合性チェックを追加することで、この問題を防ぐ。
    #
    # 注意（2026-01-31）:
    # 段落先頭の数字（２、３、４など）がMFAで<unk>になる問題は、
    # コンテンツ側で [４](+よん) のように読み替え記法を使用するか、
    # TTS辞書に登録することで対応するのが望ましい。
    backward_start = max(0, tg_index - max_backward_search)
    for i in range(backward_start, tg_index):
        # 時間整合性チェック: 候補位置の終了時刻が現在位置の開始時刻より前であること
        candidate_end_time = tg_intervals[i][2]
        if candidate_end_time > current_start_time:
            # 時間が逆行するため、この候補はスキップ
            continue

        distance = tg_index - i
        score = _score_match(i, distance)
        if score > best_match_score:
            best_match_score = score
            best_match_idx = i

    # 2. 前方検索（tg_indexが遅れている場合に対応）- 範囲を制限
    forward_end = min(tg_index + max_forward_search, len(tg_intervals))
    for i in range(tg_index, forward_end):
        distance = i - tg_index
        score = _score_match(i, distance)
        if score > best_match_score:
            best_match_score = score
            best_match_idx = i
            # 十分に高いスコアが見つかったら早期終了
            if score >= 15:
                break

    return best_match_idx


def _find_next_match_position(
    remaining: str,
    reading_pos: int,
    tg_intervals: list[tuple[str, float, float]],
    tg_index: int,
    lookahead: int = 10
) -> int:
    """
    先読みして次のマッチ位置を探す。

    現在のTextGrid単語がマッチしない場合、将来の単語を先読みして
    次にマッチする位置を探します。

    Parameters
    ----------
    remaining : str
        現在位置以降の読みテキスト。
    reading_pos : int
        現在の読みテキスト位置。
    tg_intervals : list[tuple[str, float, float]]
        TextGridインターバルのリスト。
    tg_index : int
        現在のTextGridインデックス。
    lookahead : int, optional
        先読みする単語数。デフォルトは10。

    Returns
    -------
    int
        次のマッチ位置。見つからない場合は-1。
    """
    for future_idx in range(tg_index + 1, min(tg_index + lookahead, len(tg_intervals))):
        future_word = normalize_text(tg_intervals[future_idx][0]).lower()
        future_pos = remaining.find(future_word)
        if future_pos != -1:
            return reading_pos + future_pos
    return -1


def _extract_span_reading(span_content: str) -> str:
    """
    span要素の内容から読みテキストを抽出する。

    ruby要素の場合はrt部分（読み仮名）を、
    yomikae要素（data-yomi属性付きspan）の場合はdata-yomi値を、
    それ以外はテキスト内容を返す。
    """
    import re
    # ruby要素: <ruby><rb>親字</rb><rt>読み</rt></ruby> → 読み
    result = re.sub(r'<ruby><rb>.*?</rb><rt>(.*?)</rt></ruby>', r'\1', span_content)
    # yomikae要素（seg内）: <span data-yomi="読み">表示</span> → 読み
    result = re.sub(r'<span data-yomi="([^"]*)">.*?</span>', r'\1', result)
    # その他すべてのタグを除去
    result = re.sub(r'<[^>]+>', '', result)
    return result.lower()


@dataclass
class _SpanMatch:
    """data-index付きspan要素の抽出結果。"""
    data_index: str
    data_yomi: str | None
    span_content: str
    open_tag: str  # 開始タグ部分（置換用）


def _extract_data_index_spans(paragraph: str) -> list[_SpanMatch]:
    """data-index属性付きspan要素を抽出する（ネストされたspanに対応）。"""
    results: list[_SpanMatch] = []
    open_pattern = re.compile(
        r'<span data-index="(\d+)"(?: data-yomi="([^"]*)")?>'
    )
    pos = 0
    while pos < len(paragraph):
        m = open_pattern.search(paragraph, pos)
        if not m:
            break
        data_index = m.group(1)
        data_yomi = m.group(2)
        open_tag = m.group(0)
        content_start = m.end()
        # 開始タグ以降でspan深さをカウントして対応する</span>を見つける
        depth = 1
        i = content_start
        while i < len(paragraph) and depth > 0:
            if paragraph[i:i+5] == '<span':
                depth += 1
                i += 5
            elif paragraph[i:i+7] == '</span>':
                depth -= 1
                if depth == 0:
                    break
                i += 7
            else:
                i += 1
        span_content = paragraph[content_start:i]
        results.append(_SpanMatch(data_index, data_yomi, span_content, open_tag))
        pos = i + 7  # skip past </span>
    return results


def _normalize_tg_word(word: str) -> str:
    """TextGrid単語を正規化する。"""
    return word.lower().strip()


def process_xml_paragraph(
    paragraph: str,
    tg_intervals: list[tuple[str, float, float]],
    tg_index: int,
    span_id: int,
    element_id_prefix: str,
    xhtml_path: str,
    audio_filename: str,
) -> tuple[str, list[str], int, int]:
    """
    XSLTで生成されたspan付きXHTMLをTextGridとマッチングする。

    MFAは日本語テキストを独自の辞書で分かち書きするため、
    1つのspanに複数のTextGridインターバルが対応する場合があります。
    この関数は、spanの読みテキストとTextGridの単語をマッチングし、
    複数インターバルを1つのspanにグループ化します。

    Parameters
    ----------
    paragraph : str
        XSLTで生成されたXHTML（span data-index付き）。
    tg_intervals : list[tuple[str, float, float]]
        TextGridインターバルのリスト。
    tg_index : int
        処理を開始するtg_intervalsのインデックス。
    span_id : int
        span要素のID番号の開始値。
    element_id_prefix : str
        要素IDのプレフィックス。
    xhtml_path : str
        XHTMLファイルの相対パス。
    audio_filename : str
        音声ファイルの相対パス。

    Returns
    -------
    tuple[str, list[str], int, int]
        - xhtml_paragraph : str
            ID付きのXHTML段落要素（<p>タグ）。
        - smil_pars : list[str]
            生成されたSMIL par要素のリスト。
        - next_span_id : int
            次に使用すべきspan ID番号。
        - next_tg_index : int
            次に処理すべきtg_intervalsのインデックス。
    """
    import re

    smil_pars: list[str] = []
    result = paragraph

    # TGワードが複数spanにまたがる場合のキャリーオーバー
    tg_carry = ""           # 未消費部分のテキスト
    tg_carry_begin = 0.0    # キャリー部分の開始時刻
    tg_carry_end = 0.0      # キャリー部分の終了時刻

    # span要素とその内容を抽出（ネストされたspanに対応）
    matches = _extract_data_index_spans(paragraph)

    for match in matches:
        data_index = match.data_index
        data_yomi = match.data_yomi  # yomikae の場合のみ存在
        span_content = match.span_content

        # spanの読みテキストを取得（data-yomi があればそちらを優先）
        if data_yomi:
            span_reading = data_yomi.lower()
        else:
            span_reading = _extract_span_reading(span_content)
        # マッチング用にスペース・句読点を除去した版
        span_reading_clean = _normalize_for_matching(span_reading)

        # span IDを生成
        el_id = f"{element_id_prefix}{span_id:04d}"

        # data-index="N" (+ optional data-yomi) を id="el_id" に置換
        new_span = f'<span id="{el_id}">'
        result = result.replace(match.open_tag, new_span, 1)

        # TextGridインターバルを消費してspanの読みテキストをカバー
        clip_begin: float | None = None
        clip_end: float = 0.0
        matched_text = ""

        # 前のspanで部分消費されたTGワードのキャリーオーバー処理
        if tg_carry and span_reading_clean:
            remaining_clean = span_reading_clean
            if remaining_clean.startswith(tg_carry):
                # キャリーがこのspan内で完全に消費される
                clip_begin = tg_carry_begin
                clip_end = tg_carry_end
                matched_text += tg_carry
                tg_carry = ""
                tg_index += 1
            elif tg_carry.startswith(remaining_clean):
                # キャリーがこのspan全体より長い → spanは完全カバー
                consumed_len = len(remaining_clean)
                total_len = len(tg_carry)
                duration = tg_carry_end - tg_carry_begin
                split_time = tg_carry_begin + duration * consumed_len / total_len
                clip_begin = tg_carry_begin
                clip_end = split_time
                tg_carry = tg_carry[consumed_len:]
                tg_carry_begin = split_time
                matched_text = span_reading_clean
            else:
                # キャリーがマッチしない → 破棄して次へ
                tg_carry = ""
                tg_index += 1

        while matched_text != span_reading_clean and tg_index < len(tg_intervals):
            tg_word, tg_begin, tg_end = tg_intervals[tg_index]
            tg_word_norm = normalize_text(tg_word).lower()

            # 空のインターバルはスキップ
            if not tg_word_norm:
                tg_index += 1
                continue

            # <unk> はスキップしてタイミング蓄積 + 対応テキストを matched_text に加算
            if tg_word == "<unk>":
                if clip_begin is None:
                    clip_begin = tg_begin
                clip_end = tg_end
                tg_index += 1

                # <unk> が担当するテキスト部分を特定するため、次の認識済み単語を先読み
                remaining_clean = span_reading_clean[len(matched_text):]
                if remaining_clean:
                    # 連続する <unk> をスキップして次の認識済み単語を探す
                    peek_idx = tg_index
                    next_word_norm = None
                    next_next_word_norm = None
                    while peek_idx < len(tg_intervals):
                        peek_word = tg_intervals[peek_idx][0]
                        peek_norm = normalize_text(peek_word).lower()
                        if peek_word == "<unk>" or not peek_norm:
                            peek_idx += 1
                            continue
                        next_word_norm = peek_norm
                        # さらに次の認識済み単語も取得（検証用）
                        for j in range(peek_idx + 1, len(tg_intervals)):
                            jw = tg_intervals[j][0]
                            jn = normalize_text(jw).lower()
                            if jw != "<unk>" and jn:
                                next_next_word_norm = jn
                                break
                        break

                    if next_word_norm:
                        # next_word_norm の各出現位置を検査し、
                        # next_next_word_norm も連続マッチする位置を正しい分割点とする
                        search_start = 0
                        best_pos = -1
                        while True:
                            pos = remaining_clean.find(next_word_norm, search_start)
                            if pos < 0:
                                break
                            if pos == 0:
                                # <unk> のテキストが空 → 分割不要
                                break
                            if not next_next_word_norm:
                                # 検証用の次の単語がない場合は最初のマッチを採用
                                best_pos = pos
                                break
                            after = remaining_clean[pos + len(next_word_norm):]
                            if not after or after.startswith(next_next_word_norm):
                                # next_wordがspan末尾に到達、または次の次の単語も連続マッチ
                                best_pos = pos
                                break
                            search_start = pos + 1
                        if best_pos > 0:
                            matched_text += remaining_clean[:best_pos]
                continue

            # スペース・句読点を除去した残りテキストでマッチング
            remaining_clean = span_reading_clean[len(matched_text):]
            if remaining_clean.startswith(tg_word_norm):
                # マッチ: このインターバルを消費
                if clip_begin is None:
                    clip_begin = tg_begin
                clip_end = tg_end
                matched_text += tg_word_norm
                tg_index += 1

                # span全体をカバーしたら終了
                if matched_text == span_reading_clean:
                    break
            elif tg_word_norm.startswith(remaining_clean) and remaining_clean:
                # 部分マッチ: TGワードがspan読みより長い（複数spanにまたがる）
                consumed_len = len(remaining_clean)
                total_len = len(tg_word_norm)
                duration = tg_end - tg_begin
                split_time = tg_begin + duration * consumed_len / total_len
                if clip_begin is None:
                    clip_begin = tg_begin
                clip_end = split_time
                # 未消費部分を次のspanにキャリーオーバー
                tg_carry = tg_word_norm[consumed_len:]
                tg_carry_begin = split_time
                tg_carry_end = tg_end
                matched_text = span_reading_clean
                # tg_indexは進めない（キャリー消費後に進める）
                break
            else:
                # マッチしない場合、現在のspanの処理を終了
                break

        # SMIL par要素を生成（タイミングが取得できた場合のみ）
        if clip_begin is not None:
            smil_pars.append(_generate_smil_par(
                el_id, xhtml_path, audio_filename, clip_begin, clip_end
            ))

        span_id += 1

    xhtml_paragraph = f'        <p>{result}</p>' if result.strip() else ""

    return xhtml_paragraph, smil_pars, span_id, tg_index


def _is_image_only_paragraph(paragraph: str) -> bool:
    """
    段落が画像のみで構成されているかどうかを判定する。

    Parameters
    ----------
    paragraph : str
        判定対象の段落テキスト。

    Returns
    -------
    bool
        画像のみの段落の場合True。
    """
    # 画像記法を除去した後にテキストが残らなければ画像のみ
    text_without_images = IMAGE_PATTERN.sub('', paragraph)
    return text_without_images.strip() == ''


def _generate_image_only_paragraph(paragraph: str) -> str:
    """
    画像のみの段落をXHTMLに変換する。

    Parameters
    ----------
    paragraph : str
        画像記法のみを含む段落テキスト。

    Returns
    -------
    str
        XHTML段落要素（<p>タグ）。
    """
    from html import escape
    from pathlib import Path

    images = IMAGE_PATTERN.findall(paragraph)
    img_tags = []
    for alt, path in images:
        filename = Path(path).name
        img_tags.append(f'<img src="../images/{escape(filename)}" alt="{escape(alt)}"/>')
    return f'        <p>{"".join(img_tags)}</p>'


def process_paragraph(
    paragraph: str,
    tg_intervals: list[tuple[str, float, float]],
    tg_index: int,
    span_id: int,
    element_id_prefix: str,
    xhtml_path: str,
    audio_filename: str,
    highlight_mode: str = "word",
    is_xml: bool = False
) -> tuple[str, list[str], int, int]:
    """
    段落をTextGridにマッチングしてXHTML段落要素とSMILを生成する。

    Parameters
    ----------
    paragraph : str
        処理対象の段落テキスト。XMLの場合はspan data-index付きXHTML。
    tg_intervals : list[tuple[str, float, float]]
        TextGridインターバルのリスト。
    tg_index : int
        処理を開始するtg_intervalsのインデックス。
    span_id : int
        span要素のID番号の開始値。
    element_id_prefix : str
        要素IDのプレフィックス。
    xhtml_path : str
        XHTMLファイルの相対パス。
    audio_filename : str
        音声ファイルの相対パス。
    highlight_mode : str
        ハイライトモード。"word"（単語単位）または"punctuation"（句読点単位）。
        XMLの場合は無視されます（XSLTで事前にspan生成済み）。
    is_xml : bool
        入力がXMLファイルからの場合True。

    Returns
    -------
    tuple[str, list[str], int, int]
        - xhtml_paragraph : str
            生成されたXHTML段落要素（<p>タグ）。空の場合は空文字列。
        - smil_pars : list[str]
            生成されたSMIL par要素のリスト。
        - next_span_id : int
            次に使用すべきspan ID番号。
        - next_tg_index : int
            次に処理すべきtg_intervalsのインデックス。
    """
    # XMLの場合: XSLTで生成されたspan付きXHTMLを処理
    if is_xml:
        # XML でも resync を実行（タイトル分のずれを補正）
        tg_index = _resync_tg_index(paragraph, tg_intervals, tg_index, is_xml=True)
        return process_xml_paragraph(
            paragraph, tg_intervals, tg_index, span_id,
            element_id_prefix, xhtml_path, audio_filename
        )

    # 画像のみの段落: imgタグのみを生成、SMILは空
    if _is_image_only_paragraph(paragraph):
        xhtml_paragraph = _generate_image_only_paragraph(paragraph)
        return xhtml_paragraph, [], span_id, tg_index

    # 段落の最初の単語を探して tg_index を再同期
    # これにより、前の段落でマッチングが失敗しても次の段落で回復できる
    tg_index = _resync_tg_index(paragraph, tg_intervals, tg_index, is_xml=is_xml)

    # テキストファイルの場合: 従来のマッチング処理
    if highlight_mode == "punctuation":
        spans, smil_pars, span_id, tg_index = match_text_to_textgrid_punctuation(
            paragraph, tg_intervals, tg_index, span_id,
            element_id_prefix, xhtml_path, audio_filename,
            is_xml=False
        )
    else:
        spans, smil_pars, span_id, tg_index = match_text_to_textgrid(
            paragraph, tg_intervals, tg_index, span_id,
            element_id_prefix, xhtml_path, audio_filename,
            is_xml=False
        )

    if spans:
        xhtml_paragraph = f'        <p>{"".join(spans)}</p>'
    else:
        xhtml_paragraph = ""

    return xhtml_paragraph, smil_pars, span_id, tg_index


# =============================================================================
# Strategy Pattern 実装
# =============================================================================

class WordMatchingStrategy(MatchingStrategy):
    """単語単位のマッチング戦略。

    TextGridの各単語に対して1つのspanを生成する。
    """

    def match(self, state: MatchingState) -> None:
        """単語単位でマッチング処理を実行する。"""
        spans, smil_pars, span_id, tg_index = match_text_to_textgrid(
            state.text,
            state.tg_intervals,
            state.tg_index,
            state.span_id,
            self.context.element_id_prefix,
            self.context.xhtml_path,
            self.context.audio_filename,
            is_xml=state.is_xml
        )
        state.spans = spans
        state.smil_pars = smil_pars
        state.span_id = span_id
        state.tg_index = tg_index


class PunctuationMatchingStrategy(MatchingStrategy):
    """句読点単位のマッチング戦略。

    句読点（。、，）までの複数単語を1つのspanにグループ化する。
    """

    def match(self, state: MatchingState) -> None:
        """句読点単位でマッチング処理を実行する。"""
        spans, smil_pars, span_id, tg_index = match_text_to_textgrid_punctuation(
            state.text,
            state.tg_intervals,
            state.tg_index,
            state.span_id,
            self.context.element_id_prefix,
            self.context.xhtml_path,
            self.context.audio_filename,
            is_xml=state.is_xml
        )
        state.spans = spans
        state.smil_pars = smil_pars
        state.span_id = span_id
        state.tg_index = tg_index


class TextGridMatcher:
    """TextGridマッチング処理のファサードクラス。

    Strategy Patternを使用して、単語単位または句読点単位の
    マッチング処理を統一的に扱う。

    Examples
    --------
    >>> context = MatchContext("w", "../text/content.xhtml", "../audio/audio.mp3")
    >>> matcher = TextGridMatcher(context, mode="word")
    >>> state = MatchingState(text, text_reading, tg_intervals)
    >>> matcher.match(state)
    >>> print(state.spans, state.smil_pars)
    """

    def __init__(self, context: MatchContext, mode: str = "word"):
        """
        Parameters
        ----------
        context : MatchContext
            マッチング処理のコンテキスト情報。
        mode : str
            マッチングモード。"word"（単語単位）または"punctuation"（句読点単位）。
        """
        self.context = context
        self.mode = mode
        self._strategy = self._create_strategy(mode)

    def _create_strategy(self, mode: str) -> MatchingStrategy:
        """モードに応じた戦略オブジェクトを作成する。"""
        if mode == "punctuation":
            return PunctuationMatchingStrategy(self.context)
        return WordMatchingStrategy(self.context)

    def match(self, state: MatchingState) -> None:
        """マッチング処理を実行する。"""
        self._strategy.match(state)

    def process_text(
        self,
        text: str,
        tg_intervals: list[tuple[str, float, float]],
        tg_index: int = 0,
        span_id: int = 0,
        is_xml: bool = False
    ) -> tuple[list[str], list[str], int, int]:
        """テキストをマッチング処理する便利メソッド。

        Parameters
        ----------
        text : str
            処理対象のテキスト。
        tg_intervals : list[tuple[str, float, float]]
            TextGridインターバルのリスト。
        tg_index : int
            開始インデックス。
        span_id : int
            開始span ID。
        is_xml : bool
            XML入力かどうか。

        Returns
        -------
        tuple[list[str], list[str], int, int]
            (spans, smil_pars, next_span_id, next_tg_index)
        """
        if is_xml:
            text_reading = normalize_xhtml_text(text).lower()
        else:
            text_reading = normalize_text(text).lower()

        state = MatchingState(
            text=text,
            text_reading=text_reading,
            tg_intervals=tg_intervals,
            reading_pos=0,
            tg_index=tg_index,
            span_id=span_id,
            is_xml=is_xml
        )

        self.match(state)

        return state.spans, state.smil_pars, state.span_id, state.tg_index
