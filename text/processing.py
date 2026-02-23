"""
テキスト正規化・書式処理モジュール。

ルビ記法、書式記法の処理、位置マッピング等の
テキスト処理機能を提供します。
"""
from html import escape

from pathlib import Path

from text.common import (
    RUBY_PATTERN,
    READING_SUB_PATTERN,
    SUBSCRIPT_PATTERN,
    SUPERSCRIPT_PATTERN,
    STRONG_PATTERN,
    UNDERLINE_PATTERN,
    FRAME_PATTERN,
    IMAGE_PATTERN,
    FRAME_STYLE,
    ruby_to_xhtml,
    strip_formatting,
    TextNormalizer,
)


def _get_reading_len(text: str) -> int:
    """テキストの読み長さを計算する（READING_MAP展開を考慮）。"""
    return len(TextNormalizer.to_reading(strip_formatting(text)))


def normalize_text(text: str) -> str:
    """
    テキストを正規化する。

    すべての書式記法を除去し、括弧や数字の全角/半角を統一します。
    TextGridとのマッチング用に使用します。

    Parameters
    ----------
    text : str
        正規化する元テキスト。各種書式記法を含む場合があります。
        - ルビ記法: [漢字](-ふりがな)
        - 下付き: ~text~
        - 上付き: ^text^
        - 太字: **text**
        - Underline: [text]{.underline}

    Returns
    -------
    str
        正規化されたテキスト。
        - すべての書式記法が除去されます（ルビは読みに変換）
        - 丸数字・ローマ数字は読み仮名に変換されます
        - 全角括弧は半角に変換されます
        - 全角数字は半角に変換されます

    Examples
    --------
    >>> normalize_text("[首都](-しゅと)直下地震")
    'しゅと直下地震'
    >>> normalize_text("H~2~O")
    'H2O'
    >>> normalize_text("2^10^")
    '210'
    >>> normalize_text("**重要**")
    '重要'
    >>> normalize_text("[text]{.underline}")
    'text'
    >>> normalize_text("２０２５年（令和７年）")
    '2025年(令和7年)'
    >>> normalize_text("①②③")
    'いちにさん'
    """
    # すべての書式記法を除去（ルビは読みに変換）
    result = strip_formatting(text)
    # 特殊文字を読み仮名に変換（MFAとの整合性のため）
    result = TextNormalizer.to_reading(result)
    # TextNormalizerで一括正規化（括弧を含む）
    result = TextNormalizer.normalize_all(result, include_brackets=True)
    return result


def strip_ruby(text: str) -> str:
    """
    ルビ記法から漢字部分のみを抽出する（ふりがなを削除）。

    nav.xhtmlのタイトル表示など、ルビなしのプレーンテキストが
    必要な場合に使用します。

    Parameters
    ----------
    text : str
        ルビ記法を含むテキスト。

    Returns
    -------
    str
        漢字部分のみを残したテキスト。

    Examples
    --------
    >>> strip_ruby("[被害](-ひがい)[想定](-そうてい)")
    '被害想定'
    >>> strip_ruby("新たな[被害](-ひがい)")
    '新たな被害'
    """
    return RUBY_PATTERN.sub(r'\1', text)


def escape_with_ruby(text: str) -> str:
    """
    ルビ記法を保持しつつHTMLエスケープを行う。

    ルビ記法以外の特殊文字（<, >, &等）をHTMLエスケープし、
    ルビ記法はXHTMLのrubyタグに変換します。

    Parameters
    ----------
    text : str
        処理対象のテキスト。ルビ記法 ``[漢字](-ふりがな)`` を含む場合があります。

    Returns
    -------
    str
        HTMLエスケープされ、ルビがXHTMLタグに変換されたテキスト。

    Examples
    --------
    >>> escape_with_ruby("[首都](-しゅと)直下")
    '<ruby>首都<rt>しゅと</rt></ruby>直下'
    >>> escape_with_ruby("A < B & [群衆](-ぐんしゅう)")
    'A &lt; B &amp; <ruby>群衆<rt>ぐんしゅう</rt></ruby>'

    Notes
    -----
    処理手順:
    1. ルビ記法を一時プレースホルダーに置換
    2. プレースホルダー以外をHTMLエスケープ
    3. プレースホルダーをrubyタグに復元
    """
    # 1. ルビ記法を一時プレースホルダーに置換
    placeholders: list[str] = []

    def save_ruby(m):
        placeholders.append(m.group(0))
        return f'\x00{len(placeholders) - 1}\x00'

    temp = RUBY_PATTERN.sub(save_ruby, text)

    # 2. ルビ以外をHTMLエスケープ
    temp = escape(temp)

    # 3. プレースホルダーをrubyタグに戻す
    for i, ruby_text in enumerate(placeholders):
        temp = temp.replace(f'\x00{i}\x00', ruby_to_xhtml(ruby_text))

    return temp


