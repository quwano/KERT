import re
from pathlib import Path


# =============================================================================
# テキスト正規化クラス
# =============================================================================

class TextNormalizer:
    """テキスト正規化ユーティリティクラス。

    全角→半角変換、特殊文字の正規化など、共通の正規化処理を提供します。
    MFA用とTextGridマッチング用の両方で使用されます。
    """

    # 丸数字 → 半角数字
    CIRCLED_DIGIT_MAP = {
        "①": "1", "②": "2", "③": "3", "④": "4", "⑤": "5",
        "⑥": "6", "⑦": "7", "⑧": "8", "⑨": "9", "⑩": "10",
        "⑪": "11", "⑫": "12", "⑬": "13", "⑭": "14", "⑮": "15",
        "⑯": "16", "⑰": "17", "⑱": "18", "⑲": "19", "⑳": "20", "⓪": "0"
    }

    # ローマ数字 → 半角数字
    ROMAN_NUMERAL_MAP = {
        "Ⅰ": "1", "Ⅱ": "2", "Ⅲ": "3", "Ⅳ": "4", "Ⅴ": "5",
        "Ⅵ": "6", "Ⅶ": "7", "Ⅷ": "8", "Ⅸ": "9", "Ⅹ": "10"
    }

    # 丸囲み英字 → 半角英字
    CIRCLED_LETTERS = "ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ"
    NORMAL_LETTERS = "abcdefghijklmnopqrstuvwxyz"

    # 全角数字 → 半角数字
    FULLWIDTH_DIGITS = "０１２３４５６７８９"
    HALFWIDTH_DIGITS = "0123456789"

    # ハイフン・ダッシュの正規化マップ
    HYPHEN_MAP = {
        "－": "-",  # 全角ハイフンマイナス U+FF0D
        "–": "-",   # エンダッシュ U+2013
        "—": "-",   # エムダッシュ U+2014
        "―": "-",   # ホリゾンタルバー U+2015
    }

    # 括弧の正規化マップ
    BRACKET_MAP = {
        "（": "(", "）": ")",
        "「": "[", "」": "]",
        "『": "[", "』": "]",
    }

    # MFA用: 特殊文字→読み仮名マップ（VOICEVOXと同じ読みを使用）
    READING_MAP = {
        # 全角数字（段落番号などで使用）
        "１": "いち", "２": "に", "３": "さん", "４": "よん", "５": "ご",
        "６": "ろく", "７": "なな", "８": "はち", "９": "きゅう", "０": "ぜろ",
        # 括弧類（MFAが認識できないため除去、丸括弧はスペース化でVOICEVOXの単語境界を維持）
        "（": " ", "）": " ",  # 全角丸括弧
        "(": " ", ")": " ",    # 半角丸括弧
        "「": "", "」": "",  # 鉤括弧
        "『": "", "』": "",  # 二重鉤括弧
        # 丸数字
        "①": "いち", "②": "に", "③": "さん", "④": "よん", "⑤": "ご",
        "⑥": "ろく", "⑦": "なな", "⑧": "はち", "⑨": "きゅう", "⑩": "じゅう",
        "⑪": "じゅういち", "⑫": "じゅうに", "⑬": "じゅうさん", "⑭": "じゅうよん",
        "⑮": "じゅうご", "⑯": "じゅうろく", "⑰": "じゅうなな", "⑱": "じゅうはち",
        "⑲": "じゅうきゅう", "⑳": "にじゅう", "⓪": "ぜろ",
        # ローマ数字
        "Ⅰ": "いち", "Ⅱ": "に", "Ⅲ": "さん", "Ⅳ": "よん", "Ⅴ": "ご",
        "Ⅵ": "ろく", "Ⅶ": "なな", "Ⅷ": "はち", "Ⅸ": "きゅう", "Ⅹ": "じゅう",
        # 丸囲み英字
        "ⓐ": "えい", "ⓑ": "びい", "ⓒ": "しい", "ⓓ": "でぃー", "ⓔ": "いー",
        "ⓕ": "えふ", "ⓖ": "じー", "ⓗ": "えいち", "ⓘ": "あい", "ⓙ": "じぇい",
        # 波ダッシュ
        "〜": "から", "～": "から",
    }

    @classmethod
    def to_reading(cls, text: str) -> str:
        """特殊文字を読み仮名に変換する（MFA用）。

        VOICEVOXと同じ読みを使用して、音声とテキストのアライメントを正確にする。
        """
        result = text
        for char, reading in cls.READING_MAP.items():
            result = result.replace(char, reading)
        return result

    @classmethod
    def normalize_circled_digits(cls, text: str) -> str:
        """丸数字を半角数字に変換する。"""
        result = text
        for c, n in cls.CIRCLED_DIGIT_MAP.items():
            result = result.replace(c, n)
        return result

    @classmethod
    def normalize_roman_numerals(cls, text: str) -> str:
        """ローマ数字を半角数字に変換する。"""
        result = text
        for r, n in cls.ROMAN_NUMERAL_MAP.items():
            result = result.replace(r, n)
        return result

    @classmethod
    def normalize_circled_letters(cls, text: str) -> str:
        """丸囲み英字を半角英字に変換する。"""
        result = text
        for c, n in zip(cls.CIRCLED_LETTERS, cls.NORMAL_LETTERS):
            result = result.replace(c, n)
        return result

    @classmethod
    def normalize_fullwidth_digits(cls, text: str) -> str:
        """全角数字を半角数字に変換する。"""
        result = text
        for z, h in zip(cls.FULLWIDTH_DIGITS, cls.HALFWIDTH_DIGITS):
            result = result.replace(z, h)
        return result

    @classmethod
    def normalize_hyphens(cls, text: str) -> str:
        """ハイフン・ダッシュを半角ハイフンに正規化する。"""
        result = text
        for src, dst in cls.HYPHEN_MAP.items():
            result = result.replace(src, dst)
        return result

    @classmethod
    def normalize_brackets(cls, text: str) -> str:
        """括弧を半角に正規化する。"""
        result = text
        for src, dst in cls.BRACKET_MAP.items():
            result = result.replace(src, dst)
        return result

    @classmethod
    def normalize_all(cls, text: str, include_brackets: bool = True) -> str:
        """すべての正規化を適用する。

        Parameters
        ----------
        text : str
            正規化するテキスト。
        include_brackets : bool
            括弧の正規化を含めるかどうか。MFA用ではFalse推奨。
        """
        result = text
        result = cls.normalize_circled_digits(result)
        result = cls.normalize_roman_numerals(result)
        result = cls.normalize_circled_letters(result)
        result = cls.normalize_fullwidth_digits(result)
        result = cls.normalize_hyphens(result)
        if include_brackets:
            result = cls.normalize_brackets(result)
        return result


