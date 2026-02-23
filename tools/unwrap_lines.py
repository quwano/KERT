"""
行結合ツール。

段落内の改行を半角スペースに置き換え、段落（空行）区切りは維持します。
出力ファイルは元のファイル名末尾に「_」を付加して保存されます。
"""
from pathlib import Path


def unwrap_lines(input_path: str) -> str:
    """
    テキストファイルの段落内改行をスペースに置換する。

    Parameters
    ----------
    input_path : str
        入力ファイルのパス。

    Returns
    -------
    str
        出力ファイルのパス。
    """
    input_file = Path(input_path)

    if not input_file.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {input_path}")

    # 出力ファイル名: 元のファイル名末尾に「_」を付加
    output_file = input_file.parent / f"{input_file.stem}_{input_file.suffix}"

    # ファイルを読み込む
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    result_lines: list[str] = []
    current_paragraph: list[str] = []

    for line in lines:
        stripped = line.rstrip('\n\r')

        if stripped == '':
            # 空行: 現在の段落を出力（空行自体は追加しない）
            if current_paragraph:
                result_lines.append(' '.join(current_paragraph))
                current_paragraph = []
        else:
            # 非空行: 段落に追加
            current_paragraph.append(stripped)

    # 最後の段落を出力
    if current_paragraph:
        result_lines.append(' '.join(current_paragraph))

    # ファイルに書き出し
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result_lines))
        if result_lines:
            f.write('\n')  # 最終行の改行

    return str(output_file)


def main() -> None:
    """メイン処理。"""
    print("行結合ツール")
    print("  段落内の改行をスペースに置換します。")
    print("  出力: 元のファイル名末尾に「_」を付加したファイル")
    print()

    input_path = input("入力ファイルのパスを指定してください:\n").strip()

    if not input_path:
        print("エラー: ファイルパスが指定されていません。")
        return

    try:
        output_path = unwrap_lines(input_path)
        print(f"出力: {output_path}")
    except FileNotFoundError as e:
        print(f"エラー: {e}")


if __name__ == "__main__":
    main()
