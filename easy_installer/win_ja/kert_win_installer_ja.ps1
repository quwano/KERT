﻿#Requires -Version 5.1
# KERT Windows セットアップ インストーラー

$Host.UI.RawUI.WindowTitle = "KERT セットアップ インストーラー"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# ============================================================
# ユーティリティ関数
# ============================================================

function Write-Header {
    param([string]$Title)
    Clear-Host
    Write-Host ""
    Write-Host "-----------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host "-----------------------------------------------------------" -ForegroundColor Cyan
    Write-Host ""
}

function Ask-Continue {
    Write-Host ""
    do {
        $choice = (Read-Host "次のステップへ進みますか？ (Y=続ける / N=中止)").Trim().ToUpper()
    } while ($choice -ne 'Y' -and $choice -ne 'N')
    if ($choice -eq 'N') {
        Show-Abort
        exit 1
    }
}

function Show-Abort {
    Clear-Host
    Write-Host ""
    Write-Host "===========================================================" -ForegroundColor Yellow
    Write-Host "   セットアップを中止しました" -ForegroundColor Yellow
    Write-Host "===========================================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "セットアップを中止しました。"
    Write-Host "途中までのインストールは有効です。"
    Write-Host "続きから再開するには、このスクリプトを再度実行してください。"
    Write-Host "（完了済みのステップは自動的にスキップされます）"
    Write-Host ""
    Read-Host "Enterキーを押して終了"
}

function Add-ToUserPath {
    param([string]$NewPath)
    if ($env:PATH -notlike "*$NewPath*") {
        $env:PATH = "$NewPath;$env:PATH"
    }
    $userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($userPath -notlike "*$NewPath*") {
        try {
            [Environment]::SetEnvironmentVariable("PATH", "$NewPath;$userPath", "User")
            Write-Host "[完了] PATH への永続登録が完了しました: $NewPath"
        } catch {
            Write-Host "[警告] PATH の永続保存に失敗しました。次回起動時に手動設定してください。" -ForegroundColor Yellow
            Write-Host "       追加するフォルダ: $NewPath"
        }
    }
}

# ============================================================
# ウェルカム画面
# ============================================================
Clear-Host
Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "   KERT セットアップ インストーラー" -ForegroundColor Green
Write-Host "   このスクリプトは KERT の動作環境を順番に構築します" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "【全インストール手順一覧】"
Write-Host ""
Write-Host "  ステップ 1  Python 3.12 のインストール"
Write-Host "  ステップ 2  Miniforge（conda）のインストール"
Write-Host "  ステップ 3  conda の PATH 設定確認"
Write-Host "  ステップ 4  Montreal Forced Aligner（MFA）のインストール"
Write-Host "  ステップ 5  spacy / sudachipy / sudachidict_core のインストール"
Write-Host "  ステップ 6  VOICEVOX のインストール（手動）"
Write-Host "  ステップ 7  FFmpeg のインストール"
Write-Host "  ステップ 8  textgrid / saxonche のインストール"
Write-Host "  ステップ 9  日本語 MFA モデルのダウンロード"
Write-Host ""
Write-Host "各ステップの最後に「続けるか中止するか」を確認します。"
Write-Host "N を押すといつでも中止できます。"
Write-Host ""
Read-Host "Enterキーを押してインストールを開始"

# ============================================================
# ステップ 1: Python 3.12
# ============================================================
Write-Header "ステップ 1 / 9  :  Python 3.12 のインストール"

$pyOk = $false
try {
    $pyVer = & py -3.12 --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Python 3.12 はすでにインストールされています。スキップします。"
        Write-Host $pyVer
        $pyOk = $true
    }
} catch {}

