"""
入力ソース（CommonMark拡張テキストファイル/XMLファイル）を抽象化するアダプターモジュール。

入力形式に依存しない統一的なインターフェースを提供します。
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from text.common import create_reading_file, strip_formatting_for_display
from parsers.xml_converter import convert_xml_to_audio_txt, get_sections_from_xml

if TYPE_CHECKING:
    from parsers.commonmark import Section, HeadingInfo
    from parsers.xml_converter import XmlSection


class SourceAdapter(ABC):
    """入力ソースの抽象基底クラス。"""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self._title: str | None = None
        self._title_xhtml: str | None = None
        self._paragraphs: list[str] | None = None
        self._load()

    @property
    def is_xml(self) -> bool:
        """XMLファイルかどうか。"""
        return False

    @abstractmethod
    def _load(self) -> None:
        """ソースを読み込む。サブクラスで実装必須。"""
        pass

    @abstractmethod
    def generate_reading_text(self, output_path: str) -> None:
        """読み上げ用テキストファイルを生成する。"""
        pass

    @abstractmethod
    def get_body_paragraphs(self) -> list[str]:
        """タイトル行を除いた本文段落を取得する（複数ファイル処理用）。"""
        pass

    @property
    def is_commonmark(self) -> bool:
        """CommonMark拡張ファイルかどうか。"""
        return False

    @staticmethod
    def create(
        file_path: str,
        is_xml: bool = False
    ) -> "SourceAdapter":
        """
        ファイルパスとフラグから適切なアダプターを生成する。

        Parameters
        ----------
        file_path : str
            入力ファイルのパス。
        is_xml : bool
            XMLファイルの場合True。

        Returns
        -------
        SourceAdapter
            適切なアダプターインスタンス。
        """
        if is_xml:
            return XMLSourceAdapter(file_path)
        else:
            return CommonMarkSourceAdapter(file_path)

    def get_title(self) -> str:
        """タイトルを取得する（プレーンテキスト、目次用）。"""
        return self._title or ""

    def get_title_xhtml(self) -> str:
        """タイトルをXHTML形式で取得する（h1内容用）。"""
        return self._title_xhtml or ""

    def get_paragraphs(self) -> list[str]:
        """本文段落を取得する（XHTML形式）。"""
        return self._paragraphs or []


class XMLSourceAdapter(SourceAdapter):
    """XMLファイル用アダプター。"""

    def __init__(self, file_path: str):
        self._sections: list["XmlSection"] = []
        super().__init__(file_path)

    @property
    def is_xml(self) -> bool:
        return True

    def _load(self) -> None:
        """XMLをパースする。"""
        self._sections = get_sections_from_xml(self.file_path)

        if self._sections:
            # 最初のセクションのtitleを使用
            self._title = self._sections[0].title_text
            self._title_xhtml = self._sections[0].title_xhtml or self._sections[0].title_text
            # 全paragraphsフラット化（音声生成用）
            all_paras: list[str] = []
            for sec in self._sections:
                all_paras.extend(sec.paragraphs_xhtml)
            self._paragraphs = all_paras

    def generate_reading_text(self, output_path: str) -> None:
        """XMLからXSLT変換で読み上げテキストを生成する。"""
        convert_xml_to_audio_txt(self.file_path, output_path)

    def get_body_paragraphs(self) -> list[str]:
        """XMLの場合はget_paragraphs()と同じ（タイトルは別途取得されている）。"""
        return self.get_paragraphs()

    def get_sections(self) -> list["XmlSection"]:
        """セクションリストを取得する。"""
        return self._sections

    def has_multiple_sections(self) -> bool:
        """複数セクションがあるかどうか。"""
        return len(self._sections) > 1


class CommonMarkSourceAdapter(SourceAdapter):
    """CommonMark拡張ファイル用アダプター。

    見出し（#〜#####）で分割された複数セクションを持つ
    単一ファイルを処理します。見出しがない場合は1行目を
    タイトルとして扱います。
    """

    def __init__(self, file_path: str):
        self._sections: list["Section"] = []
        self._root_heading: "HeadingInfo | None" = None
        self._no_headings: bool = False
        self._all_lines: list[str] = []
        super().__init__(file_path)

    def has_headings(self) -> bool:
        """見出しがあるかどうかを返す。"""
        return not self._no_headings

    @property
    def is_commonmark(self) -> bool:
        return True

    def _load(self) -> None:
        """CommonMark拡張ファイルをパースする。"""
        from parsers.commonmark import parse_commonmark, split_into_sections

        self._root_heading, self._all_lines = parse_commonmark(self.file_path)

        if self._root_heading:
            # 見出しがある場合: 見出しで分割
            self._sections = split_into_sections(self._root_heading)
            self._title = self._root_heading.title
            self._title_xhtml = self._root_heading.title_xhtml

            # _paragraphs は全セクションの全段落（音声生成時に使用）
            all_paragraphs: list[str] = []
            for section in self._sections:
                # 見出しも段落として追加（読み上げ用）
                all_paragraphs.append(section.heading.title)
                all_paragraphs.extend(section.paragraphs)
            self._paragraphs = all_paragraphs
        else:
            # 見出しがない場合: 1行目をタイトルとして扱う
            paragraphs = [line for line in self._all_lines if line.strip()]
            self._paragraphs = paragraphs
            self._no_headings = True

            # 1行目をタイトルとして使用
            if paragraphs:
                self._title = strip_formatting_for_display(paragraphs[0])
                self._title_xhtml = paragraphs[0]
            else:
                self._title = ""
                self._title_xhtml = ""

    def generate_reading_text(self, output_path: str) -> None:
        """TTS用読み上げテキストを生成する。"""
        if self._no_headings:
            # 見出しがない場合: 従来のcreate_reading_fileを使用
            create_reading_file(self.file_path, output_path)
        else:
            # 見出しがある場合: セクションから生成
            from parsers.commonmark import generate_reading_text
            reading_text = generate_reading_text(self._sections)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(reading_text)

    def get_body_paragraphs(self) -> list[str]:
        """タイトルを除いた本文段落を返す。"""
        if self._no_headings:
            # 見出しがない場合: 1行目を除いた残りを返す
            if self._paragraphs and len(self._paragraphs) > 1:
                return self._paragraphs[1:]
            return []

        if not self._sections:
            return []

        # 見出しがある場合: 最初のセクションの見出しを除き、残りの段落をすべて返す
        body_paragraphs: list[str] = []
        for i, section in enumerate(self._sections):
            if i == 0:
                # 最初のセクションは本文のみ（見出しはタイトルとして別途使用）
                body_paragraphs.extend(section.paragraphs)
            else:
                # 2番目以降は見出しも含める
                body_paragraphs.append(section.heading.title)
                body_paragraphs.extend(section.paragraphs)
        return body_paragraphs

    def get_sections(self) -> list["Section"]:
        """セクションリストを取得する。"""
        return self._sections

    def get_heading_hierarchy(self) -> "HeadingInfo | None":
        """見出し階層のルートを取得する（nav生成用）。"""
        return self._root_heading
