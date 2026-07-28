"""
XHTML処理モジュール。

XMLからXSLT変換で生成されたXHTMLコンテンツの処理、
位置マッピング等の機能を提供します。
"""
import re
import html
import xml.sax.saxutils as _saxutils
import xml.etree.ElementTree as ET
import bisect
from functools import lru_cache
from pathlib import Path

from text.common import TextNormalizer

# XSLTファイルのパス
_PROJECT_ROOT = Path(__file__).parent.parent
_XSLT_READING = _PROJECT_ROOT / "resources" / "xhtml_to_reading_text.xsl"

# モジュールレベルキャッシュ
_proc = None
_reading_exec = None


def _get_reading_exec():
    """キャッシュ済み (PySaxonProcessor, XsltExecutable) を返す。"""
    global _proc, _reading_exec
    if _reading_exec is None:
        try:
            from saxonche import PySaxonProcessor
        except ImportError:
            raise ImportError(
                "saxonche がインストールされていません。XML入力機能には saxonche が必要です。\n"
                "インストール方法: pip install saxonche\n"
                "ARM64環境では saxonche が利用できない場合があります。CommonMark（.md）入力のみ使用してください。"
            )
        _proc = PySaxonProcessor(license=False)
        xslt_proc = _proc.new_xslt30_processor()
        _reading_exec = xslt_proc.compile_stylesheet(
            stylesheet_file=str(_XSLT_READING)
        )
    return _proc, _reading_exec


