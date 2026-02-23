"""
XHTML処理モジュール。

XMLからXSLT変換で生成されたXHTMLコンテンツの処理、
位置マッピング等の機能を提供します。
"""
import re

# インライン要素のパターン（ruby, u, strong, sub, sup, em）
INLINE_ELEMENT_PATTERN = re.compile(
    r'<(ruby|u|strong|sub|sup|em)\b[^>]*>.*?</\1>',
    re.DOTALL
)


def normalize_xhtml_text(xhtml: str) -> str:
    """
    XHTMLコンテンツからタグを除去し、読みテキストを抽出する。

    XMLからXSLT変換で生成されたXHTMLコンテンツを処理し、
    TextGridマッチング用の正規化テキストを生成します。

    Parameters
    ----------
    xhtml : str
        XHTMLタグを含むテキスト。

    Returns
    -------
    str
        タグを除去し、正規化されたテキスト。

    Notes
    -----
    処理ルール:
    - ruby要素: rt（ルビ）部分のみ抽出、rb（親字）は除去
    - その他のタグ: 除去してテキスト内容のみ残す
    """
    result = xhtml

    # ruby要素: <ruby><rb>親字</rb><rt>読み</rt></ruby> → 読み
    result = re.sub(r'<ruby><rb>.*?</rb><rt>(.*?)</rt></ruby>', r'\1', result)

    # data-yomi属性付きspan: 表示テキストをyomi値に置換
    result = re.sub(
        r'<span\b[^>]*\bdata-yomi="([^"]*)"[^>]*>.*?</span>',
        r'\1',
        result
    )

    # その他すべてのタグを除去
    result = re.sub(r'<[^>]+>', '', result)

    # 括弧の正規化
    result = (result
              .replace("（", "(").replace("）", ")")
              .replace("「", "[").replace("」", "]")
              .replace("『", "[").replace("』", "]"))

    # 全角数字を半角に変換
    zen_digits = "０１２３４５６７８９"
    han_digits = "0123456789"
    for z, h in zip(zen_digits, han_digits):
        result = result.replace(z, h)

    return result


def _get_inner_text_length(xhtml: str) -> int:
    """XHTML要素の内部テキスト長（タグ除去後）を取得する。"""
    # ruby要素: rt部分の長さ
    text = re.sub(r'<ruby><rb>.*?</rb><rt>(.*?)</rt></ruby>', r'\1', xhtml)
    # data-yomi属性付きspan: yomi値の長さで計算
    text = re.sub(
        r'<span\b[^>]*\bdata-yomi="([^"]*)"[^>]*>.*?</span>',
        r'\1',
        text
    )
    # その他のタグを除去
    text = re.sub(r'<[^>]+>', '', text)
    return len(text)


