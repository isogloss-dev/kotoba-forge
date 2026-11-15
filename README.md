# kotoba-forge

Batch-build Japanese sentence cards for Anki. Give it a sentence and the word
you care about; it produces a deck with three furigana renderings, optional
audio, and clickable stroke-order diagrams.

This is a personal, AI-assisted project. It is tested on Windows; the Linux and
macOS code paths are implemented but have not yet been exercised by the author.

## What it does

For each CSV row:

1. the whole sentence in furigana
2. the same sentence with the target word left as kanji (no reading)
3. the same sentence with the target word written in hiragana
4. optional audio for the sentence and the word
5. [KanjiVG](https://kanjivg.tagaini.net/) stroke-order diagrams for every
   kanji in the target, on the back of the kanji card

It also writes a standalone `preview.html` with rendered ruby, audio players,
the token/reading table and any warnings, plus `errors.csv` for rows that could
not be processed. The `.apkg` is imported into Anki with *File -> Import*.

Notes use stable GUIDs derived from `sentence + target`, so rebuilding and
re-importing updates existing notes instead of duplicating them.

## Status

Tested with Anki 2.1.50+ on Windows. Linux/macOS support is implemented in the
code and setup script, but not yet tested by the author. Bug reports and patches
are welcome.

## Quick start

Requirements: Python 3.11 or newer. Anki is only needed for importing the
result.

```bash
git clone https://github.com/isogloss-dev/kotoba-forge.git
cd kotoba-forge
python scripts/setup.py
```

On Windows, `py scripts/setup.py` works too.

The setup script:

- creates `.venv` and installs the package and dependencies;
- creates `audio/words`, `audio/sentences`, `out` and `voices`;
- copies `cards.example.csv` to `cards.csv` if the latter is missing;
- downloads KanjiVG (about 12 MB, 6,703 SVGs) into `data/kanjivg/kanji/`;
- checks for a local VOICEVOX engine and prints instructions if it is absent.

Useful flags: `--no-venv`, `--no-install`, `--no-kanji`, `--force-kanji`.

Then run it with the interpreter from the virtualenv:

```bash
# Linux / macOS
.venv/bin/python run.py batch cards.csv

# Windows
.venv\Scripts\python run.py batch cards.csv
```

Or activate the environment first; `pip install -e .` also installs a
`kotoba-forge` console command.

```bash
python run.py batch cards.csv                 # build out/kotoba-forge.apkg
python run.py batch cards.csv --dry-run       # preview only, no TTS or apkg
python run.py batch cards.csv --limit 2       # first two rows only
python run.py batch cards.csv --no-audio      # ignore CSV/folder audio and TTS
python run.py batch cards.csv --tts none      # use CSV/folder audio, no TTS
python run.py one "昨日は寿司を食べた。" 食べる --sentence-meaning "I ate sushi yesterday."
python run.py voices                          # list VOICEVOX speakers
python run.py kanji-setup                     # download/refresh KanjiVG
```

Outputs:

- `out/preview.html` — the three variants, stroke diagrams and audio sources
- `out/errors.csv` — skipped rows with the reason and token list
- `out/kotoba-forge.apkg` — unless `--dry-run`

## VOICEVOX (optional)

Audio can come from files or from a local
[VOICEVOX](https://github.com/VOICEVOX/voicevox_engine/releases) engine. Download
the CPU build for your platform, extract it, and place it so the launcher is at:

```
voices/engine/run.exe     # Windows
voices/engine/run         # Linux / macOS
```

The release archives are `.7z`; `7z x` or the Windows 7-Zip GUI will extract
them. If no engine is present, the tool still uses CSV paths and files from the
audio folders; `--tts none` forces that behaviour.

VOICEVOX stores its dictionary and presets outside the project:
`%LOCALAPPDATA%\voicevox-engine` on Windows, and the platform data directory on
Linux/macOS. Normally it can create that itself. If the location is not writable
(a restricted sandbox, for example), point it at `voices/userdata` with a
directory junction on Windows:

```
cmd /c mklink /J "%LOCALAPPDATA%\voicevox-engine" "<project>\voices\userdata"
```

## CSV format

| column | required | meaning |
|---|---|---|
| `sentence` | yes | Japanese sentence, punctuation included |
| `target` | yes | dictionary form (食べる, 気に入る) or the surface |
| `sentence_meaning` | no | translation shown on the back |
| `target_meaning` | no | word meaning shown on the back |
| `target_reading` | no | override; otherwise derived from the target |
| `word_audio` | no | explicit word audio path |
| `sentence_audio` | no | explicit sentence audio path |
| `tags` | no | comma or space separated |
| `source` | no | free text |

UTF-8, with or without BOM. Paths may be absolute or relative to the project
root. `cards.csv` is gitignored; start from `cards.example.csv`.

Audio priority is the same for words and sentences:

1. the path in the CSV, if it exists
2. a file found in `audio/words/` or `audio/sentences/`
3. VOICEVOX synthesis

A missing CSV path produces a warning in `preview.html` and falls through to the
next source. Nothing writes back to the CSV.

Word files may follow Forvo naming or plain names:

```
audio/words/pronunciation_ja_食べる.mp3
audio/words/食べる.mp3
```

Sentence files are named after the sentence; trailing punctuation is ignored:

```
audio/sentences/昨日は寿司を食べた.mp3
audio/sentences/昨日は寿司を食べた。.mp3
```

A sentence file named after the target (`食べる.mp3`) is accepted as a fallback
for one-sentence-per-word setups. If several recordings exist, the unsuffixed /
shortest filename wins and the alternatives are reported in the preview.

## Furigana

Furigana follows the kanji-run convention: each maximal run of kanji gets its own
bracket, kana stays bare.

```
食べる   ->  食[た]べる
食べ物   ->  食[た]べ物[もの]
お菓子   ->  お菓子[かし]
```

Anki's `furigana` filter does not handle okurigana itself: the ruby base is
everything since the last space or `>`, and the manual marks `世[よ]の中[なか]`
as incorrect. Generated fields therefore wrap each run in an invisible `<span>`
(`<span>食[た]</span><span>べた</span>`), so each reading attaches to exactly the
kanji run without inserting visible spaces. Templates must use
`{{furigana:Field}}`; `{{Field}}` would show the brackets literally.

## Stroke order

`StrokeOrder` holds one diagram per unique kanji in the target: 食べる gives 食,
気に入る gives 気 and 入. Each kanji ships two SVGs: the plain diagram and a
colour-coded copy (`kanji_c_XXXXX.svg`) where every stroke has its own generated
colour and the number is tinted to match.

The card shows the plain version first. Click or tap a diagram to swap it for the
coloured copy; click again to return. The diagrams sit on a white tile, so they
remain readable in night mode without colour inversion. The click handler is a
small inline script at the bottom of `templates/card3_back.html`; the preview
uses the same markup.

Attribution is in the card 3 template and is required by the licence:
**KanjiVG, CC BY-SA 3.0**. The generated diagrams remain under that licence if
you share the deck. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Card 2 does not show stroke order. To add it there, put `{{StrokeOrder}}` in
`templates/card2_back.html` and copy the `<script>` block from `card3_back.html`;
without the script the plain diagram still renders, but the toggle does nothing.

## Note fields and templates

Fields: `Sentence`, `SentenceFurigana`, `SentenceTargetKanji`,
`SentenceTargetKana`, `StrokeOrder`, `Target`, `TargetReading`, `TargetMeaning`,
`SentenceMeaning`, `SentenceAudio`, `WordAudio`, `Source`, `Key`.

Three card templates are generated: *1 Furigana*, *2 Target (kanji)*,
*3 Target (hiragana)*. Audio is on the front of cards 1 and 3, and on the back of
card 2 so it does not read the answer aloud.

Templates live in `templates/`:

```
card1_front.html  card1_back.html
card2_front.html  card2_back.html
card3_front.html  card3_back.html
style.css
```

Edit them and rebuild for future packages. Once a deck is imported, Anki owns its
copy; use *Tools -> Manage Note Types -> Cards* from then on.

Notice: due to workarounds with audio auto-play, to work properly default templates require Anki auto-play to be turned off

## Project layout

```
cards.example.csv      tracked example input
cards.csv              your input (gitignored)
config.toml            deck ids, TTS, paths
audio/words/           word recordings
audio/sentences/       sentence recordings
data/kanjivg/kanji/    KanjiVG SVGs (gitignored, created by setup)
templates/             card HTML/CSS
src/jpcard/            code
tests/                 unit tests
out/                   apkg, preview, errors, media cache (gitignored)
voices/engine/         VOICEVOX (gitignored)
```

## Tests

```bash
python -m unittest discover -s tests -v
```

## Known limits

- Sudachi misreads names, slang and rare compounds. `preview.html` exists so you
  can catch that before importing.
- Arabic numerals plus counters may render as `3人[にん]` rather than one unit;
  kanji numerals (三人) come out as `三[さん]人[にん]`.
- Words written in kana in the source sentence cannot gain furigana.
- Some rare kanji have no KanjiVG diagram; they are skipped with a warning.
- Audio matching is filename-based; unusual suffixes or encoded names may not be
  found. The preview reports which source was used.
- The note-type schema is fixed. Changing fields later means a new note type and
  a migration.

## License

Code is MIT — see [LICENSE](LICENSE). KanjiVG stroke data is CC BY-SA 3.0;
VOICEVOX and its voice models have their own terms. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Built with

This project was built in a human-directed loop with **DeepSeek Harness** and its
**deepseek-flash** coding agent. The author set the requirements, reviewed each
iteration, and tested the resulting cards in Anki; the agent wrote and refactored
the implementation.
