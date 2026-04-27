"""
PDFファイルの解析モジュール。

pdfplumberを使用してPDFからテキストを抽出し、見出し階層を構築します。
見出し検出モードを heading_mode パラメータで切り替え可能です。

見出し検出モード:
    'legal'  : 第n章/条/節等の法令文言パターン（デフォルト）
    'visual' : フォントサイズ・色・背景矩形によるスコアリング
    'symbol' : ■/【】/1./①等の記号・番号プレフィックス
"""
import html
import json
import logging
import re
import unicodedata
from pathlib import Path
from statistics import mode as _stat_mode
from typing import TYPE_CHECKING

from parsers.radicalchar import normalize as _normalize_radicals

logging.getLogger('pdfminer').setLevel(logging.ERROR)

try:
    import pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except ImportError:
    _PDFPLUMBER_AVAILABLE = False

try:
    from PIL import Image as _PIL_Image
    _PILLOW_AVAILABLE = True
except ImportError:
    _PILLOW_AVAILABLE = False

if TYPE_CHECKING:
    from parsers.commonmark import HeadingInfo

# --- x0 座標の閾値（legal モード: 衆議院Webサイト形式PDFの実測値）---
_X0_JO_MAX   = 143.0  # 条・項の最大x0
_X0_NOTE_MAX = 153.0  # 〔…〕・号の最大x0

# --- スキップパターン（ヘッダー・フッター・ナビゲーション）---
_SKIP_PAT = re.compile(
    r'このページのトップ|サイトマップ|ヘルプ|サイト内検索|'
    r'衆議院トップページ|音声読み上げ|＞|'
    r'^日本国憲法$|'
    r'昭和[0-9０-９一二三四五六七八九十百]+年|'
    r'↑PAGETOP|PageTop|pagetop'
)

# visual モード: 背景矩形として認識する最大高さ（pt）。これ以上は背景全体を覆う矩形とみなしてスキップ。
_MAX_HEADING_RECT_HEIGHT_PT = 50.0

# ページ先頭からスキップするページ数（0=スキップなし）
_SKIP_FIRST_PAGES = 0

# 画像抽出の最小サイズ閾値（PDF座標系のポイント単位）
_MIN_IMAGE_HEIGHT_PT = 30.0
_MIN_IMAGE_WIDTH_PT  = 30.0

# --- 見出し検出設定のデフォルト値（resources/pdf_heading_patterns.json で上書き可）---
_DEFAULT_HEADING_CONFIG: dict = {
    "legal": {
        "shou": ["^第[〇一二三四五六七八九十百]+[章編部]"],
        "jo":   ["^第[〇一二三四五六七八九十百]+[条條節款目]$"],
        "ko":   ["^[0-9]+$"],
        "go":   ["^[一二三四五六七八九十]+$", "^[ア-ン]$"],
        "note": ["^〔.+〕$"]
    },
    "symbol": {
        "shou": ["^[■□●○◆◇]", "^【.+】$"],
        "jo":   ["^\\d+[.．]", "^\\d+$", "^\\(\\d+\\)$"]
    },
    "visual": {
        "size_ratio_threshold": 1.1,
        "score_shou_min": 3,
        "score_jo_min": 1
    }
}