def xhtml_reading_pos_to_original(xhtml: str, reading_pos: int) -> int:
    """
    XHTML読みテキストでの位置を元のXHTMLテキスト位置に変換する。

    Parameters
    ----------
    xhtml : str
        XHTMLタグを含むテキスト。
    reading_pos : int
        読みテキスト（タグ除去後）での位置。

    Returns
    -------
    int
        元のXHTMLテキストでの対応位置。
    """
    original_pos = 0
    current_reading_pos = 0

    while current_reading_pos < reading_pos and original_pos < len(xhtml):
        remaining = xhtml[original_pos:]

        # ruby要素のチェック: <ruby><rb>...</rb><rt>...</rt></ruby>
        ruby_match = re.match(r'<ruby><rb>(.*?)</rb><rt>(.*?)</rt></ruby>', remaining)
        if ruby_match:
            reading_len = len(ruby_match.group(2))  # rt部分（読み）の長さ
            if current_reading_pos + reading_len <= reading_pos:
                current_reading_pos += reading_len
                original_pos += len(ruby_match.group(0))
                continue
            else:
                # ruby内でreading_posに達した場合、ruby全体を含める
                break

        # data-yomi属性付きspanのチェック
        yomi_match = re.match(
            r'<span\b[^>]*\bdata-yomi="([^"]*)"[^>]*>.*?</span>',
            remaining
        )
        if yomi_match:
            yomi_text = yomi_match.group(1)
            reading_len = len(yomi_text)
            if current_reading_pos + reading_len <= reading_pos:
                current_reading_pos += reading_len
                original_pos += len(yomi_match.group(0))
                continue
            else:
                # yomi内でreading_posに達した場合、span全体を含める
                break

        # インライン要素のチェック: <tag>...</tag>
        inline_match = re.match(r'<(u|strong|sub|sup|em)\b[^>]*>(.*?)</\1>', remaining, re.DOTALL)
        if inline_match:
            inner_content = inline_match.group(2)
            inner_reading_len = _get_inner_text_length(inner_content)
            if current_reading_pos + inner_reading_len <= reading_pos:
                current_reading_pos += inner_reading_len
                original_pos += len(inline_match.group(0))
                continue
            else:
                # 要素内でreading_posに達した場合、開始タグの後に進む
                tag_len = len(f'<{inline_match.group(1)}>')
                original_pos += tag_len
                # 内部コンテンツを再帰的に処理
                inner_offset = reading_pos - current_reading_pos
                inner_pos = xhtml_reading_pos_to_original(inner_content, inner_offset)
                return original_pos + inner_pos

        # 開始タグのチェック: <tag> または <tag attr="...">
        tag_match = re.match(r'<[^>]+>', remaining)
        if tag_match:
            # タグ自体はスキップ（読みテキストには含まれない）
            original_pos += len(tag_match.group(0))
            continue

        # 通常の文字
        current_reading_pos += 1
        original_pos += 1

    return original_pos


def _balance_xhtml_tags(xhtml: str, start: int, end: int) -> tuple[int, int]:
    """
    XHTML範囲内のタグを平衡化する。

    抽出範囲内で開いているが閉じていないタグがあれば、
    終了位置を拡張して閉じタグを含める。

    Parameters
    ----------
    xhtml : str
        元のXHTMLテキスト。
    start : int
        開始位置。
    end : int
        終了位置。

    Returns
    -------
    tuple[int, int]
        平衡化された (開始位置, 終了位置)。
    """
    extracted = xhtml[start:end]

    # タグを出現順に取得
    tag_pattern = re.compile(r'<(/?)(ruby|u|strong|sub|sup|em)\b[^>]*>')
    tag_stack = []

    for match in tag_pattern.finditer(extracted):
        is_close = match.group(1) == '/'
        tag_name = match.group(2)

        if is_close:
            # 閉じタグ: スタックから対応する開きタグをpop
            if tag_stack and tag_stack[-1] == tag_name:
                tag_stack.pop()
        else:
            # 開きタグ: スタックにpush
            tag_stack.append(tag_name)

    # 未閉じタグがあれば、閉じタグを探して範囲を拡張
    new_end = end
    search_start = end

    for tag in reversed(tag_stack):
        close_tag = f'</{tag}>'
        remaining = xhtml[search_start:]
        close_pos = remaining.find(close_tag)
        if close_pos != -1:
            new_end = search_start + close_pos + len(close_tag)
            search_start = new_end

    return start, new_end


def get_xhtml_original_range(xhtml: str, reading_start: int, reading_len: int) -> tuple[int, int]:
    """
    XHTML読みテキストでの範囲を元のXHTMLテキスト範囲に変換する。

    タグが途中で切れないように、開きタグに対応する閉じタグまで
    範囲を拡張します。

    Parameters
    ----------
    xhtml : str
        XHTMLタグを含むテキスト。
    reading_start : int
        読みテキストでの開始位置。
    reading_len : int
        読みテキストでの長さ。

    Returns
    -------
    tuple[int, int]
        元のXHTMLテキストでの (開始位置, 終了位置) のタプル。
    """
    orig_start = xhtml_reading_pos_to_original(xhtml, reading_start)
    orig_end = xhtml_reading_pos_to_original(xhtml, reading_start + reading_len)

    # タグを平衡化
    orig_start, orig_end = _balance_xhtml_tags(xhtml, orig_start, orig_end)

    return orig_start, orig_end
