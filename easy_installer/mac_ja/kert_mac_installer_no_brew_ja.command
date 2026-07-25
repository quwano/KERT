#!/bin/bash
# KERT macOS セットアップ インストーラー（Homebrew なし版）
# 対応: macOS 11 以降（Apple Silicon / Intel 両対応）

# ============================================================
# カラー定義
# ============================================================
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

ARCH=$(uname -m)   # arm64 or x86_64
CONDA_DIR="$HOME/miniforge3"
CONDA_BIN="$CONDA_DIR/bin/conda"

# ============================================================
# ユーティリティ関数
# ============================================================

write_header() {
    clear
    echo ""
    echo -e "${CYAN}-----------------------------------------------------------${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}-----------------------------------------------------------${NC}"
    echo ""
}

ask_continue() {
    echo ""
    local _ac_choice
    while true; do
        read -rp "次のステップへ進みますか？ (Y=続ける / N=中止): " _ac_choice
        _ac_choice=$(echo "$_ac_choice" | tr '[:lower:]' '[:upper:]')
        [[ "$_ac_choice" == "Y" || "$_ac_choice" == "N" ]] && break
    done
    if [[ "$_ac_choice" == "N" ]]; then
        show_abort
        exit 1
    fi
}

show_abort() {
    clear
    echo ""
    echo -e "${YELLOW}===========================================================${NC}"
    echo -e "${YELLOW}   セットアップを中止しました${NC}"
    echo -e "${YELLOW}===========================================================${NC}"
    echo ""
    echo "セットアップを中止しました。"
    echo "途中までのインストールは有効です。"
    echo "続きから再開するには、このスクリプトを再度実行してください。"
    echo "（完了済みのステップは自動的にスキップされます）"
    echo ""
    read -rp "Enterキーを押して終了"
}

# シェルプロファイルに PATH を永続登録する
add_to_path_persistent() {
    local new_path="$1"
    local shell_profile
    if [[ "$SHELL" == *"zsh"* ]]; then
        shell_profile="$HOME/.zshrc"
    else
        shell_profile="$HOME/.bash_profile"
    fi

    if ! grep -qF "$new_path" "$shell_profile" 2>/dev/null; then
        echo "" >> "$shell_profile"
        echo "export PATH=\"$new_path:\$PATH\"" >> "$shell_profile"
        echo "[完了] PATH への永続登録が完了しました: $new_path"
        echo "       設定ファイル: $shell_profile"
    else
        echo "[OK] PATH にすでに登録されています: $new_path"
    fi

    # 現在のセッションにも反映
    export PATH="$new_path:$PATH"
}

# conda コマンドのフルパスを返す（なければ空文字）
resolve_conda() {
    if command -v conda &>/dev/null; then
        command -v conda
    elif [ -f "$CONDA_BIN" ]; then
        echo "$CONDA_BIN"
    else
        echo ""
    fi
}

# ============================================================
# ウェルカム画面
# ============================================================
clear
echo ""
echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}   KERT セットアップ インストーラー（macOS / Homebrew なし版）${NC}"
echo -e "${GREEN}   このスクリプトは KERT の動作環境を順番に構築します${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo ""
echo "【全インストール手順一覧】"
echo ""
echo "  ステップ 1  Python 3.12 のインストール"
echo "  ステップ 2  Miniforge（conda）のインストール"
echo "  ステップ 3  conda の PATH 設定確認"
echo "  ステップ 4  Montreal Forced Aligner（MFA）のインストール"
echo "  ステップ 5  spacy / sudachipy / sudachidict_core のインストール"
echo "  ステップ 6  VOICEVOX のインストール（手動）"
echo "  ステップ 7  FFmpeg のインストール"
echo "  ステップ 8  textgrid / saxonche のインストール"
echo "  ステップ 9  日本語 MFA モデルのダウンロード"
echo ""
echo "各ステップの最後に「続けるか中止するか」を確認します。"
echo "N を押すといつでも中止できます。"
echo ""
echo "動作環境: $(uname -s) $(uname -r) (${ARCH})"
echo ""
read -rp "Enterキーを押してインストールを開始"