class FormattingHandler:
    """書式記法をXHTMLタグに変換するハンドラークラス。

    プレースホルダー方式で書式記法を保持しつつHTMLエスケープを行う。

    対応する書式記法:
    - ルビ: [漢字](-ふりがな) → <ruby>漢字<rt>ふりがな</rt></ruby>
    - 読み替え: [表示](+読み) → 表示（内部書式適用、ルビなし）
    - 下付き: ~text~ → <sub>text</sub>
    - 上付き: ^text^ → <sup>text</sup>
    - 太字: **text** → <strong>text</strong>
    - Underline: [text]{.underline} → <u>text</u>
    - Frame: [text]{.frame} → <span style="...">text</span>
    - 画像: ![代替テキスト](パス) → <img src="../images/ファイル名" alt="代替テキスト"/>
    """

    def __init__(self):
        self.placeholders: list[tuple[str, str, str]] = []  # (tag, inner_content, original)

    def _save_placeholder(self, tag: str, inner: str, original: str) -> str:
        """プレースホルダーを保存して置換文字列を返す。"""
        idx = len(self.placeholders)
        self.placeholders.append((tag, inner, original))
        return f'\x00{idx}\x00'

    def _save_image(self, m) -> str:
        return self._save_placeholder('img', m.group(1), m.group(2))

    def _save_underline(self, m) -> str:
        return self._save_placeholder('u', m.group(1), m.group(0))

    def _save_frame(self, m) -> str:
        return self._save_placeholder('frame', m.group(1), m.group(0))

    def _save_strong(self, m) -> str:
        return self._save_placeholder('strong', m.group(1), m.group(0))

    def _save_reading_sub(self, m) -> str:
        return self._save_placeholder('reading_sub', m.group(1), m.group(0))

    def _save_ruby(self, m) -> str:
        return self._save_placeholder('ruby', m.group(0), m.group(0))

    def _save_subscript(self, m) -> str:
        return self._save_placeholder('sub', m.group(1), m.group(0))

    def _save_superscript(self, m) -> str:
        return self._save_placeholder('sup', m.group(1), m.group(0))

    def _replace_with_placeholders(self, text: str) -> str:
        """すべての書式記法をプレースホルダーに置換する。"""
        temp = text
        # 処理順序: 外側から内側へ
        temp = IMAGE_PATTERN.sub(self._save_image, temp)
        temp = UNDERLINE_PATTERN.sub(self._save_underline, temp)
        temp = FRAME_PATTERN.sub(self._save_frame, temp)
        temp = STRONG_PATTERN.sub(self._save_strong, temp)
        temp = READING_SUB_PATTERN.sub(self._save_reading_sub, temp)
        temp = RUBY_PATTERN.sub(self._save_ruby, temp)
        temp = SUBSCRIPT_PATTERN.sub(self._save_subscript, temp)
        temp = SUPERSCRIPT_PATTERN.sub(self._save_superscript, temp)
        return temp

    def _restore_placeholder(self, tag: str, inner: str, original: str) -> str:
        """プレースホルダーをXHTMLタグに復元する。"""
        if tag == 'img':
            filename = Path(original).name
            return f'<img src="../images/{escape(filename)}" alt="{escape(inner)}"/>'

        if tag == 'ruby':
            match = RUBY_PATTERN.match(original)
            if match:
                kanji = escape_with_formatting(match.group(1))
                reading = escape(match.group(2))
                return f'<ruby>{kanji}<rt>{reading}</rt></ruby>'
            return ruby_to_xhtml(original)

        if tag == 'reading_sub':
            return escape_with_formatting(inner)

        if tag == 'frame':
            inner_processed = escape_with_formatting(inner)
            return f'<span style="{FRAME_STYLE}">{inner_processed}</span>'

        # 標準タグ (u, strong, sub, sup)
        inner_processed = escape_with_formatting(inner)
        return f'<{tag}>{inner_processed}</{tag}>'

    def _restore_all_placeholders(self, text: str) -> str:
        """すべてのプレースホルダーをXHTMLタグに復元する。"""
        result = text
        # 逆順に復元（内側から外側へ）
        for i in range(len(self.placeholders) - 1, -1, -1):
            tag, inner, original = self.placeholders[i]
            xhtml = self._restore_placeholder(tag, inner, original)
            result = result.replace(f'\x00{i}\x00', xhtml)
        return result

    def convert(self, text: str) -> str:
        """書式記法をXHTMLタグに変換する。"""
        self.placeholders.clear()
        temp = self._replace_with_placeholders(text)
        temp = escape(temp)
        temp = self._restore_all_placeholders(temp)
        # 壊れた**パターンを除去
        temp = temp.replace('**', '')
        return temp


