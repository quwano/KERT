import os
from datetime import datetime, timedelta
from typing import List, Final


def split_text_file() -> None:
    # 1. 入力ファイルの取得
    input_path: str = input("分割するファイルのパスを入力してください:\n").strip().strip('"')

    if not os.path.exists(input_path):
        print(f"エラー: ファイルが見つかりません: {input_path}")
        return

    start_time: datetime = datetime.now()

    base_dir: str = os.path.dirname(input_path)
    full_name: str = os.path.basename(input_path)
    file_name_wo_ext: str = os.path.splitext(full_name)[0]
    ext: str = os.path.splitext(full_name)[1]

    sections: List[List[str]] = []
    current_section: List[str] = []

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#'):
                    if current_section:
                        sections.append(current_section)
                    current_section = [line]
                else:
                    current_section.append(line)

            if current_section:
                sections.append(current_section)

        # 3. ファイル書き出し
        h2_count: int = 1
        for section in sections:
            # --- 末尾の空行を削除する処理 ---
            # rstrip()で改行や空白を消した結果、空になる要素を後ろから削る
            while section and not section[-1].strip():
                section.pop()

            if not section:
                continue

            # 最後の行だけ改行を取り除く（ファイル末尾の改行を完全に無くしたい場合）
            # もし「行としての改行は残したいが空行は不要」なら、while文だけでOKです。
            # ここでは「ファイルの一番最後が改行文字で終わらない」ように処理します。
            section[-1] = section[-1].rstrip('\n')
            # ------------------------------

            first_line: str = section[0]
            suffix: str = ""
            if first_line.startswith('##'):
                suffix = f"_{h2_count}"
                h2_count += 1
            elif first_line.startswith('#'):
                suffix = "_0"
            else:
                suffix = "_prologue"

            output_path: str = os.path.join(base_dir, f"{file_name_wo_ext}{suffix}{ext}")

            with open(output_path, 'w', encoding='utf-8') as out_f:
                out_f.writelines(section)
            print(f"保存完了: {os.path.basename(output_path)}")

    except Exception as e:
        print(f"エラーが発生しました: {e}")
        return

    end_time: datetime = datetime.now()
    duration: timedelta = end_time - start_time

    print("-" * 30)
    print(f"処理時間: {duration.total_seconds():.4f} 秒")
    print("-" * 30)


if __name__ == "__main__":
    split_text_file()