# ============================================================
# ステップ 1: Python 3.12
# ============================================================
write_header "ステップ 1 / 9  :  Python 3.12 のインストール"

if python3.12 --version &>/dev/null; then
    echo "[OK] Python 3.12 はすでにインストールされています。スキップします。"
    python3.12 --version
else
    echo "Python 3.12 が見つかりません。ダウンロードしてインストールします..."
    echo ""
    echo "注意: インストール時にシステムパスワードの入力が必要です。"
    echo ""

    PY_PKG="/tmp/python-3.12.10-macos11.pkg"
    PY_URL="https://www.python.org/ftp/python/3.12.10/python-3.12.10-macos11.pkg"

    echo "ダウンロード中..."
    if curl -L --progress-bar -o "$PY_PKG" "$PY_URL"; then
        echo "ダウンロード完了。インストールを開始します..."
        echo "（システムパスワードの入力が求められます）"
        echo ""
        if sudo installer -pkg "$PY_PKG" -target /; then
            echo ""
            echo "[完了] Python 3.12 のインストールが完了しました。"
            PY312_BIN="/Library/Frameworks/Python.framework/Versions/3.12/bin"
            add_to_path_persistent "$PY312_BIN"
            python3.12 --version 2>/dev/null || true
        else
            echo ""
            echo -e "${RED}[エラー] Python のインストールに失敗しました。${NC}"
            echo "手動でインストールしてください:"
            echo "  https://www.python.org/downloads/release/python-31210/"
            echo "  ファイル: python-3.12.10-macos11.pkg"
            echo ""
        fi
    else
        echo ""
        echo -e "${RED}[エラー] Python インストーラーのダウンロードに失敗しました。${NC}"
        echo "手動でダウンロードしてください:"
        echo "  https://www.python.org/downloads/release/python-31210/"
        echo "  ファイル: python-3.12.10-macos11.pkg"
        echo ""
    fi

    echo "[3/3] pdfplumber Pillow をインストールしています..."
    if $PY_CMD -m pip install --break-system-packages pdfplumber Pillow; then
        echo "[完了] pdfplumber Pillow のインストールが完了しました。"
    else
        echo -e "${RED}[エラー] pdfplumber Pillow のインストールに失敗しました。${NC}"
    fi
fi

ask_continue

# ============================================================
# ステップ 2: Miniforge（conda）
# ============================================================
write_header "ステップ 2 / 9  :  Miniforge（conda）のインストール"

if command -v conda &>/dev/null; then
    echo "[OK] conda はすでに使用可能です。スキップします。"
    conda --version
elif [ -f "$CONDA_BIN" ]; then
    echo "[OK] Miniforge はすでにインストールされています。PATH を更新します。"
    export PATH="$CONDA_DIR/bin:$PATH"
    echo "PATH を更新しました（このセッション内）。"
else
    echo "Miniforge が見つかりません。ダウンロードしてインストールします..."
    echo ""

    if [ "$ARCH" = "arm64" ]; then
        MF_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-arm64.sh"
        MF_FILE="/tmp/Miniforge3-MacOSX-arm64.sh"
    else
        MF_URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-MacOSX-x86_64.sh"
        MF_FILE="/tmp/Miniforge3-MacOSX-x86_64.sh"
    fi

    echo "アーキテクチャ: ${ARCH}"
    echo "ダウンロード中..."

    if curl -L --progress-bar -o "$MF_FILE" "$MF_URL"; then
        chmod +x "$MF_FILE"
        echo "ダウンロード完了。インストールを開始します..."
        echo "（インストール先: $CONDA_DIR）"
        echo ""
        if bash "$MF_FILE" -b -p "$CONDA_DIR"; then
            echo ""
            echo "[完了] Miniforge のインストールが完了しました。"
            export PATH="$CONDA_DIR/bin:$PATH"
            echo "PATH を更新しました（このセッション内）。"
        else
            echo ""
            echo -e "${RED}[エラー] Miniforge のインストールに失敗しました。${NC}"
            echo "手動でインストールしてください:"
            echo "  https://github.com/conda-forge/miniforge/releases/latest"
            echo ""
        fi
    else
        echo ""
        echo -e "${RED}[エラー] Miniforge のダウンロードに失敗しました。${NC}"
        echo "手動でダウンロードしてください:"
        echo "  https://github.com/conda-forge/miniforge/releases/latest"
        echo ""
    fi