def _xhtml_fragment_to_reading_text(xhtml: str) -> str:
    """XHTMLフラグメントから読みテキストを抽出する（XSLT使用、内部共通処理）。

    math要素をdata-yomi付きspanに前変換してからXSLTで処理する。
    """
    from mathconv.converter import get_current_processor, mathml_to_speech_xml
    math_proc = get_current_processor()
    sre_lang = math_proc.sre_lang if math_proc else "ja"

    def _replace_math(m: re.Match) -> str:
        speech = mathml_to_speech_xml(m.group(0), sre_lang)
        speech_escaped = (speech
                          .replace('&', '&amp;')
                          .replace('<', '&lt;')
                          .replace('>', '&gt;')
                          .replace('"', '&quot;'))
        return f'<span data-yomi="{speech_escaped}">数式</span>'

    fragment = re.sub(r'<math\b[^>]*>.*?</math>', _replace_math, xhtml, flags=re.DOTALL)
    proc, exec_ = _get_reading_exec()
    xdm_node = proc.parse_xml(xml_text=f'<fragment>{fragment}</fragment>')
    result = exec_.transform_to_string(xdm_node=xdm_node)
    return result if result is not None else ""


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
    - math要素: Speech Rule Engineで音声テキストに変換
    - ruby要素: rt（ルビ）部分のみ抽出、rb（親字）は除去
    - その他のタグ: 除去してテキスト内容のみ残す
    - 丸数字・ローマ数字等: 読み仮名に変換（text/processing.pyのnormalize_textと同様、
      TextGrid側の文字起こしがto_reading済みのため、揃える必要がある）
    """
    result = _xhtml_fragment_to_reading_text(xhtml)

    # 特殊文字を読み仮名に変換（MFAとの整合性のため。normalize_textと同じ処理）
    result = TextNormalizer.to_reading(result)

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


# ──────────────────────────────────────────────────────────────────────────────
# セグメントマップ（ElementTree ベース）
# ──────────────────────────────────────────────────────────────────────────────

def _text_orig_len(t: str) -> int:
    """テキストノードの元のXML文字列での長さ（&amp; 等のエスケープを考慮）"""
    return len(_saxutils.escape(t))


def _attr_orig_len(v: str) -> int:
    """属性値の元のXML文字列での長さ"""
    return len(html.escape(v, quote=True))


def _open_tag_orig_len(tag: str, attribs: dict) -> int:
    """<tag k="v"...> の文字列長"""
    n = 1 + len(tag)  # '<' + tagname
    for k, v in attribs.items():
        n += 1 + len(k) + 2 + _attr_orig_len(v) + 1  # ' key="value"'
    return n + 1  # '>'


def _self_close_orig_len(tag: str, attribs: dict) -> int:
    """<tag k="v".../> の文字列長"""
    return _open_tag_orig_len(tag, attribs) + 1  # '>' → '/>'


def _close_tag_orig_len(tag: str) -> int:
    """</tag> の文字列長"""
    return 3 + len(tag)


@lru_cache(maxsize=32)
def _build_segments(
    xhtml: str, sre_lang: str
) -> tuple[tuple[int, int, int, int], ...]:
    """
    XHTML文字列を解析し、セグメントマップを返す（キャッシュ済み）。

    各セグメント: (r_start, r_end, o_start, o_end)
      r_*: 読みテキスト（タグ除去後）での文字位置
      o_*: 元のXHTML文字列での文字位置

    インライン要素の開き・閉じタグは (r, r, o_tag_start, o_tag_end) として記録。
    同一の (xhtml, sre_lang) に対して複数回呼ばれる場合にキャッシュが効く。
    """
    from mathconv.converter import mathml_to_speech_xml

    # math → data-yomi span に置換（元のmath文字列長を記録）
    math_orig_lens: list[int] = []

    def _replace_math(m: re.Match) -> str:
        speech = mathml_to_speech_xml(m.group(0), sre_lang)
        speech_esc = html.escape(speech, quote=True)
        idx = len(math_orig_lens)
        math_orig_lens.append(len(m.group(0)))
        return f'<span data-yomi="{speech_esc}" data-math-idx="{idx}">数式</span>'

    fragment = re.sub(r'<math\b[^>]*>.*?</math>', _replace_math, xhtml, flags=re.DOTALL)

    try:
        root = ET.fromstring(f'<fragment>{fragment}</fragment>')
    except ET.ParseError:
        return ()

    segs: list[tuple[int, int, int, int]] = []

    def walk(elem: ET.Element, r: int, o: int) -> tuple[int, int]:
        # elem.text（最初の子の前のテキスト）
        if elem.text:
            tlen = len(elem.text)
            olen = _text_orig_len(elem.text)
            segs.append((r, r + tlen, o, o + olen))
            r += tlen
            o += olen

        for child in elem:
            tag = child.tag
            attrs = child.attrib

            if tag == 'ruby':
                rb = child.find('rb')
                rt = child.find('rt')
                rb_t = (rb.text or '') if rb is not None else ''
                rt_t = (rt.text or '') if rt is not None else ''
                o_ruby = (
                    _open_tag_orig_len('ruby', {})
                    + _open_tag_orig_len('rb', {}) + _text_orig_len(rb_t) + _close_tag_orig_len('rb')
                    + _open_tag_orig_len('rt', {}) + _text_orig_len(rt_t) + _close_tag_orig_len('rt')
                    + _close_tag_orig_len('ruby')
                )
                segs.append((r, r + len(rt_t), o, o + o_ruby))
                r += len(rt_t)
                o += o_ruby

            elif tag == 'span' and 'data-yomi' in attrs:
                yomi = attrs['data-yomi']
                math_idx = attrs.get('data-math-idx')
                if math_idx is not None:
                    o_span = math_orig_lens[int(math_idx)]
                else:
                    inner = child.text or ''
                    o_span = (
                        _open_tag_orig_len('span', attrs)
                        + _text_orig_len(inner)
                        + _close_tag_orig_len('span')
                    )
                segs.append((r, r + len(yomi), o, o + o_span))
                r += len(yomi)
                o += o_span

            elif tag == 'img':
                alt = attrs.get('alt', '')
                o_img = _self_close_orig_len('img', attrs)
                segs.append((r, r + len(alt), o, o + o_img))
                r += len(alt)
                o += o_img

            elif tag in ('u', 'strong', 'sub', 'sup', 'em', 'span'):
                # 透過インライン要素: 開き・閉じタグを幅ゼロセグメントとして記録
                o_open = _open_tag_orig_len(tag, attrs)
                segs.append((r, r, o, o + o_open))
                o += o_open
                r, o = walk(child, r, o)
                o_close = _close_tag_orig_len(tag)
                segs.append((r, r, o, o + o_close))
                o += o_close

            else:
                # 未知要素: orig位置を消費（reading は増やさない）
                o_open = _open_tag_orig_len(tag, attrs)
                segs.append((r, r, o, o + o_open))
                o += o_open
                r, o = walk(child, r, o)
                o_close = _close_tag_orig_len(tag)
                segs.append((r, r, o, o + o_close))
                o += o_close

            # child.tail（この子の後、次の兄弟の前のテキスト）
            if child.tail:
                tlen = len(child.tail)
                olen = _text_orig_len(child.tail)
                segs.append((r, r + tlen, o, o + olen))
                r += tlen
                o += olen

        return r, o

    walk(root, 0, 0)
    return tuple(segs)


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
    from mathconv.converter import get_current_processor
    math_proc = get_current_processor()
    sre_lang = math_proc.sre_lang if math_proc else "ja"

    segs = _build_segments(xhtml, sre_lang)
    if not segs:
        return reading_pos

    r_starts = tuple(s[0] for s in segs)
    idx = bisect.bisect_right(r_starts, reading_pos) - 1

    if idx < 0:
        return 0

    r_start, r_end, o_start, o_end = segs[idx]

    if reading_pos >= r_end:
        # このセグメントを超えている（= 次のセグメントの o_start に相当）
        return o_end
    # テキストセグメント内: 文字補間。アトミックセグメント(r_start==r_end)は o_start を返す。
    return o_start + (reading_pos - r_start)


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
    try:
        ET.fromstring(f'<fragment>{xhtml[start:end]}</fragment>')
        return start, end
    except ET.ParseError:
        pass

    from mathconv.converter import get_current_processor
    math_proc = get_current_processor()
    sre_lang = math_proc.sre_lang if math_proc else "ja"

    segs = _build_segments(xhtml, sre_lang)
    if not segs:
        return start, end

    # [start, end) の範囲に o_start があるが o_end が end を超えるセグメントを探す
    new_end = end
    for _, _, o_s, o_e in segs:
        if o_s < end and o_e > new_end:
            new_end = o_e

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


def extract_xhtml_reading_text(xhtml: str) -> str:
    """XHTMLフラグメントから読みテキストを抽出する（正規化前）。

    normalize_xhtml_text()と異なり、括弧・全角数字の正規化は行わない。
    TextGridマッチング用のスパン読みテキスト抽出に使用する。
    """
    return _xhtml_fragment_to_reading_text(xhtml)