if (-not $pyOk) {
    Write-Host "Python 3.12 が見つかりません。ダウンロードしてインストールします..."
    Write-Host ""
    $pyInstaller = "$env:TEMP\python-3.12.10-amd64.exe"

    Write-Host "ダウンロード中..."
    $downloadOk = $true
    try {
        Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' `
            -OutFile $pyInstaller -ErrorAction Stop
    } catch {
        $downloadOk = $false
        Write-Host ""
        Write-Host "[エラー] Python インストーラーのダウンロードに失敗しました。" -ForegroundColor Red
        Write-Host "手動でダウンロードしてください:"
        Write-Host "  https://www.python.org/downloads/release/python-31210/"
        Write-Host "  ファイル: python-3.12.10-amd64.exe"
        Write-Host ""
    }

    if ($downloadOk -and (Test-Path $pyInstaller)) {
        Write-Host "ダウンロード完了。インストールを開始します（しばらくお待ちください）..."
        $result = Start-Process -FilePath $pyInstaller `
            -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0" -Wait -PassThru
        if ($result.ExitCode -ne 0) {
            Write-Host ""
            Write-Host "[エラー] Python のインストールに失敗しました（終了コード: $($result.ExitCode)）。" -ForegroundColor Red
            Write-Host "手動でインストールしてください:"
            Write-Host "  https://www.python.org/downloads/release/python-31210/"
            Write-Host ""
        } else {
            $pyPath = "$env:LOCALAPPDATA\Programs\Python\Python312"
            $pyScripts = "$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
            $env:PATH = "$pyPath;$pyScripts;$env:PATH"
            Write-Host ""
            Write-Host "[完了] Python 3.12 のインストールが完了しました。"
            try { & py -3.12 --version 2>&1 | Write-Host } catch {}
        }
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# ステップ 2: Miniforge
# ============================================================
Write-Header "ステップ 2 / 9  :  Miniforge（conda）のインストール"

$condaCmd = Get-Command conda -ErrorAction SilentlyContinue

if ($null -ne $condaCmd) {
    Write-Host "[OK] conda はすでに使用可能です。スキップします。"
    & conda --version
} elseif (Test-Path "$env:USERPROFILE\miniforge3\Scripts\conda.exe") {
    Write-Host "[OK] Miniforge はすでにインストールされています。PATH を更新します。"
    $env:PATH = "$env:USERPROFILE\miniforge3\Scripts;$env:USERPROFILE\miniforge3\condabin;$env:PATH"
    Write-Host "PATH を更新しました（このセッション内）。"
} else {
    Write-Host "Miniforge が見つかりません。ダウンロードしてインストールします..."
    Write-Host ""
    $mfInstaller = "$env:TEMP\Miniforge3-Windows-x86_64.exe"

    Write-Host "ダウンロード中..."
    $downloadOk = $true
    try {
        Invoke-WebRequest -Uri 'https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Windows-x86_64.exe' `
            -OutFile $mfInstaller -ErrorAction Stop
    } catch {
        $downloadOk = $false
        Write-Host ""
        Write-Host "[エラー] Miniforge インストーラーのダウンロードに失敗しました。" -ForegroundColor Red
        Write-Host "手動でダウンロードしてください:"
        Write-Host "  https://github.com/conda-forge/miniforge/releases/latest"
        Write-Host "  ファイル: Miniforge3-Windows-x86_64.exe"
        Write-Host ""
    }

    if ($downloadOk -and (Test-Path $mfInstaller)) {
        Write-Host "ダウンロード完了。インストールを開始します（しばらくお待ちください）..."
        $result = Start-Process -FilePath $mfInstaller `
            -ArgumentList "/S /D=$env:USERPROFILE\miniforge3" -Wait -PassThru
        if ($result.ExitCode -ne 0) {
            Write-Host ""
            Write-Host "[エラー] Miniforge のインストールに失敗しました（終了コード: $($result.ExitCode)）。" -ForegroundColor Red
            Write-Host "手動でインストールしてください:"
            Write-Host "  https://github.com/conda-forge/miniforge/releases/latest"
            Write-Host ""
        } else {
            Write-Host "[完了] Miniforge のインストールが完了しました。"
            $env:PATH = "$env:USERPROFILE\miniforge3\Scripts;$env:USERPROFILE\miniforge3\condabin;$env:PATH"
            Write-Host "PATH を更新しました（このセッション内）。"
        }
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# ステップ 3: conda PATH 確認・設定
# ============================================================
Write-Header "ステップ 3 / 9  :  conda の PATH 設定確認"

if ($null -ne (Get-Command conda -ErrorAction SilentlyContinue)) {
    Write-Host "[OK] conda は PATH に登録されています。"
    & conda --version
} else {
    Write-Host "conda が PATH にありません。conda フォルダを探しています..."
    Write-Host ""

    $condaFound = $null
    $condaScripts = $null

    if (Test-Path "$env:USERPROFILE\miniforge3\Scripts\conda.exe") {
        $condaFound = "$env:USERPROFILE\miniforge3"
        $condaScripts = "$env:USERPROFILE\miniforge3\Scripts"
        Write-Host "発見: $env:USERPROFILE\miniforge3"
    } elseif (Test-Path "$env:USERPROFILE\miniconda3\Scripts\conda.exe") {
        $condaFound = "$env:USERPROFILE\miniconda3"
        $condaScripts = "$env:USERPROFILE\miniconda3\Scripts"
        Write-Host "発見: $env:USERPROFILE\miniconda3"
    } elseif (Test-Path "$env:USERPROFILE\Anaconda3\Scripts\conda.exe") {
        $condaFound = "$env:USERPROFILE\Anaconda3"
        $condaScripts = "$env:USERPROFILE\Anaconda3\Scripts"
        Write-Host "発見: $env:USERPROFILE\Anaconda3"
    }

    if ($null -ne $condaFound) {
        Add-ToUserPath $condaScripts
        $env:PATH = "$condaScripts;$condaFound\condabin;$env:PATH"
        Write-Host "このセッションの PATH も更新しました。"
    } else {
        Write-Host "[警告] conda の実行ファイルが見つかりませんでした。" -ForegroundColor Yellow
        Write-Host "ステップ 2 に戻って Miniforge をインストールしてください。"
        Write-Host ""
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# ステップ 4: Montreal Forced Aligner（MFA）
# ============================================================
Write-Header "ステップ 4 / 9  :  Montreal Forced Aligner のインストール"

Write-Host "MFA の conda 環境（mfa）を確認しています..."
Write-Host ""

& conda run -n mfa echo check 2>&1 | Out-Null
$mfaEnvExists = ($LASTEXITCODE -eq 0)

if ($mfaEnvExists) {
    Write-Host "conda 環境 `"mfa`" は存在します。MFA 本体を確認しています..."
    & conda run -n mfa mfa version 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] MFA はすでにインストールされています。スキップします。"
        & conda run -n mfa mfa version
    } else {
        Write-Host "MFA が見つかりません。mfa 環境にインストールします..."
        & conda install -n mfa -c conda-forge montreal-forced-aligner -y
        if ($LASTEXITCODE -ne 0) {
            Write-Host ""
            Write-Host "[エラー] MFA のインストールに失敗しました。" -ForegroundColor Red
            Write-Host "conda が正しくインストールされ、インターネットに接続されているか確認してください。"
            Write-Host ""
        } else {
            Write-Host ""
            Write-Host "[完了] Montreal Forced Aligner のインストールが完了しました。"
        }
    }
} else {
    Write-Host "conda 環境 `"mfa`" が存在しません。新規作成してインストールします..."
    Write-Host "（処理に数分かかる場合があります）"
    & conda create -n mfa -c conda-forge montreal-forced-aligner -y
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "[エラー] MFA のインストールに失敗しました。" -ForegroundColor Red
        Write-Host "conda が正しくインストールされ、インターネットに接続されているか確認してください。"
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "[完了] Montreal Forced Aligner のインストールが完了しました。"
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# ステップ 5: spacy / sudachipy / sudachidict_core
# ============================================================
Write-Header "ステップ 5 / 9  :  spacy 等のインストール"

Write-Host "mfa 環境内に spacy / sudachipy / sudachidict_core をインストールします..."
Write-Host "（処理に数分かかる場合があります）"
Write-Host ""

& conda run -n mfa pip install spacy sudachipy sudachidict_core
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[エラー] インストールに失敗しました。" -ForegroundColor Red
    Write-Host "MFA 環境（ステップ 4）が正常か確認してください。"
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "[完了] spacy / sudachipy / sudachidict_core のインストールが完了しました。"
}

Write-Host ""
Ask-Continue

# ============================================================
# ステップ 6: VOICEVOX（手動インストール）
# ============================================================
Write-Header "ステップ 6 / 9  :  VOICEVOX のインストール（手動）"

Write-Host "VOICEVOX はグラフィカルインストーラーのため、手動でのインストールが必要です。"
Write-Host ""
Write-Host "【手順】"
Write-Host "  1. ブラウザで https://voicevox.hiroshiba.jp/ を開く"
Write-Host "  2. ページ上の「ダウンロード」ボタンをクリック"
Write-Host "  3. Windows 版をダウンロードして実行"
Write-Host "  4. インストール後、VOICEVOX を起動する"
Write-Host "  5. タスクバーに VOICEVOX のアイコンが表示されれば起動完了"
Write-Host ""
Write-Host "KERT の日本語処理（ja_JP モード）には VOICEVOX の起動が必要です。"
Write-Host "英語・ドイツ語のみ使用する場合はスキップしても構いません。"
Write-Host ""

do {
    $choice = (Read-Host "ブラウザで VOICEVOX の公式サイトを開きますか？ (Y=開く / N=スキップ)").Trim().ToUpper()
} while ($choice -ne 'Y' -and $choice -ne 'N')

if ($choice -eq 'Y') {
    Start-Process "https://voicevox.hiroshiba.jp/"
    Write-Host ""
    Write-Host "ブラウザを開きました。インストールと起動が完了したら続けてください。"
}

Write-Host ""
Ask-Continue

# ============================================================
# ステップ 7: FFmpeg
# ============================================================
Write-Header "ステップ 7 / 9  :  FFmpeg のインストール"

if ($null -ne (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Host "[OK] FFmpeg はすでに PATH に登録されています。スキップします。"
    & ffmpeg -version 2>&1 | Select-String -Pattern "ffmpeg version" | ForEach-Object { Write-Host $_ }
} elseif (Test-Path "$env:USERPROFILE\ffmpeg\bin\ffmpeg.exe") {
    Write-Host "[OK] FFmpeg はすでにインストールされています。PATH を更新します。"
    Add-ToUserPath "$env:USERPROFILE\ffmpeg\bin"
} else {
    Write-Host "FFmpeg が見つかりません。ダウンロードしてインストールします..."
    Write-Host ""
    $ffZip = "$env:TEMP\ffmpeg-latest.zip"
    $ffWork = "$env:TEMP\ffmpeg_work"

    Write-Host "ダウンロード中（数分かかる場合があります）..."
    $downloadOk = $true
    try {
        Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' `
            -OutFile $ffZip -ErrorAction Stop
    } catch {
        $downloadOk = $false
        Write-Host ""
        Write-Host "[エラー] FFmpeg のダウンロードに失敗しました。" -ForegroundColor Red
        Write-Host "手動でダウンロードしてください:"
        Write-Host "  https://ffmpeg.org/download.html"
        Write-Host "  または https://github.com/BtbN/FFmpeg-Builds/releases"
        Write-Host "  ダウンロード後、ffmpeg.exe を任意のフォルダに置き PATH に追加してください。"
        Write-Host ""
    }

    if ($downloadOk -and (Test-Path $ffZip)) {
        Write-Host "ダウンロード完了。展開しています..."
        if (Test-Path $ffWork) { Remove-Item $ffWork -Recurse -Force }
        New-Item -ItemType Directory -Path $ffWork | Out-Null

        $expandOk = $true
        try {
            Expand-Archive -LiteralPath $ffZip -DestinationPath $ffWork -Force -ErrorAction Stop
        } catch {
            $expandOk = $false
            Write-Host ""
            Write-Host "[エラー] ZIP の展開に失敗しました。" -ForegroundColor Red
            Write-Host "手動でインストールしてください: https://ffmpeg.org/download.html"
            Write-Host ""
        }

        if ($expandOk) {
            $ffExtracted = Get-ChildItem -Path $ffWork -Directory | Select-Object -First 1
            if ($null -eq $ffExtracted) {
                Write-Host ""
                Write-Host "[エラー] 展開フォルダが見つかりません。" -ForegroundColor Red
                Write-Host "手動でインストールしてください: https://ffmpeg.org/download.html"
                Write-Host ""
            } else {
                Write-Host "展開先: $($ffExtracted.FullName)"
                Write-Host "コピーしています..."
                $destBin = "$env:USERPROFILE\ffmpeg\bin"
                New-Item -ItemType Directory -Path $destBin -Force | Out-Null
                Copy-Item "$($ffExtracted.FullName)\bin\*" $destBin -Force
                Add-ToUserPath $destBin
                Write-Host ""
                Write-Host "[完了] FFmpeg のインストールが完了しました。"
                & ffmpeg -version 2>&1 | Select-String -Pattern "ffmpeg version" | ForEach-Object { Write-Host $_ }
            }
        }
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# ステップ 8: textgrid / saxonche
# ============================================================
Write-Header "ステップ 8 / 9  :  textgrid / saxonche のインストール"

# 使用する Python コマンドを決定
$pyExe = $null
$testOut = & py -3.12 --version 2>&1
if ($testOut -match "Python 3\.12") { $pyExe = "py -3.12" }

if ($null -eq $pyExe) {
    Write-Host "[エラー] Python 3.12 が見つかりません。ステップ 1 を確認してください。" -ForegroundColor Red
    Write-Host ""
} else {
    Write-Host "使用する Python: $pyExe ($testOut)"
    Write-Host ""

    # --- textgrid（純 Python、全プラットフォーム対応）---
    Write-Host "[1/3] textgrid をインストールしています..."
    $pyArgs = $pyExe.Split()
    & $pyArgs[0] @($pyArgs[1..99] + @("-m", "pip", "install", "textgrid"))
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[完了] textgrid のインストールが完了しました。"
    } else {
        Write-Host "[エラー] textgrid のインストールに失敗しました。" -ForegroundColor Red
    }

    Write-Host ""

    # --- saxonche（SaxonC バインディング、ARM64 Windows 非対応）---
    Write-Host "[2/3] saxonche をインストールしています..."
    $arch = $env:PROCESSOR_ARCHITECTURE
    if ($arch -eq "ARM64") {
        Write-Host ""
        Write-Host "[警告] ARM64 Windows 環境が検出されました。" -ForegroundColor Yellow
        Write-Host "saxonche は現在 ARM64 Windows 向けパッケージが PyPI に存在しないため、"
        Write-Host "自動インストールできません。"
        Write-Host ""
        Write-Host "【回避策】XML 入力機能（.xml ファイルの処理）が必要な場合："
        Write-Host "  1. Python 公式サイトから『Windows installer (64-bit)』をインストール"
        Write-Host "     ※ 一覧に ARM64 版もあるが、そちらは選ばないこと"
        Write-Host "     https://www.python.org/downloads/release/python-31210/"
        Write-Host "     ファイル: python-3.12.10-amd64.exe（ページ表示名: Windows installer (64-bit)）"
        Write-Host "  2. コマンドプロンプトで以下を実行してインストール済み Python の一覧を確認:"
        Write-Host "     py -0p"
        Write-Host "     → パスに 'arm64' を含まない Python 3.12 の行を探す"
        Write-Host "     例: C:\Users\<ユーザー名>\AppData\Local\Programs\Python\Python312\python.exe"
        Write-Host "  3. その python.exe のフルパスで全パッケージを pip インストール:"
        Write-Host "     <上で確認したパス>\python.exe -m pip install textgrid saxonche pdfplumber Pillow"
        Write-Host "  4. 同じ python.exe で main.py を実行:"
        Write-Host "     <上で確認したパス>\python.exe main.py"
        Write-Host ""
        Write-Host "CommonMark（.md）形式の入力のみ使用する場合は saxonche 不要です。"
        Write-Host ""
        Read-Host "Enterキーを押して続けます"
    } else {
        & $pyArgs[0] @($pyArgs[1..99] + @("-m", "pip", "install", "saxonche"))
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[完了] saxonche のインストールが完了しました。"
        } else {
            Write-Host "[エラー] saxonche のインストールに失敗しました。" -ForegroundColor Red
            Write-Host "インターネット接続と Python のバージョン（3.8 以上）を確認してください。"
        }
    }

    Write-Host ""

    # --- pdfplumber / Pillow（PDF処理用）---
    Write-Host "[3/3] pdfplumber / Pillow をインストールしています..."
    & $pyArgs[0] @($pyArgs[1..99] + @("-m", "pip", "install", "pdfplumber", "Pillow"))
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[完了] pdfplumber / Pillow のインストールが完了しました。"
    } else {
        Write-Host "[エラー] pdfplumber / Pillow のインストールに失敗しました。" -ForegroundColor Red
    }
}