fi

ask_continue

# ============================================================
# ステップ 3: conda PATH 設定確認
# ============================================================
write_header "ステップ 3 / 9  :  conda の PATH 設定確認"

CONDA_CMD=$(resolve_conda)

if [ -n "$CONDA_CMD" ]; then
    echo "[OK] conda は使用可能です。"
    "$CONDA_CMD" --version

    # PATH への永続登録を確認
    if ! grep -qF "$CONDA_DIR/bin" "${HOME}/.zshrc" 2>/dev/null && \
       ! grep -qF "$CONDA_DIR/bin" "${HOME}/.bash_profile" 2>/dev/null; then
        add_to_path_persistent "$CONDA_DIR/bin"
    else
        echo "[OK] PATH への永続登録はすでに済んでいます。"
    fi
else
    # conda が見つからない場合、よくある場所を探す
    echo "conda が PATH にありません。インストール済みの conda を探しています..."
    echo ""
    FOUND_CONDA=""
    for candidate in \
        "$HOME/miniforge3/bin/conda" \
        "$HOME/miniconda3/bin/conda" \
        "$HOME/anaconda3/bin/conda"; do
        if [ -f "$candidate" ]; then
            FOUND_CONDA="$candidate"
            FOUND_DIR=$(dirname "$candidate")
            echo "発見: $candidate"
            break
        fi
    done

    if [ -n "$FOUND_CONDA" ]; then
        CONDA_BIN="$FOUND_CONDA"
        CONDA_DIR=$(dirname "$FOUND_DIR")
        add_to_path_persistent "$FOUND_DIR"
        "$CONDA_BIN" --version
    else
        echo -e "${YELLOW}[警告] conda の実行ファイルが見つかりませんでした。${NC}"
        echo "ステップ 2 に戻って Miniforge をインストールしてください。"
        echo ""
    fi
fi

ask_continue

# ============================================================
# ステップ 4: Montreal Forced Aligner（MFA）
# ============================================================
write_header "ステップ 4 / 9  :  Montreal Forced Aligner のインストール"

CONDA_CMD=$(resolve_conda)

if [ -z "$CONDA_CMD" ]; then
    echo -e "${RED}[エラー] conda が見つかりません。ステップ 2・3 を確認してください。${NC}"
else
    echo "MFA の conda 環境（mfa）を確認しています..."
    echo ""

    if "$CONDA_CMD" run -n mfa echo check &>/dev/null 2>&1; then
        if "$CONDA_CMD" run -n mfa mfa version &>/dev/null 2>&1; then
            echo "[OK] MFA はすでにインストールされています。スキップします。"
            "$CONDA_CMD" run -n mfa mfa version
        else
            echo "MFA が見つかりません。mfa 環境にインストールします..."
            if "$CONDA_CMD" install -n mfa -c conda-forge montreal-forced-aligner -y; then
                echo ""
                echo "[完了] Montreal Forced Aligner のインストールが完了しました。"
            else
                echo ""
                echo -e "${RED}[エラー] MFA のインストールに失敗しました。${NC}"
                echo "conda が正しくインストールされ、インターネットに接続されているか確認してください。"
                echo ""
            fi
        fi
    else
        echo "conda 環境 \"mfa\" が存在しません。新規作成してインストールします..."
        echo "（処理に数分かかる場合があります）"
        if "$CONDA_CMD" create -n mfa -c conda-forge montreal-forced-aligner -y; then
            echo ""
            echo "[完了] Montreal Forced Aligner のインストールが完了しました。"
        else
            echo ""
            echo -e "${RED}[エラー] MFA のインストールに失敗しました。${NC}"
            echo "conda が正しくインストールされ、インターネットに接続されているか確認してください。"
            echo ""
        fi
    fi
fi

ask_continue

# ============================================================
# ステップ 5: spacy / sudachipy / sudachidict_core
# ============================================================
write_header "ステップ 5 / 9  :  spacy 等のインストール"

CONDA_CMD=$(resolve_conda)

