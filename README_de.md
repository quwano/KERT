# KERT - EPUB3 & DAISY4 Support Tool

**[English](./README.md)** | **[日本語](./README_ja.md)** | **Deutsch**

![version](https://img.shields.io/github/v/release/quwano/KERT?label=version&color=brightgreen)
![license](https://img.shields.io/badge/license-GPL-green)
![platform](https://img.shields.io/badge/platform-MacOS%20Sequoia%2FTahoe%20Windows%2011-blue)

## Über dieses Projekt

KERT ist ein Werkzeug, das aus Textdateien **DAISY4/EPUB3-E-Books mit Media Overlay (Audiosynchronisierung)** erzeugt. Es ist in Python geschrieben.

Als Eingabeformate werden die **erweiterte CommonMark-Notation** (`.txt` / `.md`), das **XML-Format** (`.xml`) sowie das **PDF-Format** (`.pdf`) unterstützt.

### Verarbeitungsablauf

```
Eingabedatei (.txt / .md / .xml)
    |  Textanalyse & Erzeugung des Vorlesetextes
    |  TTS (Text-to-Speech) erzeugt WAV
    |  FFmpeg konvertiert zu MP3
    |  Montreal Forced Aligner führt Audioausrichtung durch (TextGrid-Erzeugung)
    |  XHTML + SMIL-Erzeugung & EPUB-Paketierung
EPUB3-Datei (mit Audiosynchronisierung)

PDF-Eingabe (.pdf)
    |  pdfplumber: Textextraktion + Überschriftenerkennung (3 Modi)
    |  Pillow: Bildextraktion → intermediate_products/figures/
    |  TTS → WAV → MP3 → TextGrid (MFA) → EPUB-Paketierung
EPUB3-Datei (mit Audiosynchronisierung)

PDF → Markdown-Export (ohne Audio):
    |  pdfplumber: Textextraktion
Markdown-Datei (.md) ← Mit Yomikae/Ruby-Notation ergänzen und als CommonMark neu verarbeiten
```

## Schnellinstallation

Installationsskripte für macOS und Windows befinden sich im Ordner `easy_installer/`.

Welcher Installer für Ihr Betriebssystem und Ihre Sprache geeignet ist, erfahren Sie unter **[`easy_installer/INSTALL_GUIDE.md`](./easy_installer/INSTALL_GUIDE.md)**.

Für die manuelle Installation folgen Sie den Schritten unter [Voraussetzungen](#voraussetzungen).

## Voraussetzungen

### Python

Python 3.12 oder höher ist erforderlich (aufgrund der Verwendung der Typhinweis-Syntax `X | None`).

### Conda / Montreal Forced Aligner (MFA)

[Montreal Forced Aligner (MFA)](https://montreal-forced-aligner.readthedocs.io/) wird für die Audio-Text-Ausrichtung verwendet (Analyse, welche Wörter welchen Positionen im Audio entsprechen).

#### Conda installieren

Conda wird als Laufzeitumgebung für MFA benötigt. Installieren Sie [Miniforge](https://github.com/conda-forge/miniforge) oder [Miniconda](https://docs.anaconda.com/free/miniconda/).

> **Hinweis für Windows**: KERT erkennt die conda-Programmdatei automatisch (sucht in PATH, der Umgebungsvariable `CONDA_EXE` und gängigen Installationspfaden wie `%USERPROFILE%\miniforge3`). Falls die automatische Erkennung fehlschlägt, fügen Sie das Verzeichnis `Scripts` von Conda zum System-PATH hinzu oder setzen Sie die Umgebungsvariable `CONDA_EXE` auf den vollständigen Pfad von conda.exe.

#### MFA installieren

MFA wird in einer Conda-Umgebung installiert. Der Standardname der Umgebung ist `mfa`.

```bash
# Conda-Umgebung erstellen und MFA installieren
conda create -n mfa -c conda-forge montreal-forced-aligner
conda activate mfa
```

Nach der Installation von MFA laden Sie die Wörterbuch- und akustischen Modelle für die gewünschten Sprachen herunter (siehe „[MFA-Modelle installieren](#mfa-modelle-installieren)" für Details).

> **Hinweis**: Während der KERT-Ausführung wird MFA automatisch über `conda run -n mfa` aufgerufen. Sie müssen `conda activate mfa` nicht vorher ausführen.

#### Zusätzliches Setup für Japanisch

Das japanische MFA-Modell (`japanese_mfa`) verwendet intern spacy / sudachipy. Nach der Installation von MFA installieren Sie die zusätzlichen Pakete mit den folgenden Befehlen:

```bash
conda activate mfa
pip install spacy sudachipy sudachidict_core
```

### VOICEVOX (nur Japanisch)

[VOICEVOX](https://voicevox.hiroshiba.jp/) wird für die japanische Sprachsynthese verwendet.

- Starten Sie die VOICEVOX-Engine, bevor Sie KERT ausführen.
- Die Standard-Verbindungs-URL ist `http://localhost:50021`.
- Die Standardstimme ist ID 109 (Tohoku Itako).

VOICEVOX ist nicht erforderlich, wenn Sie nur Englisch oder Deutsch verwenden.

> **Wichtig: VOICEVOX-Nutzungsbedingungen**
>
> Wenn Sie EPUBs mit von VOICEVOX erzeugtem Audio verteilen oder veröffentlichen, müssen Sie die VOICEVOX-[Nutzungsbedingungen](https://voicevox.hiroshiba.jp/term/) und die individuellen Charakter-Nutzungsbedingungen prüfen. Für einige Charaktere gelten Einschränkungen für die kommerzielle Nutzung oder es ist eine Namensnennung erforderlich. Die Standardstimme in KERT ist „Tohoku Itako" (ID 109).

### macOS say / Windows SAPI (Englisch & Deutsch)

Für die englische und deutsche Sprachsynthese wird die im Betriebssystem integrierte TTS verwendet.

- **macOS**: `say`-Befehl (Englisch: Samantha, Deutsch: Anna)
- **Windows**: Verwendet System.Speech.Synthesis (SAPI) über PowerShell. Fällt automatisch von macOS say mit denselben Spracheinstellungen zurück.

> **Hinweis für Windows**: Das Sprachpaket für die Zielsprache muss vorab installiert werden. Gehen Sie zu **Windows-Einstellungen > Zeit & Sprache > Sprache**, fügen Sie Englisch oder Deutsch hinzu und stellen Sie sicher, dass **Spracheingabe** aktiviert ist.

### FFmpeg

[FFmpeg](https://ffmpeg.org/) wird verwendet, um WAV-Dateien, die von TTS erzeugt wurden, in MP3 umzuwandeln.

```bash
# macOS (Homebrew)
brew install ffmpeg

# Windows (Chocolatey)
choco install ffmpeg
```

Stellen Sie sicher, dass der Befehl `ffmpeg` in Ihrem PATH verfügbar ist.

### pip-Pakete

```bash
pip install -r requirements.txt
```

Installierte Pakete:

| Paket | Zweck |
|-------|-------|
| `textgrid` | Lesen von TextGrid-Dateien, die von MFA erzeugt wurden |
| `saxonche` | XSLT 3.0-Prozessor |
| `pdfplumber` | PDF-Text- und Bildextraktion |
| `Pillow` | Speichern von PDF-Abbildungen als Bilddateien |

saxonche wird für die XML-Eingabekonvertierung verwendet. Bei ausschließlicher Verwendung von CommonMark- oder PDF-Eingaben ist es nicht erforderlich.
pdfplumber und Pillow werden für die PDF-Eingabe benötigt. Pillow ist nur erforderlich, wenn Abbildungen aus PDFs extrahiert werden sollen.

### Unterstützung für mathematische Formeln (Optional)

Mathematische Formeln in TeX-Notation (`$...$`, `$$...$$`) in CommonMark-Dateien und MathML (`<math>`) in XML-Dateien werden unterstützt. Die folgenden Werkzeuge sind erforderlich, um diese Funktion zu aktivieren.

| Werkzeug | Zweck | Installation |
|----------|-------|-------------|
| [pandoc](https://pandoc.org/) | TeX → MathML-Konvertierung | `brew install pandoc` / [pandoc.org](https://pandoc.org/installing.html) |
| [Node.js](https://nodejs.org/) | Laufzeit für speech-rule-engine | `brew install node` / [nodejs.org](https://nodejs.org/) |
| [speech-rule-engine](https://github.com/zorkow/speech-rule-engine) | MathML → Sprachtext | Siehe unten |

#### Unterstützte Sprachen für mathematische Sprachausgabe

Die **Anzeige** mathematischer Formeln (MathML im EPUB) funktioniert unabhängig von der Sprache. Die **Sprachausgabe** (Vorlesen von Formeln während der Wiedergabe) erfordert jedoch, dass sowohl speech-rule-engine als auch MFA die Sprache unterstützen.

Unterstützte Sprachen finden Sie auf [speechruleengine.org](https://speechruleengine.org/).

| KERT-Sprache | Formelanzeige | Formelausgabe |
|--------------|--------------|---------------|
| Japanisch (ja_JP) | ✓ | ✗ Nicht verfügbar (Stand März 2026, SRE unterstützt kein Japanisch) |
| Englisch (en_US)  | ✓ | ✓ |
| Deutsch (de_DE)   | ✓ | ✓ |

Bei japanischer Eingabe erscheinen mathematische Formeln als MathML im EPUB, werden jedoch nicht korrekt vorgelesen. Der umgebende Text wird normal verarbeitet.

#### speech-rule-engine installieren

speech-rule-engine muss lokal im **KERT-Projektstammverzeichnis** installiert werden.

> **Wichtig**: Führen Sie `npm install` aus dem **KERT-Projektstammverzeichnis** aus. Die Installation in einem anderen Verzeichnis wird von KERT nicht erkannt, obwohl npm keinen Fehler meldet.

```bash
cd /path/to/KERT   # Zum KERT-Projektstammverzeichnis wechseln
npm install speech-rule-engine
```

Wenn eines dieser Werkzeuge fehlt, wenn mathematische Formeln in der Eingabedatei erkannt werden, zeigt KERT eine Warnung an und fordert Sie auf, abzubrechen oder ohne Formelunterstützung fortzufahren.

## Mehrsprachige Unterstützung

### Unterstützte Sprachen

| Sprachcode | Sprache | TTS-Engine | MFA-Wörterbuch / Akustisches Modell |
|------------|---------|------------|-------------------------------------|
| `ja_JP` | Japanisch | VOICEVOX | `japanese_mfa` |
| `en_US` | Englisch (US) | macOS say (Samantha) / Windows SAPI | `english_us_arpa` |
| `de_DE` | Deutsch | macOS say (Anna) / Windows SAPI | `german_mfa` |

### MFA-Modelle installieren

Laden Sie die Wörterbuch- und akustischen Modelle für die Sprachen herunter, die Sie verwenden möchten.

```bash
# Japanisch
conda run -n mfa mfa model download dictionary japanese_mfa
conda run -n mfa mfa model download acoustic japanese_mfa

# Englisch (US)
conda run -n mfa mfa model download dictionary english_us_arpa
conda run -n mfa mfa model download acoustic english_us_arpa

# Deutsch
conda run -n mfa mfa model download dictionary german_mfa
conda run -n mfa mfa model download acoustic german_mfa
```

### Neue Sprachen hinzufügen

Über die drei aufgeführten Sprachen hinaus können weitere Sprachen unterstützt werden. Führen Sie dazu folgende Schritte aus:

1. **MFA-Modelle vorbereiten**: Installieren Sie die Wörterbuch- und akustischen Modelle für die Zielsprache. Verfügbare Modelle finden Sie in der [MFA-Dokumentation](https://mfa-models.readthedocs.io/).

2. **Eintrag zu `LANGUAGE_CONFIGS` in `core/config.py` hinzufügen**: Verwenden Sie folgendes Format:

```python
"fr_FR": LanguageConfig(
    code="fr_FR",
    display_name="Fran\u00e7ais",
    epub_lang="fr",
    mfa_dictionary="french_mfa",      # MFA-Wörterbuchmodellname
    mfa_acoustic="french_mfa",        # MFA-akustischer Modellname
    tts_engine="say",                  # "voicevox" oder "say"
    tts_voice="Thomas",               # macOS say-Stimmenname (bei Verwendung von say)
),
```

- `tts_engine`: Verwenden Sie `"voicevox"` für Japanisch, `"say"` für andere Sprachen. Unter Windows wird bei Angabe von `"say"` automatisch auf SAPI zurückgefallen.
- `tts_voice`: Der Stimmenname für macOS say. Führen Sie `say -v '?'` aus, um verfügbare Stimmen aufzulisten.

## Dokumente erstellen

KERT unterstützt zwei Eingabeformate: **erweiterte CommonMark-Notation** und **XML-Format**.

### Erweiterte CommonMark-Notation

Schreiben Sie in CommonMark (Markdown)-basierter Notation in Textdateien mit den Endungen `.txt` oder `.md`.

#### Überschriftenhierarchie

Verwenden Sie `#` (1 bis 5) zum Schreiben von Überschriften. Jede Überschrift wird in eine separate Seite (XHTML-Datei) innerhalb des EPUBs aufgeteilt, und die hierarchische Struktur wird im Inhaltsverzeichnis (nav.xhtml) widergespiegelt.

```markdown
# Buchtitel

Erster Absatz.

## Kapitel 1

Inhalt von Kapitel 1.

### Abschnitt 1

Inhalt von Abschnitt 1.
```

- `#` wird zum Buchtitel (h1).
- `##` und darüber hinaus werden als Kapitel und Abschnitte strukturiert.
- Dateien ohne Überschriften können ebenfalls verarbeitet werden (in diesem Fall wird der Titel aus metadata.txt verwendet).

#### Formatierungsnotation

| Notation | Beschreibung | Beispiel | EPUB-Anzeige |
|----------|-------------|---------|-------------|
| `[Wort](-lesung)` | Ruby (Furigana) | `[kanji](-reading)` | Ruby-Annotation über dem Text |
| `[Anzeigetext](+Lesung)` | Alternative Lesung | `[display](+read)` | Zeigt „display", liest „read" vor |
| `**Text**` | Fett | `**wichtig**` | **wichtig** |
| `[Text]{.underline}` | Unterstrichen | `[Hinweis]{.underline}` | <u>Hinweis</u> |
| `[Text]{.frame}` | Umrahmtes Feld | `[A]{.frame}` | Text mit Rahmen |
| `~Text~` | Tiefgestellt | `H~2~O` | H<sub>2</sub>O |
| `^Text^` | Hochgestellt | `10^3^` | 10<sup>3</sup> |
| `$Formel$` | Inline-Mathematik (TeX) | `$x^2 + y^2$` | Inline MathML |
| `$$Formel$$` | Block-Mathematik (TeX) | `$$\int_0^1 x\,dx$$` | Block-MathML (zentriert) |

- Die alternative Lesungsnotation `[Anzeige](+Lesung)` wird verwendet, wenn Anzeigetext und gesprochener Text unterschiedlich sein sollen.
- Formatierungsnotationen unterstützen Verschachtelung. Beispiel: `[**fett unterstrichen**]{.underline}`

#### Bilder einfügen

```markdown
![Alternativtext](Bilddateipfad)
```

- Platzieren Sie Bilddateien im selben Verzeichnis wie die Eingabedatei oder geben Sie einen relativen Pfad an.
- Bilder werden in das Verzeichnis `images/` innerhalb des EPUBs kopiert.
- Unterstützte Formate: SVG, PNG, JPEG, GIF, WebP

#### Tabellen

Verwenden Sie die GFM-Pipe-Tabellen-Notation (GitHub Flavored Markdown) zur Erstellung von Tabellen.

```markdown
| Spalte 1 | Spalte 2 | Spalte 3 |
| --- | --- | --- |
| Daten A | Daten B | Daten C |
| Daten D | Daten E | Daten F |
```

- Die erste Zeile wird zur Kopfzeile (`<th>`); ab der dritten Zeile folgen Datenzeilen (`<td>`).
- Die zweite Zeile (`---`) ist die Trennzeile, die die Spaltenanzahl definiert.
- **Zellenweises Hervorheben.** Kopfzellen (`<th>`) werden ebenfalls vorgelesen.
- Formatierungsnotationen (Ruby, alternative Lesung, Fett usw.) können in Zellen verwendet werden.

### XML-Format

> **XML-Editor**: XML-Dokumente lassen sich einfach mit dem dedizierten Editor **[KERT XMLEditor](https://github.com/quwano/KERT_XMLEditor)** erstellen. Er ermöglicht die schemakonforme Bearbeitung von XML über eine GUI, ohne Code direkt schreiben zu müssen.

Schreiben Sie XML-Dateien, die dem XML-Schema (`resources/document_schema.xsd`) entsprechen.

#### Grundstruktur

```xml
<?xml version="1.0" encoding="UTF-8"?>
<root>
  <title1>Buchtitel</title1>
  <p>Ein Absatz mit Fließtext.</p>
  <p>Der nächste Absatz.</p>
</root>
```

Das Wurzelelement ist `<root>`, mit Überschriftenelementen (`title1` bis `title5`) und Absatzelementen (`p`) direkt darunter.

#### Elementliste

| Element | Beschreibung | Beispiel |
|---------|-------------|---------|
| `<p>` | Absatz | `<p>Fließtext</p>` |
| `<title1>` bis `<title5>` | Überschrift (Ebene 1-5) | `<title1>Titel</title1>` |
| `<ruby yomi="Lesung">Basistext</ruby>` | Ruby | `<ruby yomi="reading">kanji</ruby>` |
| `<yomikae yomi="Lesung">Anzeige</yomikae>` | Alternative Lesung | `<yomikae yomi="read">display</yomikae>` |
| `<u>` | Unterstrichen | `<u>unterstrichener Text</u>` |
| `<g>` | Betonung (fett) | `<g>betonter Text</g>` |
| `<sub>` | Tiefgestellt | `<sub>2</sub>` |
| `<sup>` | Hochgestellt | `<sup>3</sup>` |
| `<math>` | MathML-Formel | `<math xmlns="...">...</math>` |
| `<table>` | Tabelle | `<table>...</table>` |
| `<tr>` | Zeile | `<tr>...</tr>` |
| `<th>` | Kopfzelle | `<th>Spaltenname</th>` |
| `<td>` | Datenzelle | `<td>Wert</td>` |

- Dekorationselemente können verschachtelt werden. Beispiel: `<u><g>fett unterstrichen</g></u>`

#### Bilder einfügen

```xml
<img src="foto.jpg" alt="Ein kleiner Vogel"/>
```

- Platzieren Sie Bilddateien im selben Verzeichnis wie die Eingabedatei oder geben Sie einen relativen Pfad an.
- Bilder werden in das Verzeichnis `images/` innerhalb des EPUBs kopiert.
- Unterstützte Formate: SVG, PNG, JPEG, GIF, WebP

#### Tabellen

Verwenden Sie das Element `<table>` zur Erstellung von Tabellen.

```xml
<table>
  <tr><th>Spalte 1</th><th>Spalte 2</th></tr>
  <tr><td>Daten A</td><td>Daten B</td></tr>
  <tr><td>Daten D</td><td>Daten E</td></tr>
</table>
```

- `<tr>` ist eine Zeile, `<th>` eine Kopfzelle und `<td>` eine Datenzelle.
- **Zellenweises Hervorheben.** `<th>`-Zellen werden ebenfalls vorgelesen.
- Dekorationselemente (`<ruby>`, `<u>` usw.) können in Zellen verwendet werden.

#### Überschriftenhierarchie (title1 bis title5)

Die Verwendung von `title1` bis `title5` teilt den Inhalt bei jeder Überschrift in separate Seiten innerhalb des EPUBs auf und erzeugt ein hierarchisches Inhaltsverzeichnis. Diese entsprechen CommonMarks `#` bis `#####`.

```xml
<root>
  <title1>Buchtitel</title1>
  <title2>Kapitel 1</title2>
  <p>Inhalt von Kapitel 1.</p>
  <title3>Abschnitt 1</title3>
  <p>Inhalt von Abschnitt 1.</p>
  <title2>Kapitel 2</title2>
  <p>Inhalt von Kapitel 2.</p>
</root>
```

### PDF-Format (`.pdf`)

KERT extrahiert Text und Abbildungen aus PDF-Dateien und erzeugt eine EPUB- oder Markdown-Datei.

> **Hinweis**: Nur PDFs mit eingebettetem Text werden unterstützt. Gescannte (nur-Bild-)PDFs werden nicht unterstützt.

#### Überschriften-Erkennungsmodi

Bei der PDF-Verarbeitung wählen Sie einen von drei Modi:

| Modus | Geeignet für | Erkennungsmethode |
|-------|------------|-----------------|
| **1. Layout-basiert** | Webseiten, Broschüren, gestaltete Dokumente | Schriftgröße, Farbe, Hintergrundrechtecke |
| **2. Rechtliche Sprache** | Gesetze, Verordnungen, Verträge | Muster wie 第n章、第n条 usw. |
| **3. Nummeriert / Symbol** | Berichte, Handbücher, Gliederungen | ■, 【...】, `1.`, `①`, `⑴` |

#### Konfigurationsdatei für Überschriftenmuster

`resources/pdf_heading_patterns.json` enthält die regulären Ausdrücke für jeden Erkennungsmodus. Sie können Muster durch direkte Bearbeitung dieser Datei hinzufügen oder entfernen.

#### Abbildungsextraktion

In der PDF eingebettete Bilder werden automatisch nach `intermediate_products/figures/` extrahiert und in das erzeugte EPUB eingebunden. Erfordert Pillow (`pip install Pillow`).

#### PDF → Markdown-Export

Sie können eine PDF auch als Markdown-Datei (`.md`) exportieren, ohne Audio oder EPUB zu erzeugen. Die generierte Markdown-Datei kann mit Yomikae-/Ruby-Notation ergänzt und dann als CommonMark-Eingabe neu verarbeitet werden.

---

### Metadatendatei (metadata.txt)

Eine Textdatei mit bibliografischen Informationen (Titel, Autor usw.) für das EPUB. **Der Titel ist erforderlich.**

#### Dateibenennungsregeln

- **Einzeldatei-Eingabe**: Platzieren Sie `{Eingabedateiname_ohne_Endung}_metadata.txt` im selben Verzeichnis wie die Eingabedatei.
  - Beispiel: `mybook.txt` -> `mybook_metadata.txt`
  - Beispiel: `document.xml` -> `document_metadata.txt`
- **Ordner-Eingabe**: Platzieren Sie `{Ordnername}_metadata.txt` im übergeordneten Verzeichnis des Ordners.
  - Beispiel: Ordner `chapters/` -> `chapters_metadata.txt` im übergeordneten Verzeichnis

#### Format

Eine UTF-8-kodierte Textdatei mit jeder Zeile im Format `Schlüssel: Wert`.

```
title: Buchtitel
author: Autorenname
contributor: Mitwirkender
publisher: Verlagsname
rights: (C) 2026 Autorenname
subject: Genre
```

| Schlüssel | Beschreibung | Erforderlich |
|-----------|-------------|-------------|
| `title` | Buchtitel | Erforderlich |
| `author` | Autorenname | |
| `contributor` | Mitwirkender | |
| `publisher` | Verlagsname | |
| `rights` | Rechtevermerk | |
| `subject` | Genre / Kategorie | |

#### Barrierefreiheits-Metadaten

Sie können EPUB-Barrierefreiheitsinformationen hinzufügen.
```
accessMode: textual
accessModeSufficient: textual
accessibilityFeature: index
accessibilityHazard: noFlashingHazard
accessibilityHazard: noMotionSimulationHazard
accessibilityHazard: noSoundHazard
accessibilitySummary: Keine besonderen Hinweise
```

Details finden Sie auf der [DAISY-Website](https://kb.daisy.org/publishing/docs/metadata/schema.org/index.html).

### Einzeldatei und Ordner (mehrere Dateien)

KERT unterstützt zwei Verarbeitungsmodi.

**Einzeldatei-Modus**: Erzeugt ein EPUB aus einer einzelnen Eingabedatei. Audio wird in einer einzelnen Datei zusammengefasst.

**Ordner-Modus**: Kombiniert mehrere Dateien in einem Ordner zu einem EPUB. Jede Datei wird zu einem Kapitel mit individuellen Audiodateien pro Datei.

```
chapters/
+-- 01_prologue.txt    -> chapter1.xhtml + chapter1.mp3
+-- 02_chapter1.txt    -> chapter2.xhtml + chapter2.mp3
+-- 03_chapter2.txt    -> chapter3.xhtml + chapter3.mp3
```

- Dateien werden in natürlicher Reihenfolge nach Dateinamen sortiert (numerische Teile werden als Zahlen verglichen).
- Bei CommonMark werden sowohl `.txt`- als auch `.md`-Dateien gesammelt.
- Bei XML werden `.xml`-Dateien gesammelt.
- Platzieren Sie die `_metadata.txt` für Ordner im übergeordneten Verzeichnis.

## Verwendung

### Ausführen

```bash
python main.py
```

Sie werden interaktiv aufgefordert, Folgendes auszuwählen:

1. **Sprache**: Japanisch / Englisch (US) / Deutsch
2. **Eingabeformat**: Erweiterte CommonMark-Textdatei / XML-Datei / **PDF-Datei**
3. **Verarbeitungsmodus**: Einzeldatei / Ordner (mehrere Dateien) / *(nur PDF)* Markdown erzeugen
4. **(nur PDF) Überschriften-Erkennungsmodus**: Layout-basiert / Rechtliche Sprache / Nummeriert & Symbol
5. **Eingabepfad**: Datei- oder Ordnerpfad
6. **Zwischendateien**: Ob diese behalten werden sollen

> **Tipp**: Drücken Sie **ESC** oder **Ctrl+C** an jeder Eingabeaufforderung, um den Vorgang sofort abzubrechen und zu beenden.

### Ausführungsbeispiel

Für Deutsch, CommonMark, Einzeldatei:

```
$ python main.py
==================================================
EPUB Generator
==================================================
Select language:
  1: Japanese (ja_JP)
  2: English (US) (en_US)
  3: Deutsch (de_DE)
------
Language (1-3, default: 1): 3
------
Select input format:
  1: CommonMark extended text file (.txt/.md)
  2: XML file (.xml)
------
Selection (1-2, default: 1): 1
------
Select processing mode:
  1: Generate EPUB from a single CommonMark extended file
  2: Generate EPUB from multiple CommonMark extended files in a folder
------
Selection (1-2, default: 1): 1
------
Specify the path to the CommonMark extended file (.txt/.md)
/path/to/mybook.txt
------
Keep intermediate files (META-INF, OEBPS, audio.*)?
  1: Do not keep (default)
  2: Keep
------
Selection (1-2, default: 1): 1
```

### Ausgabedateien

Die erzeugte EPUB-Datei wird im selben Verzeichnis wie die Eingabedatei ausgegeben.

Dateinamenformat: `{Eingabedateiname}_{Modusnummer}_{Zeitstempel}.epub`

- Modusnummer: Eine Verkettung der ausgewählten Sprach-, Format- und Verarbeitungsmodusnummern (z. B. `311`)
- Zeitstempel: Format `YYYYMMDDHHmmss`

Beispiel: `mybook_311_20250219143000.epub`

### Zwischendateien

Wenn Sie „Zwischendateien behalten" wählen, werden folgende Dateien im Verzeichnis `intermediate_products/` gespeichert.

**Einzeldatei-Modus**:

| Datei | Inhalt |
|-------|--------|
| `audio.txt` | Vorlesetext, der an TTS übergeben wird |
| `audio.wav` | Von TTS erzeugtes WAV-Audio |
| `audio.mp3` | Von FFmpeg konvertiertes MP3-Audio |
| `audio.TextGrid` | Von MFA erzeugte Ausrichtungsinformationen |
| `META-INF/` | EPUB-Containerinformationen |
| `OEBPS/` | EPUB-Inhalt (XHTML, SMIL, CSS usw.) |

**Ordner-Modus**:

| Datei | Inhalt |
|-------|--------|
| `work_multi/audio/` | MP3-Audio für jedes Kapitel |
| `work_multi/textgrid/` | TextGrid für jedes Kapitel |
| `META-INF/` | EPUB-Containerinformationen |
| `OEBPS/` | EPUB-Inhalt |

Sie können Formatierungskonvertierungsergebnisse und Span-Aufteilung durch Prüfen der XHTML-Zwischendateien debuggen.

## Anpassung

### Lesekarte für Zeichen (`resources/reading_map.json`)

Definiert, wie Sonderzeichen für TTS/MFA-Audioausrichtung konvertiert werden. Die integrierte Karte enthält Kreiszahlen (①②…), römische Ziffern (Ⅰ Ⅱ…) und gängige Klammern. Durch Bearbeitung von `resources/reading_map.json` können Einträge hinzugefügt oder überschrieben werden:

```json
{
  "〔": "",
  "〕": "",
  "①": "いち"
}
```

`""` bedeutet, das Zeichen aus dem Vorlesetext zu entfernen (nützlich für Zeichen, die MFA nicht verarbeiten kann). Ein Zeichenkettenwert überschreibt die eingebaute Lesung.

### PDF-Überschriftenmuster (`resources/pdf_heading_patterns.json`)

Definiert reguläre Ausdrücke für jeden PDF-Überschriften-Erkennungsmodus. Bearbeiten Sie diese Datei, um Muster je nach Dokumenttyp anzupassen. Die Schwellenwerte des Layout-Modus (Schriftgrößenverhältnis, Score-Grenzen) sind ebenfalls konfigurierbar.

## Erzeugte EPUB-Struktur

Die interne Struktur des erzeugten EPUB3 ist wie folgt.

**Einzeldatei-Eingabe (mit Überschriften)**:

```
book.epub
+-- mimetype
+-- META-INF/
|   +-- container.xml
+-- OEBPS/
    +-- content.opf          <- Paketdokument
    +-- text/
    |   +-- nav.xhtml        <- Hierarchisches Inhaltsverzeichnis
    |   +-- chapter1.xhtml   <- # Überschrift 1
    |   +-- chapter2.xhtml   <- ## Überschrift 2
    |   +-- ...
    +-- smil/
    |   +-- chapter1.smil    <- Audiosynchronisierungsinfo
    |   +-- chapter2.smil
    |   +-- ...
    +-- audio/
    |   +-- audio.mp3        <- Einzelne Audiodatei
    +-- styles/
        +-- style.css        <- CSS für Hervorhebungsanzeige
```

**Ordner-Eingabe**:

```
book.epub
+-- mimetype
+-- META-INF/
|   +-- container.xml
+-- OEBPS/
    +-- content.opf
    +-- text/
    |   +-- nav.xhtml
    |   +-- chapter1.xhtml   <- Datei 1
    |   +-- chapter2.xhtml   <- Datei 2
    |   +-- ...
    +-- smil/
    |   +-- chapter1.smil
    |   +-- chapter2.smil
    |   +-- ...
    +-- audio/
    |   +-- chapter1.mp3     <- Audio für Datei 1
    |   +-- chapter2.mp3     <- Audio für Datei 2
    |   +-- ...
    +-- styles/
        +-- style.css
```

Während der Wiedergabe wird hervorgehobener Text mit gelbem Hintergrund über die CSS-Klasse `.-epub-media-overlay-active` angezeigt.

Um die Hervorhebungsfarbe zu ändern, bearbeiten Sie die Werte `background-color` und `color` in `CSS_CONTENT` in `epub/packaging.py`.

### Getestete Umgebungen

Die von diesem Werkzeug erzeugten EPUB3-Dateien wurden in folgenden Umgebungen getestet:

- **Anzeige & Media Overlay-Wiedergabe**: [Thorium Reader](https://thorium.edrlab.org/)
- **EPUB3-Konformitätsprüfung**: [Ace by DAISY](https://daisy.github.io/ace/)

## Enthaltene Werkzeuge

Das Verzeichnis `tools/` enthält eigenständige Werkzeuge zur Vorbereitung von Eingabedateien.

### split_commonmark — CommonMark-Dateiaufteilung

Teilt eine lange CommonMark-Datei nach Überschriften in mehrere Dateien auf. Nützlich als Vorverarbeitungsschritt für die Ordner-Modus-Verarbeitung.

```bash
python tools/split_commonmark.py
```

- Abschnitte, die mit `#` (h1) beginnen, werden nach `{Originaldateiname}_0{Endung}` ausgegeben
- Abschnitte, die mit `##` (h2) beginnen, werden nach `{Originaldateiname}_1{Endung}`, `{Originaldateiname}_2{Endung}`, ... ausgegeben

### unwrap_lines — Zeilenverbinder

Ersetzt Zeilenumbrüche innerhalb von Absätzen durch Leerzeichen. Nützlich für die Vorverarbeitung von Dateien, bei denen Absätze über Zeilen gebrochen werden, wie bei englischen Texten.

```bash
python tools/unwrap_lines.py
```

- Erkennt Leerzeilen als Absatztrennzeichen und konvertiert Zeilenumbrüche innerhalb von Absätzen in Leerzeichen.
- Die Ausgabedatei hat `_` an den Originaldateinamen angehängt (z. B. `input.txt` -> `input_.txt`).

### KERT XMLEditor — XML-Dokumenteditor

Ein dedizierter Editor zum Erstellen und Bearbeiten von KERT-XML-Dateien (`.xml`) über eine GUI. Schemakonforme Dokumente lassen sich erstellen, ohne XML-Code direkt schreiben zu müssen.

- **Repository**: [https://github.com/quwano/KERT_XMLEditor](https://github.com/quwano/KERT_XMLEditor)

## Danksagungen

Ich danke folgender Person aufrichtig für das Testen und das wertvolle Feedback während der Entwicklung dieses Werkzeugs:

**Tsubasa Miyazaki** - Manuelle Überprüfung und Windows-Tests

## Autor
Kazuyuki Kuwano

## Lizenz- und Rechtsinformationen

Siehe [LICENSE_de.md](LICENSE_de.md).
