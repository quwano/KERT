# KERT インストールガイド / Installer Guide / Installationsanleitung

---

KERTが利用する他のアプリやツール類のインストールを簡単に行うことができるファイルを用意しています。

We provide installer files that make it easy to install the applications and tools required by KERT.

Wir stellen Installationsdateien bereit, mit denen Sie die von KERT benötigten Anwendungen und Tools einfach installieren können.

## 1. フォルダの選び方 / Choose Your Folder / Ordner wählen

| OS      | 言語 / Language / Sprache | フォルダ / Folder / Verzeichnis |
|---------|--------------------------|--------------------------------|
| macOS   | 日本語                    | `mac_ja/`                      |
| macOS   | English                  | `mac_en/`                      |
| macOS   | Deutsch                  | `mac_de/`                      |
| Windows | 日本語                    | `win_ja/`                      |
| Windows | English                  | `win_en/`                      |
| Windows | Deutsch                  | `win_de/`                      |

---

## 2. macOS — ファイルの選び方 / Which file to use / Welche Datei verwenden

各フォルダには `.command` ファイルが2つあります。

Each folder contains two `.command` files.

Jeder Ordner enthält zwei `.command`-Dateien.

| ファイル / File / Datei | 使う場面 / When to use / Wann verwenden |
|---|---|
| `kert_mac_installer_brew_*.command`    | Homebrew がインストール済みの場合 / Homebrew is already installed / Homebrew ist bereits installiert |
| `kert_mac_installer_no_brew_*.command` | Homebrew を使わない場合 / Without Homebrew / Ohne Homebrew |

**実行方法 / How to run / Ausführen:**

`.command` ファイルをダブルクリックしてください。

Double-click the `.command` file.

Doppelklicken Sie auf die `.command`-Datei.

> **初回起動時 / First run / Erster Start:**
>
> macOS のセキュリティ警告が表示される場合は、ファイルを右クリック →「開く」を選択してください。
>
> If macOS shows a security warning, right-click the file and choose **Open**.
>
> Falls macOS eine Sicherheitswarnung anzeigt, klicken Sie mit der rechten Maustaste auf die Datei und wählen Sie **Öffnen**.

---

## 3. Windows — ファイルの選び方 / Which file to use / Welche Datei verwenden

各フォルダには `.bat` ファイルと `.ps1` ファイルがあります。

Each folder contains a `.bat` file and a `.ps1` file.

Jeder Ordner enthält eine `.bat`-Datei und eine `.ps1`-Datei.

**`.bat` ファイルをダブルクリックして実行してください。**

**Double-click the `.bat` file to start.**

**Doppelklicken Sie auf die `.bat`-Datei, um zu starten.**

`.ps1` ファイルは自動的に呼び出されます。直接実行する必要はありません。

The `.ps1` file is called automatically — you do not need to run it directly.

Die `.ps1`-Datei wird automatisch aufgerufen — Sie müssen sie nicht direkt ausführen.
