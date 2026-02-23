"""
TextGrid処理ユーティリティモジュール。

Montreal Forced Alignerが生成するTextGridファイルの
読み込み・解析機能を提供します。
"""
from pathlib import Path


def extract_textgrid_intervals(
    textgrid_path: str | Path
) -> tuple[list[tuple[str, float, float]], float]:
    """
    TextGridファイルからタイミング情報を抽出する。

    Parameters
    ----------
    textgrid_path : str | Path
        TextGridファイルのパス。

    Returns
    -------
    tuple[list[tuple[str, float, float]], float]
        - intervals : list[tuple[str, float, float]]
            (ラベル, 開始時間, 終了時間) のリスト。空ラベルは除外されます。
        - total_duration : float
            音声の総再生時間（秒）。

    Notes
    -----
    TextGridの最初のtierから単語情報を取得します。
    空文字列のラベルは除外されますが、<unk>などの特殊ラベルは保持されます。
    """
    import textgrid

    tg = textgrid.TextGrid.fromFile(str(textgrid_path))
    words_tier = tg[0]
    total_duration = tg.maxTime

    intervals: list[tuple[str, float, float]] = []
    for interval in words_tier:
        label = interval.mark.strip()
        if label:  # 空文字列のみ除外
            intervals.append((label, interval.minTime, interval.maxTime))

    return intervals, total_duration