if [ -z "$CONDA_CMD" ]; then
    echo -e "${RED}[エラー] conda が見つかりません。ステップ 2・3 を確認してください。${NC}"
else
    echo "mfa 環境内に spacy / sudachipy / sudachidict_core をインストールします..."
    echo "（処理に数分かかる場合があります）"
    echo ""

    if "$CONDA_CMD" run -n mfa pip install spacy sudachipy sudachidict_core; then
        echo ""
        echo "[完了] spacy / sudachipy / sudachidict_core のインストールが完了しました。"
    else
        echo ""
        echo -e "${RED}[エラー] インストールに失敗しました。${NC}"
        echo "MFA 環境（ステップ 4）が正常か確認してください。"
        echo ""
    fi
fi

ask_continue

# ============================================================
# ステップ 6: VOICEVOX（手動インストール）
# ============================================================
write_header "ステップ 6 / 9  :  VOICEVOX のインストール（手動）"

echo "VOICEVOX はグラフィカルインストーラーのため、手動でのインストールが必要です。"
echo ""
echo "【手順】"
echo "  1. ブラウザで https://voicevox.hiroshiba.jp/ を開く"
echo "  2. ページ上の「ダウンロード」ボタンをクリック"
echo "  3. macOS 版をダウンロードして実行"
echo "  4. インストール後、VOICEVOX を起動する"
echo "  5. メニューバーに VOICEVOX のアイコンが表示されれば起動完了"
echo ""
echo "KERT の日本語処理（ja_JP モード）には VOICEVOX の起動が必要です。"
echo "英語・ドイツ語のみ使用する場合はスキップしても構いません。"
echo ""

VV_CHOICE=""
while true; do
    read -rp "ブラウザで VOICEVOX の公式サイトを開きますか？ (Y=開く / N=スキップ): " VV_CHOICE
    VV_CHOICE=$(echo "$VV_CHOICE" | tr '[:lower:]' '[:upper:]')
    [[ "$VV_CHOICE" == "Y" || "$VV_CHOICE" == "N" ]] && break
done

if [[ "$VV_CHOICE" == "Y" ]]; then
    open "https://voicevox.hiroshiba.jp/"
    echo ""
    echo "ブラウザを開きました。インストールと起動が完了したら続けてください。"
fi

ask_continue

# ============================================================
# ステップ 7: FFmpeg
# ============================================================
write_header "ステップ 7 / 9  :  FFmpeg のインストール"

if command -v ffmpeg &>/dev/null; then
    echo "[OK] FFmpeg はすでに PATH に登録されています。スキップします。"
    ffmpeg -version 2>&1 | grep "ffmpeg version" | head -1
elif [ -f "$CONDA_DIR/bin/ffmpeg" ]; then
    echo "[OK] FFmpeg はすでにインストールされています（conda base 環境）。"
    add_to_path_persistent "$CONDA_DIR/bin"
    ffmpeg -version 2>&1 | grep "ffmpeg version" | head -1 || true
else
    CONDA_CMD=$(resolve_conda)
    if [ -z "$CONDA_CMD" ]; then
        echo -e "${RED}[エラー] conda が見つかりません。FFmpeg を手動でインストールしてください。${NC}"
        echo "  https://evermeet.cx/ffmpeg/"
        echo "  ダウンロードした ffmpeg バイナリを /usr/local/bin/ にコピーしてください。"
    else
        echo "FFmpeg が見つかりません。conda-forge 経由でインストールします..."
        echo "（処理に数分かかる場合があります）"
        echo ""
        if "$CONDA_CMD" install -c conda-forge ffmpeg -y; then
            echo ""
            echo "[完了] FFmpeg のインストールが完了しました。"
            add_to_path_persistent "$CONDA_DIR/bin"
            ffmpeg -version 2>&1 | grep "ffmpeg version" | head -1 || true
        else
            echo ""
            echo -e "${RED}[エラー] FFmpeg のインストールに失敗しました。${NC}"
            echo "手動でインストールしてください:"
            echo "  https://evermeet.cx/ffmpeg/"
            echo "  ダウンロードした ffmpeg バイナリを /usr/local/bin/ にコピーしてください。"
            echo ""
        fi
    fi
fi

ask_continue