# =============================================================================
# 正規表現パターン
# =============================================================================

# ルビ記法のパターン: [漢字](-ふりがな)
# [^[\]]+ で [ と ] の両方を除外し、入れ子の [ による誤マッチを防止
RUBY_PATTERN = re.compile(r'\[([^[\]]+)\]\(-([^)]+)\)')

# 読み替え記法のパターン: [表示テキスト](+読み上げテキスト)
# XHTMLでは[ ]内を表示、音声では(+ )内を読み上げ、ルビタグなし
# [^[\]]+ で [ と ] の両方を除外
READING_SUB_PATTERN = re.compile(r'\[([^[\]]+)\]\(\+([^)]+)\)')

# 下付き文字のパターン: ~text~
SUBSCRIPT_PATTERN = re.compile(r'~([^~]+)~')

# 上付き文字のパターン: ^text^
SUPERSCRIPT_PATTERN = re.compile(r'\^([^\^]+)\^')

# 強調の太字パターン: **text**
STRONG_PATTERN = re.compile(r'\*\*(.+?)\*\*', re.DOTALL)

# Underlineパターン: [text]{.underline}
# 内部にルビ記法 [...](-...) 、読み替え記法 [...](+...) 、frame記法 [...]{.frame} を含むことを許可
# [^[\]]* : 角括弧以外の文字
# (?:\[[^\]]*\](?:\([+-][^)]*\)|\{\.frame\})[^[\]]*)* : ルビ/読み替え/frame記法とその後のテキスト（0回以上繰り返し）
UNDERLINE_PATTERN = re.compile(
    r'\[([^[\]]*(?:\[[^\]]*\](?:\([+-][^)]*\)|\{\.frame\})[^[\]]*)*)\]\{\.underline\}',
    re.DOTALL
)

# Frameパターン: [text]{.frame}
# Underlineと同様の構造で、内部にルビ記法や読み替え記法を含むことを許可
# さらに{.frame}を含むことも許可（入れ子対応）
FRAME_PATTERN = re.compile(
    r'\[([^[\]]*(?:\[[^\]]*\](?:\([+-][^)]*\)|\{\.frame\})[^[\]]*)*)\]\{\.frame\}',
    re.DOTALL
)

# 画像記法のパターン: ![代替テキスト](パス)
IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

# 枠のスタイル（一箇所で管理）
FRAME_STYLE = "border: solid 2px; padding: 0.25em; margin:0em 0.2em 0em 0.2em; white-space: nowrap;"


def ruby_to_reading(text: str) -> str:
    """ルビ記法をひらがな読みに変換

    例: [首都](-しゅと) → しゅと
    """
    return RUBY_PATTERN.sub(r'\2', text)


def ruby_to_xhtml(text: str) -> str:
    """ルビ記法をXHTMLのrubyタグに変換

    例: [首都](-しゅと) → <ruby>首都<rt>しゅと</rt></ruby>
    """
    return RUBY_PATTERN.sub(r'<ruby>\1<rt>\2</rt></ruby>', text)


def subscript_to_xhtml(text: str) -> str:
    """下付き文字記法をXHTMLのsubタグに変換

    例: H~2~O → H<sub>2</sub>O
    """
    return SUBSCRIPT_PATTERN.sub(r'<sub>\1</sub>', text)