def escape_with_formatting(text: str) -> str:
    """
    すべての書式記法を保持しつつHTMLエスケープを行う。

    対応する書式記法:
    - ルビ: [漢字](-ふりがな) → <ruby>漢字<rt>ふりがな</rt></ruby>
    - 読み替え: [表示](+読み) → 表示（内部書式適用、ルビなし）
    - 下付き: ~text~ → <sub>text</sub>
    - 上付き: ^text^ → <sup>text</sup>
    - 太字: **text** → <strong>text</strong>
    - Underline: [text]{.underline} → <u>text</u>
    - 画像: ![代替テキスト](パス) → <img src="../images/ファイル名" alt="代替テキスト"/>

    Parameters
    ----------
    text : str
        処理対象のテキスト。各種書式記法を含む場合があります。

    Returns
    -------
    str
        HTMLエスケープされ、書式がXHTMLタグに変換されたテキスト。

    Examples
    --------
    >>> escape_with_formatting("H~2~O")
    'H<sub>2</sub>O'
    >>> escape_with_formatting("**重要**")
    '<strong>重要</strong>'
    """
    return FormattingHandler().convert(text)


def reading_pos_to_original(text: str, reading_pos: int) -> int:
    """
    読みテキストでの位置を元テキストでの位置に変換する。

    書式記法を含む元テキストと、書式を除去/変換した読みテキストでは
    文字位置が異なります。この関数は読みテキストでの位置から
    元テキストでの対応位置を計算します。

    Parameters
    ----------
    text : str
        書式記法を含む元テキスト。
    reading_pos : int
        読みテキスト（書式除去後）での位置。

    Returns
    -------
    int
        元テキストでの対応位置。

    Examples
    --------
    >>> # 元テキスト: "[首都](-しゅと)直下" (14文字)
    >>> # 読みテキスト: "しゅと直下" (5文字)
    >>> reading_pos_to_original("[首都](-しゅと)直下", 3)
    14  # "しゅと"の後 → ルビ記法全体の後

    Notes
    -----
    対応する書式記法:
    - ルビ: [漢字](-ふりがな) → ふりがな
    - Underline: [text]{.underline} → text
    - Strong: **text** → text
    - Subscript: ~text~ → text
    - Superscript: ^text^ → text
    """
    original_pos = 0
    current_reading_pos = 0

    while current_reading_pos <= reading_pos and original_pos < len(text):
        # current_reading_pos == reading_pos の場合、パターン内部への再帰が必要かチェック
        at_target = (current_reading_pos == reading_pos)

        remaining = text[original_pos:]

        # Underline記法のチェック: [text]{.underline}
        underline_match = UNDERLINE_PATTERN.match(remaining)
        if underline_match:
            inner_text = underline_match.group(1)
            inner_reading_len = _get_reading_len(inner_text)
            if current_reading_pos + inner_reading_len <= reading_pos and not at_target:
                current_reading_pos += inner_reading_len
                original_pos += len(underline_match.group(0))
                continue
            else:
                # 内部の途中またはパターン開始位置でreading_posに達した場合、内部を再帰的に処理
                inner_offset = reading_pos - current_reading_pos
                inner_pos = reading_pos_to_original(inner_text, inner_offset)
                # [の後 + 内部位置
                return original_pos + 1 + inner_pos

        # Frame記法のチェック: [text]{.frame}
        frame_match = FRAME_PATTERN.match(remaining)
        if frame_match:
            inner_text = frame_match.group(1)
            inner_reading_len = _get_reading_len(inner_text)
            if current_reading_pos + inner_reading_len <= reading_pos and not at_target:
                current_reading_pos += inner_reading_len
                original_pos += len(frame_match.group(0))
                continue
            else:
                # 内部の途中またはパターン開始位置でreading_posに達した場合、内部を再帰的に処理
                inner_offset = reading_pos - current_reading_pos
                inner_pos = reading_pos_to_original(inner_text, inner_offset)
                # [の後 + 内部位置
                return original_pos + 1 + inner_pos

        # Strong記法のチェック: **text**
        strong_match = STRONG_PATTERN.match(remaining)
        if strong_match:
            inner_text = strong_match.group(1)
            inner_reading_len = _get_reading_len(inner_text)
            if current_reading_pos + inner_reading_len <= reading_pos and not at_target:
                current_reading_pos += inner_reading_len
                original_pos += len(strong_match.group(0))
                continue
            else:
                # 内部の途中またはパターン開始位置でreading_posに達した場合、内部を再帰的に処理
                inner_offset = reading_pos - current_reading_pos
                inner_pos = reading_pos_to_original(inner_text, inner_offset)
                # **の後 + 内部位置
                return original_pos + 2 + inner_pos

        # 読み替え記法のチェック: [表示](+読み)
        reading_sub_match = READING_SUB_PATTERN.match(remaining)
        if reading_sub_match:
            reading_len = len(reading_sub_match.group(2))  # 読み上げ部分の長さ
            if current_reading_pos + reading_len <= reading_pos and not at_target:
                current_reading_pos += reading_len
                original_pos += len(reading_sub_match.group(0))
                continue
            else:
                # 読み替えの途中でreading_posに達した場合、全体を含める
                break

        # ルビ記法のチェック: [漢字](-ふりがな)
        ruby_match = RUBY_PATTERN.match(remaining)
        if ruby_match:
            reading_len = len(ruby_match.group(2))  # ふりがな部分の長さ
            if current_reading_pos + reading_len <= reading_pos and not at_target:
                current_reading_pos += reading_len
                original_pos += len(ruby_match.group(0))
                continue
            else:
                # ルビの途中でreading_posに達した場合、ルビ全体を含める
                break

        # Subscript記法のチェック: ~text~
        subscript_match = SUBSCRIPT_PATTERN.match(remaining)
        if subscript_match:
            inner_text = subscript_match.group(1)
            inner_reading_len = _get_reading_len(inner_text)  # READING_MAP展開を考慮
            if current_reading_pos + inner_reading_len <= reading_pos and not at_target:
                current_reading_pos += inner_reading_len
                original_pos += len(subscript_match.group(0))
                continue
            else:
                # 内部の途中またはパターン開始位置でreading_posに達した場合、内部を再帰的に処理
                inner_offset = reading_pos - current_reading_pos
                inner_pos = reading_pos_to_original(inner_text, inner_offset)
                # ~の後 + 内部位置
                return original_pos + 1 + inner_pos

        # Superscript記法のチェック: ^text^
        superscript_match = SUPERSCRIPT_PATTERN.match(remaining)
        if superscript_match:
            inner_text = superscript_match.group(1)
            inner_reading_len = _get_reading_len(inner_text)  # READING_MAP展開を考慮
            if current_reading_pos + inner_reading_len <= reading_pos and not at_target:
                current_reading_pos += inner_reading_len
                original_pos += len(superscript_match.group(0))
                continue
            else:
                # 内部の途中またはパターン開始位置でreading_posに達した場合、内部を再帰的に処理
                inner_offset = reading_pos - current_reading_pos
                inner_pos = reading_pos_to_original(inner_text, inner_offset)
                # ^の後 + 内部位置
                return original_pos + 1 + inner_pos

        # READING_MAP文字のチェック（丸数字・ローマ数字・丸囲み英字など）
        # これらは1文字が複数文字の読みに展開される
        current_char = text[original_pos] if original_pos < len(text) else ''
        if current_char in TextNormalizer.READING_MAP:
            reading_expansion = TextNormalizer.READING_MAP[current_char]
            expansion_len = len(reading_expansion)
            if current_reading_pos + expansion_len <= reading_pos and not at_target:
                current_reading_pos += expansion_len
                original_pos += 1
                continue
            else:
                # 展開の途中でreading_posに達した場合、元の文字全体を含める
                return original_pos

        # 通常の文字
        if at_target:
            # 目標位置に到達（パターンではない通常文字）
            return original_pos
        current_reading_pos += 1
        original_pos += 1

    return original_pos


