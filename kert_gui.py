"""
KERT GUI — tkinter フロントエンド。
main.py の対話的CUIをGUIフォームに置き換え、処理はバックグラウンドスレッドで実行する。
"""
import logging
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

from core.config import LANGUAGE_CONFIGS, get_language_config
from core.messages import msg
from main import (
    InputFormat,
    ProcessingMode,
    _check_voicevox_running,
    _detect_math_in_source,
    process_commonmark_file,
    process_commonmark_folder,
    process_folder,
    process_pdf_to_epub,
    process_pdf_to_md,
    process_single_file,
)

# ハイライトモードは常に句読点単位で固定（CUIと同仕様）
_HIGHLIGHT_MODE = "punctuation"

# PDF見出しモード
_PDF_HEADING_MODES = [
    ("layout",  "レイアウト重視"),
    ("legal",   "法令文言"),
    ("number",  "番号記号"),
]


# =============================================================================
# ログハンドラ
# =============================================================================

class _QueueLogHandler(logging.Handler):
    """logging メッセージを queue.Queue に書き込む Handler。"""
    def __init__(self, q: queue.Queue) -> None:
        super().__init__()
        self._q = q

    def emit(self, record: logging.LogRecord) -> None:
        self._q.put(self.format(record))


# =============================================================================
# GUI アプリケーション
# =============================================================================