def superscript_to_xhtml(text: str) -> str:
    """上付き文字記法をXHTMLのsupタグに変換

    例: 2^10^ → 2<sup>10</sup>
    """
    return SUPERSCRIPT_PATTERN.sub(r'<sup>\1</sup>', text)


def strong_to_xhtml(text: str) -> str:
    """太字記法をXHTMLのstrongタグに変換

    例: **重要** → <strong>重要</strong>
    """
    return STRONG_PATTERN.sub(r'<strong>\1</strong>', text)


def underline_to_xhtml(text: str) -> str:
    """アンダーライン記法をXHTMLのuタグに変換

    例: [重要]{.underline} → <u>重要</u>
    """
    return UNDERLINE_PATTERN.sub(r'<u>\1</u>', text)


def frame_to_xhtml(text: str) -> str:
    """枠記法をXHTMLのspanタグに変換

    例: [　ア　]{.frame} → <span style="...">　ア　</span>
    """
    def replace_frame(m):
        return f'<span style="{FRAME_STYLE}">{m.group(1)}</span>'
    return FRAME_PATTERN.sub(replace_frame, text)


def strip_formatting(text: str) -> str:
    """すべての書式記法を除去してプレーンテキストを返す

    読みテキスト生成やTextGridマッチング用。
    ルビは読み（ふりがな）に変換される。
    読み替え記法は読み上げテキストに変換される。
    画像記法は完全に除去される。

    例:
        [首都](-しゅと) → しゅと
        [2^10^](+にのじゅうじょう) → にのじゅうじょう
        H~2~O → H2O
        2^10^ → 210
        **重要** → 重要
        [text]{.underline} → text
        ![代替テキスト](path.png) → (除去)
    """
    result = text
    # 画像: ![alt](path) → (除去) ※他の記法より先に処理
    result = IMAGE_PATTERN.sub('', result)
    # Underline: [text]{.underline} → text
    result = UNDERLINE_PATTERN.sub(r'\1', result)
    # Frame: [text]{.frame} → text
    result = FRAME_PATTERN.sub(r'\1', result)
    # 太字: **text** → text
    result = STRONG_PATTERN.sub(r'\1', result)
    # 読み替え: [表示](+読み) → 読み（ルビより先に処理）
    result = READING_SUB_PATTERN.sub(r'\2', result)
    # ルビ: [漢字](-ふりがな) → ふりがな
    result = RUBY_PATTERN.sub(r'\2', result)
    # 下付き: ~text~ → text
    result = SUBSCRIPT_PATTERN.sub(r'\1', result)
    # 上付き: ^text^ → text
    result = SUPERSCRIPT_PATTERN.sub(r'\1', result)
    return result


def strip_formatting_for_display(text: str) -> str:
    """すべての書式記法を除去してプレーンテキストを返す（表示用）

    nav.xhtmlのタイトル表示など、書式なしのプレーンテキストが
    必要な場合に使用。ルビは漢字部分を保持、読み替えは表示テキストを保持。

    例:
        [首都](-しゅと) → 首都（漢字を保持）
        [表示](+読み) → 表示（表示テキストを保持）
        H~2~O → H2O
        2^10^ → 210
        **重要** → 重要
        [text]{.underline} → text
        ![代替テキスト](path.png) → (除去)
    """
    result = text
    # 画像: ![alt](path) → (除去) ※他の記法より先に処理
    result = IMAGE_PATTERN.sub('', result)
    # Underline: [text]{.underline} → text
    result = UNDERLINE_PATTERN.sub(r'\1', result)
    # Frame: [text]{.frame} → text
    result = FRAME_PATTERN.sub(r'\1', result)
    # 太字: **text** → text
    result = STRONG_PATTERN.sub(r'\1', result)
    # 読み替え: [表示](+読み) → 表示（表示テキストを保持）
    result = READING_SUB_PATTERN.sub(r'\1', result)
    # ルビ: [漢字](-ふりがな) → 漢字（漢字を保持）
    result = RUBY_PATTERN.sub(r'\1', result)
    # 下付き: ~text~ → text
    result = SUBSCRIPT_PATTERN.sub(r'\1', result)
    # 上付き: ^text^ → text
    result = SUPERSCRIPT_PATTERN.sub(r'\1', result)
    return result


def create_reading_file(input_path: str, output_path: str) -> None:
    """元テキストから読みテキストファイルを生成

    すべての書式記法を除去したテキストファイルを出力する。
    音声生成やMFAアライメント用に使用。

    処理される書式:
    - ルビ記法 [漢字](-ふりがな) → ふりがな
    - 下付き ~text~ → text
    - 上付き ^text^ → text
    - 太字 **text** → text
    - Underline [text]{.underline} → text
    - 丸数字・ローマ数字 → 読み仮名（MFA用）
    """
    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()
    # 書式記法を除去
    result = strip_formatting(text)
    # 特殊文字を読み仮名に変換（MFAアライメント用）
    result = TextNormalizer.to_reading(result)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(result)


def change_suffix(origin_path_str:str, suffix:str):
    origin_path: Path = Path(origin_path_str)
    new_path: Path = origin_path.with_suffix(suffix)
    new_path_str: str = str(new_path)
    return new_path_str