# ============================================================
# ステップ 8: textgrid / saxonche
# ============================================================
write_header "ステップ 8 / 9  :  textgrid / saxonche のインストール"

# 使用する Python コマンドを決定
PY_CMD=""
if python3.12 --version &>/dev/null; then
    PY_CMD="python3.12"
elif python3 --version &>/dev/null; then
    PY_CMD="python3"
fi

if [ -z "$PY_CMD" ]; then
    echo -e "${RED}[エラー] Python が見つかりません。ステップ 1 を確認してください。${NC}"
    echo ""
else
    echo "使用する Python: $PY_CMD ($($PY_CMD --version))"
    echo ""

    echo "[1/3] textgrid をインストールしています..."
    if $PY_CMD -m pip install --break-system-packages textgrid; then
        echo "[完了] textgrid のインストールが完了しました。"
    else
        echo -e "${RED}[エラー] textgrid のインストールに失敗しました。${NC}"
    fi

    echo ""

    echo "[2/3] saxonche をインストールしています..."
    if $PY_CMD -m pip install --break-system-packages saxonche; then
        echo "[完了] saxonche のインストールが完了しました。"
    else
        echo -e "${RED}[エラー] saxonche のインストールに失敗しました。${NC}"
        echo "インターネット接続と Python のバージョンを確認してください。"
    fi

    echo ""

    echo "[3/3] tkinterdnd2 をインストールしています..."
    if $PY_CMD -m pip install --break-system-packages "tkinterdnd2>=0.4.2,<0.5.0"; then
        echo "[完了] tkinterdnd2 のインストールが完了しました。"
    else
        echo -e "${RED}[エラー] tkinterdnd2 のインストールに失敗しました。${NC}"
    fi
fi

ask_continue

# ============================================================
# ステップ 9: 日本語 MFA モデルのダウンロード
# ============================================================
write_header "ステップ 9 / 9  :  日本語 MFA モデルのダウンロード"

CONDA_CMD=$(resolve_conda)

if [ -z "$CONDA_CMD" ]; then
    echo -e "${RED}[エラー] conda が見つかりません。ステップ 2・3 を確認してください。${NC}"
else
    echo "日本語 MFA モデル（辞書・音響モデル）をダウンロードします。"
    echo "（ファイルサイズが大きいため、数分かかる場合があります）"
    echo ""

    echo "[1/2] 日本語辞書モデルをダウンロードしています..."
    if "$CONDA_CMD" run -n mfa mfa model download dictionary japanese_mfa; then
        echo "[完了] 日本語辞書モデルのダウンロードが完了しました。"
    else
        echo -e "${RED}[エラー] 日本語辞書モデルのダウンロードに失敗しました。${NC}"
        echo "インターネット接続と MFA 環境を確認してください。"
    fi

    echo ""

    echo "[2/2] 日本語音響モデルをダウンロードしています..."
    if "$CONDA_CMD" run -n mfa mfa model download acoustic japanese_mfa; then
        echo "[完了] 日本語音響モデルのダウンロードが完了しました。"
    else
        echo -e "${RED}[エラー] 日本語音響モデルのダウンロードに失敗しました。${NC}"
        echo "インターネット接続と MFA 環境を確認してください。"
    fi
fi

ask_continue

# start_kert.command に実行権限を付与
KERT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
if [ -f "$KERT_DIR/start_kert.command" ]; then
    chmod +x "$KERT_DIR/start_kert.command"
fi

# ============================================================
# 完了画面
# ============================================================
clear
echo ""
echo -e "${GREEN}===========================================================${NC}"
echo -e "${GREEN}   セットアップが完了しました！${NC}"
echo -e "${GREEN}===========================================================${NC}"
echo ""
echo "すべてのインストール手順が完了しました。"
echo ""
echo "【次のステップ】"
echo "  1. ターミナルを再起動する（PATH の変更を反映するため）"
echo "  2. VOICEVOX を起動する（日本語使用時）"
echo "  3. KERT フォルダ内の start_kert.command をダブルクリックして起動する"
echo ""
echo "ご不明な点は README.md または README_ja.md をご参照ください。"
echo ""
read -rp "Enterキーを押して終了"