class KertApp:
    def __init__(self, root: tk.Tk) -> None:
        self._root = root
        root.title("KERT - EPUB3 & DAISY4 Support Tool")
        root.resizable(True, True)

        self._log_queue: queue.Queue[str] = queue.Queue()
        self._result_queue: queue.Queue[tuple[bool, str]] = queue.Queue()

        # logging ハンドラ追加
        self._log_handler = _QueueLogHandler(self._log_queue)
        self._log_handler.setFormatter(logging.Formatter("%(message)s"))
        logging.getLogger("KERT").addHandler(self._log_handler)

        self._build_ui()
        self._update_form()  # 初期表示状態を整える

    # ------------------------------------------------------------------
    # UI 構築
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 8, "pady": 4}

        # ── 言語 ──
        lang_frame = ttk.LabelFrame(self._root, text="言語 / Language")
        lang_frame.grid(row=0, column=0, sticky="ew", **pad)

        self._lang_var = tk.StringVar(value="ja_JP")
        for col, (code, cfg) in enumerate(LANGUAGE_CONFIGS.items()):
            ttk.Radiobutton(
                lang_frame, text=cfg.display_name,
                variable=self._lang_var, value=code,
            ).grid(row=0, column=col, padx=6, pady=2)

        # ── 入力形式 ──
        fmt_frame = ttk.LabelFrame(self._root, text="入力形式 / Input Format")
        fmt_frame.grid(row=1, column=0, sticky="ew", **pad)

        self._fmt_var = tk.StringVar(value=InputFormat.COMMONMARK_EXT.value)
        fmt_options = [
            (InputFormat.COMMONMARK_EXT, "CommonMark (.txt/.md)"),
            (InputFormat.XML,            "XML"),
            (InputFormat.PDF,            "PDF"),
        ]
        for col, (fmt, label) in enumerate(fmt_options):
            ttk.Radiobutton(
                fmt_frame, text=label,
                variable=self._fmt_var, value=fmt.value,
                command=self._update_form,
            ).grid(row=0, column=col, padx=6, pady=2)

        # ── 処理モード ──
        mode_frame = ttk.LabelFrame(self._root, text="処理モード / Processing Mode")
        mode_frame.grid(row=2, column=0, sticky="ew", **pad)

        self._mode_var = tk.StringVar(value=ProcessingMode.SINGLE_FILE.value)
        self._opt_single = ttk.Radiobutton(
            mode_frame, text="単一ファイル",
            variable=self._mode_var, value=ProcessingMode.SINGLE_FILE.value,
            command=self._update_form,
        )
        self._opt_single.grid(row=0, column=0, padx=6, pady=2)

        self._opt_folder = ttk.Radiobutton(
            mode_frame, text="フォルダ",
            variable=self._mode_var, value=ProcessingMode.FOLDER.value,
            command=self._update_form,
        )
        self._opt_folder.grid(row=0, column=1, padx=6, pady=2)

        self._opt_pdf_md = ttk.Radiobutton(
            mode_frame, text="PDF → MD 変換のみ",
            variable=self._mode_var, value=ProcessingMode.PDF_TO_MD.value,
            command=self._update_form,
        )
        self._opt_pdf_md.grid(row=0, column=2, padx=6, pady=2)

        # ── PDF 見出し検出（PDF 選択時のみ表示）──
        self._pdf_heading_frame = ttk.LabelFrame(self._root, text="PDF 見出し検出 / Heading Detection")
        self._pdf_heading_var = tk.StringVar(value="legal")
        for col, (val, label) in enumerate(_PDF_HEADING_MODES):
            ttk.Radiobutton(
                self._pdf_heading_frame, text=label,
                variable=self._pdf_heading_var, value=val,
            ).grid(row=0, column=col, padx=6, pady=2)

        # ── パス入力 ──
        path_frame = ttk.Frame(self._root)
        path_frame.grid(row=4, column=0, sticky="ew", **pad)
        path_frame.columnconfigure(1, weight=1)

        ttk.Label(path_frame, text="パス / Path:").grid(row=0, column=0, sticky="w")
        self._path_var = tk.StringVar()
        self._path_entry = ttk.Entry(path_frame, textvariable=self._path_var, width=50)
        self._path_entry.grid(row=0, column=1, sticky="ew", padx=(4, 4))
        self._path_entry.drop_target_register(DND_FILES)
        self._path_entry.dnd_bind("<<Drop>>", self._on_drop)
        self._browse_btn = ttk.Button(path_frame, text="参照... / Browse...", command=self._browse)
        self._browse_btn.grid(row=0, column=2)

        # ── 中間ファイル保持 ──
        self._keep_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self._root, text="中間ファイルを残す / Keep intermediate files",
            variable=self._keep_var,
        ).grid(row=5, column=0, sticky="w", **pad)

        # ── 実行ボタン ──
        self._run_btn = ttk.Button(self._root, text="実行 / Run", command=self._on_run)
        self._run_btn.grid(row=6, column=0, pady=8)

        # ── ログ出力 ──
        log_frame = ttk.LabelFrame(self._root, text="ログ出力 / Log")
        log_frame.grid(row=7, column=0, sticky="nsew", padx=8, pady=4)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self._log_text = tk.Text(log_frame, state="disabled", height=15, wrap="word")
        self._log_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(log_frame, command=self._log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._log_text.config(yscrollcommand=scrollbar.set)

        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(7, weight=1)

        # ウィンドウ全面をドロップターゲットに登録
        self._root.drop_target_register(DND_FILES)
        self._root.dnd_bind("<<Drop>>", self._on_drop)

    # ------------------------------------------------------------------
    # フォーム状態更新
    # ------------------------------------------------------------------

    def _update_form(self) -> None:
        fmt = self._current_input_format()
        mode = self._mode_var.get()

        if fmt == InputFormat.PDF:
            # PDF では単一ファイル or PDF_TO_MD のみ（フォルダ不可）
            self._opt_folder.config(state="disabled")
            if mode == ProcessingMode.FOLDER.value:
                self._mode_var.set(ProcessingMode.SINGLE_FILE.value)
            self._opt_pdf_md.config(state="normal")
            # PDF 見出し検出フレームを表示
            self._pdf_heading_frame.grid(row=3, column=0, sticky="ew", padx=8, pady=4)
        else:
            self._opt_folder.config(state="normal")
            self._opt_pdf_md.config(state="disabled")
            if mode == ProcessingMode.PDF_TO_MD.value:
                self._mode_var.set(ProcessingMode.SINGLE_FILE.value)
            self._pdf_heading_frame.grid_remove()

    # ------------------------------------------------------------------
    # ドロップ
    # ------------------------------------------------------------------

    def _on_drop(self, event) -> None:
        # TkinterDnD はスペース区切りで複数パスを返す。複数の場合は先頭のみ使用。
        raw = event.data.strip()
        # 波括弧で囲まれたパス（スペース含む macOS パス）を展開する
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        else:
            # 複数ドロップの場合は最初のパスだけ取る
            raw = raw.split("} {")[0].lstrip("{")
        self._path_var.set(raw)
        # ドロップされたパスがフォルダかファイルかで処理モードを自動切替
        p = Path(raw)
        if p.is_dir():
            fmt = self._current_input_format()
            if fmt != InputFormat.PDF:
                self._mode_var.set(ProcessingMode.FOLDER.value)
        else:
            self._mode_var.set(ProcessingMode.SINGLE_FILE.value)
            # ファイル拡張子から入力形式を自動推定
            ext = p.suffix.lower()
            if ext == ".pdf":
                self._fmt_var.set(InputFormat.PDF.value)
            elif ext == ".xml":
                self._fmt_var.set(InputFormat.XML.value)
            elif ext in (".txt", ".md"):
                self._fmt_var.set(InputFormat.COMMONMARK_EXT.value)
        self._update_form()

    # ------------------------------------------------------------------
    # ファイル/フォルダ参照
    # ------------------------------------------------------------------

    def _browse(self) -> None:
        fmt = self._current_input_format()
        mode = self._mode_var.get()

        if mode == ProcessingMode.FOLDER.value:
            path = filedialog.askdirectory(title="フォルダを選択")
        else:
            ext_map = {
                InputFormat.COMMONMARK_EXT: [("Text/Markdown", "*.txt *.md"), ("All", "*.*")],
                InputFormat.XML:            [("XML", "*.xml"), ("All", "*.*")],
                InputFormat.PDF:            [("PDF", "*.pdf"), ("All", "*.*")],
            }
            filetypes = ext_map.get(fmt, [("All", "*.*")])
            path = filedialog.askopenfilename(title="ファイルを選択", filetypes=filetypes)

        if path:
            self._path_var.set(path)

    # ------------------------------------------------------------------
    # 実行ハンドラ（メインスレッド）
    # ------------------------------------------------------------------

    def _on_run(self) -> None:
        source = self._path_var.get().strip().strip('"').strip("'")
        if not source:
            messagebox.showwarning("入力エラー", "パスを入力してください。")
            return

        lang_config = get_language_config(self._lang_var.get())
        fmt = self._current_input_format()
        mode = self._mode_var.get()
        keep = self._keep_var.get()
        heading_mode = self._pdf_heading_var.get()

        # VOICEVOX チェック（ja_JP のみ）
        if lang_config.tts_engine == "voicevox":
            if not _check_voicevox_running():
                if not messagebox.askyesno(
                    "VOICEVOX 未起動",
                    "VOICEVOX が起動していません。\n起動後に再実行してください。\n\nこのまま続行しますか？",
                ):
                    return

        # 数式ツールチェック（PDF 以外）
        if fmt != InputFormat.PDF:
            is_folder = mode == ProcessingMode.FOLDER.value
            if _detect_math_in_source(source, fmt, is_folder):
                from mathconv.converter import check_math_tools
                tools = check_math_tools()
                missing = [n for n, ok in tools.items() if not ok]
                if missing:
                    name_map = {"pandoc": "pandoc", "node": "Node.js", "sre": "speech-rule-engine (npm)"}
                    missing_str = "\n".join(f"  - {name_map[n]}" for n in missing)
                    if not messagebox.askyesno(
                        "数式ツール不足",
                        f"数式が検出されましたが、以下のツールが見つかりません:\n{missing_str}\n\n"
                        "数式が正しく変換されない場合があります。続行しますか？",
                    ):
                        return

        # ログエリアをクリアして実行開始
        self._log_clear()
        self._set_running(True)

        mode_string = f"{self._lang_var.get()}_{fmt.value}_{mode}"

        threading.Thread(
            target=self._run_pipeline,
            args=(source, lang_config, fmt, mode, keep, heading_mode, mode_string),
            daemon=True,
        ).start()

        self._root.after(100, self._poll_queues)

    # ------------------------------------------------------------------
    # バックグラウンドスレッド
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        source: str,
        lang_config,
        fmt: InputFormat,
        mode: str,
        keep: bool,
        heading_mode: str,
        mode_string: str,
    ) -> None:
        try:
            # 数式サポート初期化（PDF 以外）
            if fmt != InputFormat.PDF:
                from mathconv.converter import init_math_support
                init_math_support(lang_config.code)

            if fmt == InputFormat.PDF:
                if mode == ProcessingMode.PDF_TO_MD.value:
                    process_pdf_to_md(source, heading_mode=heading_mode)
                else:
                    process_pdf_to_epub(
                        source, _HIGHLIGHT_MODE, lang_config, keep,
                        mode_string=mode_string, heading_mode=heading_mode,
                    )
            elif fmt == InputFormat.COMMONMARK_EXT:
                if mode == ProcessingMode.FOLDER.value:
                    process_commonmark_folder(source, _HIGHLIGHT_MODE, lang_config, keep, mode_string=mode_string)
                else:
                    process_commonmark_file(source, _HIGHLIGHT_MODE, lang_config, keep, mode_string=mode_string)
            else:  # XML
                if mode == ProcessingMode.FOLDER.value:
                    process_folder(source, _HIGHLIGHT_MODE, is_xml=True, lang_config=lang_config,
                                   keep_intermediate=keep, mode_string=mode_string)
                else:
                    process_single_file(source, _HIGHLIGHT_MODE, is_xml=True, lang_config=lang_config,
                                        keep_intermediate=keep, mode_string=mode_string)

            self._result_queue.put((True, "処理が完了しました。"))
        except Exception as exc:
            self._result_queue.put((False, str(exc)))

    # ------------------------------------------------------------------
    # ポーリング（メインスレッド）
    # ------------------------------------------------------------------

    def _poll_queues(self) -> None:
        # ログを Text ウィジェットに追記
        while True:
            try:
                line = self._log_queue.get_nowait()
                self._log_append(line)
            except queue.Empty:
                break

        # 処理完了チェック
        try:
            success, message = self._result_queue.get_nowait()
            self._set_running(False)
            if success:
                messagebox.showinfo("完了", message)
            else:
                messagebox.showerror("エラー", message)
            return
        except queue.Empty:
            pass

        self._root.after(100, self._poll_queues)

    # ------------------------------------------------------------------
    # ヘルパー
    # ------------------------------------------------------------------

    def _current_input_format(self) -> InputFormat:
        return InputFormat(self._fmt_var.get())

    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self._run_btn.config(state=state)
        self._browse_btn.config(state=state)

    def _log_clear(self) -> None:
        self._log_text.config(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.config(state="disabled")

    def _log_append(self, text: str) -> None:
        self._log_text.config(state="normal")
        self._log_text.insert("end", text + "\n")
        self._log_text.see("end")
        self._log_text.config(state="disabled")


# =============================================================================
# エントリポイント
# =============================================================================

def main() -> None:
    root = TkinterDnD.Tk()
    KertApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