Write-Host ""
Ask-Continue

# ============================================================
# ステップ 9: 日本語 MFA モデルのダウンロード
# ============================================================
Write-Header "ステップ 9 / 9  :  日本語 MFA モデルのダウンロード"

Write-Host "日本語 MFA モデル（辞書・音響モデル）をダウンロードします。"
Write-Host "（ファイルサイズが大きいため、数分かかる場合があります）"
Write-Host ""

Write-Host "[1/2] 日本語辞書モデルをダウンロードしています..."
& conda run -n mfa mfa model download dictionary japanese_mfa
if ($LASTEXITCODE -ne 0) {
    Write-Host "[エラー] 日本語辞書モデルのダウンロードに失敗しました（終了コード: $LASTEXITCODE）。" -ForegroundColor Red
    Write-Host "インターネット接続と MFA 環境を確認してください。"
} else {
    Write-Host "[完了] 日本語辞書モデルのダウンロードが完了しました。"
}

Write-Host ""
Write-Host "[2/2] 日本語音響モデルをダウンロードしています..."
& conda run -n mfa mfa model download acoustic japanese_mfa
if ($LASTEXITCODE -ne 0) {
    Write-Host "[エラー] 日本語音響モデルのダウンロードに失敗しました（終了コード: $LASTEXITCODE）。" -ForegroundColor Red
    Write-Host "インターネット接続と MFA 環境を確認してください。"
} else {
    Write-Host "[完了] 日本語音響モデルのダウンロードが完了しました。"
}

Write-Host ""
Ask-Continue

# ============================================================
# 完了画面
# ============================================================
Clear-Host
Write-Host ""
Write-Host "===========================================================" -ForegroundColor Green
Write-Host "   セットアップが完了しました！" -ForegroundColor Green
Write-Host "===========================================================" -ForegroundColor Green
Write-Host ""
Write-Host "すべてのインストール手順が完了しました。"
Write-Host ""
Write-Host "【次のステップ】"
Write-Host "  1. VOICEVOX を起動する（日本語使用時）"
Write-Host "  2. KERT フォルダに移動する"
Write-Host "  3. KERT フォルダ内の start_kert.bat をダブルクリックして起動する"
Write-Host ""
Write-Host "ご不明な点は README.md または README_ja.md をご参照ください。"
Write-Host ""
Read-Host "Enterキーを押して終了"