def _load_heading_config() -> dict:
    """resources/pdf_heading_patterns.json を読み込む。失敗時はデフォルト値を使用。"""
    config_path = Path(__file__).parent.parent / "resources" / "pdf_heading_patterns.json"
    if config_path.exists():
        try:
            with open(config_path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return _DEFAULT_HEADING_CONFIG


_HEADING_CONFIG: dict = _load_heading_config()


def _compile_mode_patterns(config: dict, mode: str) -> dict[str, list]:
    """指定モードのパターン文字列をコンパイルして返す。"""
    mode_cfg = config.get(mode, {})
    return {
        kind: [re.compile(p) for p in patterns]
        for kind, patterns in mode_cfg.items()
        if isinstance(patterns, list)
    }


_PAT_LEGAL  = _compile_mode_patterns(_HEADING_CONFIG, 'legal')
_PAT_SYMBOL = _compile_mode_patterns(_HEADING_CONFIG, 'symbol')


# =============================================================================
# テキスト処理ユーティリティ
# =============================================================================

def _nfkc(text: str) -> str:
    """NFKC正規化と部首文字の統一漢字変換を行う。

    pdfminer が CID フォントの ToUnicode CMap を誤解釈して
    CJK Radicals Supplement (U+2E80-U+2EFF) を抽出するケースがある。
    NFKC では Kangxi Radicals (U+2F00-) は変換されるが Supplement 範囲は
    変換されないため、radicalchar ライブラリで補完する。
    """
    result = unicodedata.normalize('NFKC', text)
    return _normalize_radicals(result)


def _join_words(words: list[dict]) -> str:
    """x0座標順にwordsを結合する。単語間ギャップが0.5文字分超なら全角スペースを挿入。"""
    if not words:
        return ''
    sorted_w = sorted(words, key=lambda w: w['x0'])
    result = _nfkc(sorted_w[0]['text'])
    for i in range(1, len(sorted_w)):
        prev = sorted_w[i - 1]
        curr = sorted_w[i]
        gap = curr['x0'] - (prev['x0'] + prev.get('width', 0))
        char_w = prev.get('size', 8.7)
        if gap > char_w * 0.5:
            result += '　'
        result += _nfkc(curr['text'])
    return result


def _group_into_rows(words: list[dict]) -> list[list[dict]]:
    """top座標が近いword（±3pt）をグループ化して行のリストを返す。"""
    if not words:
        return []
    words_sorted = sorted(words, key=lambda w: w['top'])
    rows: list[list[dict]] = []
    cur = [words_sorted[0]]
    for w in words_sorted[1:]:
        if abs(w['top'] - cur[0]['top']) < 3.0:
            cur.append(w)
        else:
            rows.append(cur)
            cur = [w]
    rows.append(cur)
    return rows


# =============================================================================
# 見出し検出（3モード）
# =============================================================================

def _compute_page_stats(words: list[dict]) -> dict:
    """ページの最頻フォントサイズ・フォント名・文字色を返す（visual モード用）。"""
    sizes  = [round(w.get('size', 0), 1) for w in words if w.get('size')]
    fonts  = [w.get('fontname', '') for w in words if w.get('fontname')]
    colors = [str(w.get('non_stroking_color')) for w in words]
    return {
        'body_size':     _stat_mode(sizes)  if sizes  else 0.0,
        'body_fontname': _stat_mode(fonts)  if fonts  else '',
        'body_color':    _stat_mode(colors) if colors else 'None',
    }


def _row_overlaps_rect(sorted_w: list[dict], rects: list) -> bool:
    """行の中心点が塗りつぶし矩形の内側にあるか判定する（visual モード用）。

    - 行の中心点（垂直方向）を基準にすることで端点ギリギリの誤検出を防ぐ。
    - ページ全体を覆う大きな背景矩形（高さ > _MAX_HEADING_RECT_HEIGHT_PT）は無視する。
    """
    if not rects or not sorted_w:
        return False
    row_top    = min(w['top'] for w in sorted_w)
    row_bottom = max(w.get('bottom', w['top'] + w.get('size', 8)) for w in sorted_w)
    row_mid    = (row_top + row_bottom) / 2
    row_x0     = min(w['x0'] for w in sorted_w)
    row_x1     = max(w['x0'] + w.get('width', 0) for w in sorted_w)
    for rect in rects:
        if rect.get('non_stroking_color') is None:
            continue
        rect_height = rect['bottom'] - rect['top']
        if rect_height > _MAX_HEADING_RECT_HEIGHT_PT:
            continue
        if (rect['x0'] < row_x1 and rect['x1'] > row_x0 and
                rect['top'] <= row_mid <= rect['bottom']):
            return True
    return False


def _classify_row_legal(words: list[dict]) -> tuple[str, str, str]:
    """法令文言モード: 第n章/条/節/款/目、項、号、〔〕注記を検出。

    Returns (kind, marker_text, body_text)
    kind: 'skip'|'shou'|'jo'|'ko'|'go'|'note'|'body'
    """
    if not words:
        return ('skip', '', '')

    sorted_w  = sorted(words, key=lambda w: w['x0'])
    first     = sorted_w[0]
    first_text = _nfkc(first['text'])
    fn        = first.get('fontname', '')
    x0        = first['x0']
    full_text = _join_words(sorted_w)
    rest_text = _join_words(sorted_w[1:])

    if _SKIP_PAT.search(full_text):
        return ('skip', '', '')

    # W6フォント → 章タイトル（衆議院形式PDF用）
    if 'W6' in fn:
        return ('shou', full_text, '')

    for pat in _PAT_LEGAL.get('shou', []):
        if pat.match(full_text):
            return ('shou', full_text, '')

    for pat in _PAT_LEGAL.get('jo', []):
        if x0 <= _X0_JO_MAX and pat.match(first_text):
            return ('jo', first_text, rest_text)

    for pat in _PAT_LEGAL.get('ko', []):
        if x0 <= _X0_JO_MAX and pat.match(first_text):
            return ('ko', first_text, rest_text)

    for pat in _PAT_LEGAL.get('go', []):
        if x0 <= _X0_NOTE_MAX and pat.match(first_text):
            return ('go', first_text, rest_text)

    for pat in _PAT_LEGAL.get('note', []):
        if pat.match(full_text):
            return ('note', full_text, '')

    return ('body', '', full_text)


def _classify_row_visual(
    words: list[dict],
    page_stats: dict,
    page_rects: list
) -> tuple[str, str, str]:
    """視覚特徴スコアリングモード: フォントサイズ・色・背景矩形でスコアを合算して分類。

    スコア計算:
        size > modal * ratio : +2
        fontname ≠ modal     : +2
        color ≠ modal        : +1
        背景矩形と重なる      : +1
    """
    if not words:
        return ('skip', '', '')

    sorted_w  = sorted(words, key=lambda w: w['x0'])
    full_text = _join_words(sorted_w)

    if _SKIP_PAT.search(full_text):
        return ('skip', '', '')

    first      = sorted_w[0]
    row_size   = first.get('size', 0)
    row_font   = first.get('fontname', '')
    row_color  = str(first.get('non_stroking_color'))

    body_size  = page_stats.get('body_size', 0)
    body_font  = page_stats.get('body_fontname', '')
    body_color = page_stats.get('body_color', 'None')

    cfg            = _HEADING_CONFIG.get('visual', {})
    size_ratio     = cfg.get('size_ratio_threshold', 1.1)
    score_shou_min = cfg.get('score_shou_min', 3)
    score_jo_min   = cfg.get('score_jo_min', 1)

    score = 0
    if body_size > 0 and row_size > body_size * size_ratio:
        score += 2
    if body_font and row_font and row_font != body_font:
        score += 2
    if body_color != 'None' and row_color != body_color:
        score += 1
    if _row_overlaps_rect(sorted_w, page_rects):
        score += 1

    if score >= score_shou_min:
        return ('shou', full_text, '')
    elif score >= score_jo_min:
        return ('jo', full_text, '')
    return ('body', '', full_text)


def _classify_row_symbol(words: list[dict]) -> tuple[str, str, str]:
    """記号・番号付き見出しモード: ■/【】/1./①等を検出。"""
    if not words:
        return ('skip', '', '')

    sorted_w   = sorted(words, key=lambda w: w['x0'])
    full_text  = _join_words(sorted_w)
    first_text = _nfkc(sorted_w[0]['text'])
    rest_text  = _join_words(sorted_w[1:])

    if _SKIP_PAT.search(full_text):
        return ('skip', '', '')

    for pat in _PAT_SYMBOL.get('shou', []):
        if pat.match(full_text):
            return ('shou', full_text, '')

    for pat in _PAT_SYMBOL.get('jo', []):
        if pat.match(first_text):
            return ('jo', first_text, rest_text)

    return ('body', '', full_text)


def _classify_row(
    words: list[dict],
    mode: str = 'legal',
    page_stats: dict | None = None,
    page_rects: list | None = None
) -> tuple[str, str, str]:
    """見出し検出モードに応じて行を分類するディスパッチャ。"""
    if mode == 'visual':
        return _classify_row_visual(words, page_stats or {}, page_rects or [])
    elif mode == 'symbol':
        return _classify_row_symbol(words)
    else:
        return _classify_row_legal(words)


# =============================================================================
# 画像抽出
# =============================================================================

def _is_valid_pdf_image(img: dict) -> bool:
    """PDFの画像オブジェクトが抽出対象として有効かどうかを判定する。"""
    if img.get('imagemask'):
        return False
    if img.get('height', 0) < _MIN_IMAGE_HEIGHT_PT:
        return False
    if img.get('width', 0) < _MIN_IMAGE_WIDTH_PT:
        return False
    return True


def _extract_page_images(
    page,
    page_num: int,
    figure_dir: Path,
    img_digits: int
) -> list[tuple[float, str, str]]:
    """ページから有効な画像を抽出してファイルに保存する。

    Returns list of (top座標, 相対パス, altテキスト)。top昇順でソート済み。
    """
    if not _PILLOW_AVAILABLE:
        return []

    results: list[tuple[float, str, str]] = []
    valid_imgs = sorted(
        [img for img in page.images if _is_valid_pdf_image(img)],
        key=lambda x: x['top']
    )
    for idx, img in enumerate(valid_imgs, 1):
        stem     = f"p{page_num + 1:02d}_img{idx:0{img_digits}d}"
        filename = f"{stem}.png"
        rel_path = f"intermediate_products/figures/{filename}"
        try:
            data    = img['stream'].get_data()
            w, h    = img['srcsize']
            pil_img = _PIL_Image.frombytes('RGB', (w, h), data)
            pil_img.save(figure_dir / filename)
            results.append((img['top'], rel_path, stem))
        except Exception:
            pass
    return results


# =============================================================================
# メイン解析関数
# =============================================================================

def parse_pdf(file_path: str, heading_mode: str = 'legal') -> tuple:
    """PDFファイルを解析して見出し階層を構築する。

    Parameters
    ----------
    file_path : str
        入力PDFファイルのパス。
    heading_mode : str
        見出し検出モード。'legal'（デフォルト）/ 'visual' / 'symbol'。

    Returns
    -------
    tuple[HeadingInfo, list[str]]
        (root_heading, reading_lines)
    """
    from parsers.commonmark import HeadingInfo

    if not _PDFPLUMBER_AVAILABLE:
        raise ImportError(
            'pdfplumberがインストールされていません。'
            'pip install pdfplumber でインストールしてください。'
        )
    if not Path(file_path).exists():
        raise FileNotFoundError(f'ファイルが見つかりません: {file_path}')

    pdf_dir    = Path(file_path).parent
    figure_dir = pdf_dir / "intermediate_products" / "figures"

    # all_items: (top, kind, data...) のフラットリスト
    #   kind='row': item = (top, 'row', words, page_ctx)
    #   kind='img': item = (top, 'img', rel_path, alt_stem)
    all_items: list[tuple] = []

    with pdfplumber.open(file_path) as pdf:
        # パス1: 画像の事前カウント（ファイル名桁数決定用）
        images_per_page: dict[int, int] = {}
        for page_num, page in enumerate(pdf.pages):
            if page_num < _SKIP_FIRST_PAGES:
                continue
            count = sum(1 for img in page.images if _is_valid_pdf_image(img))
            if count > 0:
                images_per_page[page_num] = count

        max_count = max(images_per_page.values()) if images_per_page else 1
        img_digits = len(str(max_count))

        if images_per_page and _PILLOW_AVAILABLE:
            figure_dir.mkdir(parents=True, exist_ok=True)

        # パス2: テキスト行と画像を top 座標でソートして統合
        for page_num, page in enumerate(pdf.pages):
            if page_num < _SKIP_FIRST_PAGES:
                continue
            page_items: list[tuple] = []

            # non_stroking_color は visual モードで使用（常に取得しておく）
            words = page.extract_words(extra_attrs=['fontname', 'size', 'non_stroking_color'])

            # ページコンテキスト（visual モードのみ stats/rects を格納）
            page_ctx: dict = {}
            if heading_mode == 'visual':
                page_ctx['stats'] = _compute_page_stats(words)
                page_ctx['rects'] = page.rects

            for row in _group_into_rows(words):
                row_top = row[0]['top'] if row else 0.0
                page_items.append((row_top, 'row', row, page_ctx))

            for img_top, rel_path, alt_stem in _extract_page_images(
                page, page_num, figure_dir, img_digits
            ):
                page_items.append((img_top, 'img', rel_path, alt_stem))

            page_items.sort(key=lambda x: x[0])
            all_items.extend(page_items)

    # --- ルート見出し（書籍タイトル）---
    stem = Path(file_path).stem
    root: HeadingInfo = HeadingInfo(
        level=1,
        title=stem,
        title_xhtml=html.escape(stem),
        title_raw=stem
    )

    # --- 状態変数 ---
    current_shou: HeadingInfo | None = None
    current_jo:   HeadingInfo | None = None
    para_buf: list[str] = []
    pending_note: str | None = None

    current_jo = HeadingInfo(
        level=2,
        title='前文',
        title_xhtml=html.escape('前文'),
        title_raw='前文'
    )

    def _flush_para() -> None:
        nonlocal para_buf
        if para_buf:
            text = ''.join(para_buf).strip()
            if text:
                if current_jo is not None:
                    current_jo.content.append(text)
                elif current_shou is not None:
                    current_shou.content.append(text)
                else:
                    root.content.append(text)
        para_buf = []

    def _finish_jo() -> None:
        nonlocal current_jo
        _flush_para()
        if current_jo is not None and (current_jo.content or current_jo.children):
            target = current_shou if current_shou is not None else root
            target.children.append(current_jo)
        current_jo = None

    def _finish_shou() -> None:
        nonlocal current_shou
        _finish_jo()
        if current_shou is not None and (current_shou.content or current_shou.children):
            root.children.append(current_shou)
        current_shou = None

    # --- 行・画像ごとに分類して木構造を構築 ---
    for item in all_items:
        item_kind = item[1]

        if item_kind == 'img':
            rel_path, alt_stem = item[2], item[3]
            _flush_para()
            img_ref = f'![{alt_stem}]({rel_path})'
            target = (current_jo if current_jo is not None
                      else (current_shou if current_shou is not None else root))
            target.content.append(img_ref)
            continue

        # item_kind == 'row'
        words    = item[2]
        page_ctx = item[3]
        kind, marker, body = _classify_row(
            words, heading_mode,
            page_ctx.get('stats'), page_ctx.get('rects')
        )

        if kind == 'skip':
            continue

        elif kind == 'shou':
            # 直前が内容なし shou の場合はタイトルを連結（複数行見出しの結合）
            if (current_shou is not None and current_jo is None
                    and not para_buf and not current_shou.content and not current_shou.children):
                merged = current_shou.title + ' ' + marker
                current_shou.title       = merged
                current_shou.title_xhtml = html.escape(merged)
                current_shou.title_raw   = merged
            else:
                _finish_shou()
                pending_note = None
                current_shou = HeadingInfo(
                    level=2,
                    title=marker,
                    title_xhtml=html.escape(marker),
                    title_raw=marker
                )

        elif kind == 'jo':
            _finish_jo()
            current_jo = HeadingInfo(
                level=3,
                title=marker,
                title_xhtml=html.escape(marker),
                title_raw=marker
            )
            if pending_note:
                current_jo.content.append(pending_note)
                pending_note = None
            if body:
                para_buf.append(body)

        elif kind in ('ko', 'go'):
            _flush_para()
            prefix = marker + '　'
            para_buf.append(prefix + body if body else prefix)

        elif kind == 'note':
            _flush_para()
            pending_note = marker

        else:  # body
            para_buf.append(body)

    _finish_shou()

    # --- 読み上げ用テキスト行を生成 ---
    from parsers.commonmark import split_into_sections, generate_reading_text
    sections = split_into_sections(root)
    reading_lines = [
        line for line in generate_reading_text(sections).splitlines()
        if line.strip()
    ]

    return root, reading_lines


def pdf_to_commonmark(root: 'HeadingInfo') -> str:
    """HeadingInfoツリーからCommonMarkテキストを生成する。"""
    lines: list[str] = []

    def _traverse(node: 'HeadingInfo') -> None:
        prefix = '#' * max(1, node.level)
        lines.append(f'{prefix} {node.title}')
        lines.append('')
        for para in node.content:
            if isinstance(para, str) and para.strip():
                lines.append(para.strip())
                lines.append('')
        for child in node.children:
            _traverse(child)

    _traverse(root)
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + '\n'