def get_original_range(text: str, reading_start: int, reading_len: int) -> tuple[int, int]:
    """
    読みテキストでの範囲を元テキストでの範囲に変換する。

    Parameters
    ----------
    text : str
        ルビ記法を含む元テキスト。
    reading_start : int
        読みテキストでの開始位置。
    reading_len : int
        読みテキストでの長さ。

    Returns
    -------
    tuple[int, int]
        元テキストでの (開始位置, 終了位置) のタプル。
        範囲は [開始位置, 終了位置) の半開区間。

    Examples
    --------
    >>> # 元テキスト: "[首都](-しゅと)直下"
    >>> # 読みテキスト: "しゅと直下"
    >>> get_original_range("[首都](-しゅと)直下", 0, 3)
    (0, 14)  # "しゅと" → "[首都](-しゅと)"

    See Also
    --------
    reading_pos_to_original : 単一位置の変換に使用。
    """
    orig_start = reading_pos_to_original(text, reading_start)
    orig_end = reading_pos_to_original(text, reading_start + reading_len)

    # orig_endが新しいbracket構文([...]{.frame/underline})の直後に入っている場合、
    # 構文の前に戻す（reading_pos_to_originalが内部offset=0で構文内に入るため）
    if orig_end > orig_start and orig_end >= 1 and text[orig_end - 1] == '[':
        remaining_from_bracket = text[orig_end - 1:]
        if UNDERLINE_PATTERN.match(remaining_from_bracket) or FRAME_PATTERN.match(remaining_from_bracket):
            orig_end -= 1

    # orig_end が書式パターン内部に入っている場合、パターン開始位置まで戻す
    # 例: ~ⓓ~[関係...] で orig_end が「関」(12) を指している場合、
    # 「[」(11) の前の「~」(10) の後ろ、つまり11に戻す
    # Underline/Frame パターンの内部に入っている場合
    if orig_end > orig_start:
        # orig_end の位置から逆算して [ を探す
        for back in range(1, min(3, orig_end - orig_start + 1)):
            check_pos = orig_end - back
            if check_pos >= 0 and check_pos < len(text) and text[check_pos] == '[':
                # [ の直前が ~ か ^ なら、それは subscript/superscript の終了
                if check_pos > 0 and text[check_pos - 1] in '~^':
                    orig_end = check_pos
                    break

    # 範囲内に]{.underline}や]{.frame}が含まれているが対応する[がない場合、
    # 書式マーカーを除外する（長い[text]{.underline}構文の途中で発生）
    if orig_end > orig_start:
        range_text = text[orig_start:orig_end]
        for marker in [']{.underline}', ']{.frame}']:
            marker_idx = range_text.find(marker)
            if marker_idx >= 0 and '[' not in range_text[:marker_idx]:
                # 対応する[がない — 書式マーカーを除外してコンテンツのみにする
                orig_end = orig_start + marker_idx
                break

    # 書式記法の境界に拡張
    # 開始位置の前の書式記法を含める

    # orig_startが[...]{.frame/underline}構文の内部にあるかを厳密チェック
    inside_bracket = False
    bracket_pos = None
    if orig_start >= 1:
        # 後方に[を検索（途中に]があれば中断）
        for back in range(1, min(16, orig_start + 1)):
            ch = text[orig_start - back]
            if ch == '[':
                # [を見つけた。前方に]{.frame}か]{.underline}があり、途中に[がないか確認
                after = text[orig_start:]
                frame_idx = after.find(']{.frame}')
                underline_idx = after.find(']{.underline}')
                end_idx = -1
                if frame_idx >= 0 and (underline_idx < 0 or frame_idx <= underline_idx):
                    end_idx = frame_idx
                elif underline_idx >= 0:
                    end_idx = underline_idx
                if end_idx >= 0 and '[' not in after[:end_idx]:
                    # frame構文のみ展開（短い構文を1スパンにする）
                    # underline構文は展開しない（長い構文の各単語を個別スパンにする）
                    if after[end_idx:].startswith(']{.frame}'):
                        inside_bracket = True
                        bracket_pos = orig_start - back
                break
            elif ch == ']':
                break  # 別の構文の境界に到達

    if inside_bracket:
        # 構文内部: [まで拡張（さらに**があれば含む）
        if bracket_pos >= 2 and text[bracket_pos - 2:bracket_pos] == '**':
            orig_start = bracket_pos - 2
        else:
            orig_start = bracket_pos
    else:
        # 構文外: 個別の書式マーカーをチェック
        if orig_start >= 3 and text[orig_start-3:orig_start] == '**[':
            # **[はframe構文の場合のみ展開
            if FRAME_PATTERN.match(text[orig_start-1:]):
                orig_start -= 3
            else:
                orig_start -= 2  # **のみ展開（[は含めない）
        elif orig_start >= 2 and text[orig_start-2:orig_start] == '**':
            orig_start -= 2
        elif orig_start >= 1 and text[orig_start-1] == '[':
            # [はframe構文の場合のみ展開（underlineは個別単語スパンのため展開しない）
            if FRAME_PATTERN.match(text[orig_start-1:]):
                orig_start -= 1
        elif orig_start >= 1 and text[orig_start-1] == '~':
            orig_start -= 1
        elif orig_start >= 1 and text[orig_start-1] == '^':
            orig_start -= 1

    # 終了位置の後の書式記法を含める
    remaining_end = text[orig_end:]
    # ]{.frame/underline}拡張は、範囲内に未閉じの[がある場合のみ行う
    # （長い[text]{.underline}構文の途中で]{.underline}だけ含めると壊れた断片になる）
    range_text = text[orig_start:orig_end]
    has_unmatched_bracket = range_text.count('[') > range_text.count(']')

    if has_unmatched_bracket:
        # ]{.frame}**パターン
        if remaining_end.startswith(']{.frame}**'):
            orig_end += len(']{.frame}**')
        # ]{.underline}**パターン
        elif remaining_end.startswith(']{.underline}**'):
            orig_end += len(']{.underline}**')
        # ]{.frame}パターン
        elif remaining_end.startswith(']{.frame}'):
            orig_end += len(']{.frame}')
        # ]{.underline}パターン
        elif remaining_end.startswith(']{.underline}'):
            orig_end += len(']{.underline}')
        # スペース+]{.frame}パターン（スペースを含む場合）
        elif ']{.frame}' in remaining_end[:15]:
            frame_pos = remaining_end.find(']{.frame}')
            orig_end += frame_pos + len(']{.frame}')
        # スペース+]{.underline}パターン（スペースを含む場合）
        elif ']{.underline}' in remaining_end[:20]:
            underline_pos = remaining_end.find(']{.underline}')
            orig_end += underline_pos + len(']{.underline}')
        # 未閉じの[がある場合、距離制限なしで]{.frame/underline}を検索
        # （開始位置で[を含めたので、対応する閉じ記号も含める必要がある）
        elif ']{.frame}' in remaining_end:
            frame_pos = remaining_end.find(']{.frame}')
            if '[' not in remaining_end[:frame_pos]:
                orig_end += frame_pos + len(']{.frame}')
        elif ']{.underline}' in remaining_end:
            underline_pos = remaining_end.find(']{.underline}')
            if '[' not in remaining_end[:underline_pos]:
                orig_end += underline_pos + len(']{.underline}')
        # **パターン（単独のstrong）
        elif orig_end <= len(text) - 2 and text[orig_end:orig_end+2] == '**':
            orig_end += 2
        # ~パターン（subscript終了）
        elif orig_end < len(text) and text[orig_end] == '~':
            orig_end += 1
        # ^パターン（superscript終了）
        elif orig_end < len(text) and text[orig_end] == '^':
            orig_end += 1
    else:
        # 未閉じの[がない場合、]{.frame/underline}拡張はスキップ
        # **パターン（単独のstrong）
        if orig_end <= len(text) - 2 and text[orig_end:orig_end+2] == '**':
            orig_end += 2
        # ~パターン（subscript終了）
        elif orig_end < len(text) and text[orig_end] == '~':
            orig_end += 1
        # ^パターン（superscript終了）
        elif orig_end < len(text) and text[orig_end] == '^':
            orig_end += 1

    return orig_start, orig_end
