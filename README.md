# kotoba-forge

Batch-build Japanese sentence cards for Anki. Give it a sentence and the word
you care about; it produces a deck with three furigana renderings, optional
audio, and clickable stroke-order diagrams.

This is a personal, AI-assisted project. It is tested on Windows and Linux;
the macOS code path is implemented but has not yet been exercised by the author.
Bug reports and patches are welcome.

## The main idea

The point is to target meaning, reading and writing for each word in context,
and to help automate this a bit. You provide a list of words and sentences as
examples of those words in context, and the script generates an Anki package
with 3 card types:

1. A card focused on the meaning of the word. The whole sentence is provided
   with furigana and [optional] audio for context.
2. A card focused on the reading of the word. The target word is left as pure
   kanji in the example sentence.
3. A card focused on the writing of the word. In the example sentence the
   target word is written in hiragana, and the audio is also present. The back
   of the card has a kanji stroke-order diagram.

Notice: due to the audio auto-play workaround, the default templates require
Anki auto-play to be turned off.

## What it does

For each CSV row:

1. the whole sentence in furigana
2. the same sentence with the target word left as kanji (no reading)
3. the same sentence with the target word written in hiragana
4. optional audio for the sentence and the word
5. [KanjiVG](https://kanjivg.tagaini.net/) stroke-order diagrams for every
   kanji in the target, on the back of the writing card

It also writes a standalone `preview.html` with rendered ruby, audio players,
the token/reading table and any warnings, plus `errors.csv` for rows that could
not be processed. The `.apkg` is imported into Anki with *File -> Import*.

Notes use stable GUIDs derived from `sentence + target`, so rebuilding and
re-importing updates existing notes instead of duplicating them.

## Quick start

Requirements: Python 3.11 or newer. Anki is only needed for importing the
result.

```bash
git clone https://github.com/isogloss-dev/kotoba-forge.git
cd kotoba-forge
python scripts/setup.py        # Python command according to your OS
```

The setup script:

- creates `.venv` and installs the package and dependencies;
- creates `audio/words`, `audio/sentences`, `out`, `voices/engine` and
  `voices/userdata`;
- copies `cards.example.csv` to `cards.csv` if the latter is missing;
- downloads KanjiVG (about 12 MB, 6,703 SVGs) into `data/kanjivg/kanji/`;
- checks for a local VOICEVOX engine and prints instructions if it is absent.

Useful setup flags:

- `--no-venv` — use the interpreter running the script instead of creating or
  reusing `.venv`.
- `--no-install` — skip `pip install -e .`; the folders, `cards.csv` and
  KanjiVG are still prepared.
- `--no-kanji` — skip the KanjiVG download; stroke order stays empty until
  `run.py kanji-setup` runs.
- `--force-kanji` — re-download KanjiVG even if the archive is already there
  (without `--no-kanji`).

Then run it with the interpreter from the virtualenv:

```bash
# Linux / macOS
.venv/bin/python run.py batch cards.csv

# Windows
.venv\Scripts\python run.py batch cards.csv
```

Dependencies are installed only into `.venv`. Running the script with the
system Python fails because the dependencies (`genanki` and others) are not
installed there; `run.py` names the missing package and prints the virtualenv
interpreter to use instead.

The available commands:

In these commands `python` means the virtualenv interpreter shown above, or
the active environment's `python` after activation (see below).

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

To activate the environment, run one of the commands below. Activation only
affects the current terminal session (and programs started from it): it
prepends the environment's scripts folder to `PATH` and sets `VIRTUAL_ENV`.
`deactivate` or closing the window undoes it; your permanent `PATH` is not
changed.

```bash
# Linux / macOS
source .venv/bin/activate

# Windows (cmd)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

Once active, `python` is the virtualenv interpreter and the `kotoba-forge`
console command that setup installed is on `PATH`:

```bash
kotoba-forge batch cards.csv
python run.py batch cards.csv
```

Activation is optional: the full paths `.venv\Scripts\kotoba-forge.exe`
(Windows) and `.venv/bin/kotoba-forge` (Linux/macOS) work without it. In
Windows PowerShell, if scripts are blocked by the execution policy, run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that window
first.

## VOICEVOX (optional)

Audio can come from files or from a local
[VOICEVOX](https://github.com/VOICEVOX/voicevox_engine/releases) engine. Download
the CPU build for your platform, extract it, and place it so the launcher is at:

```
voices/engine/run.exe     # Windows
voices/engine/run         # Linux / macOS
```

If no engine is present, the tool still uses CSV paths and files from the
audio folders; `--tts none` forces that behaviour.

When kotoba-forge starts the engine on Linux or Windows, it points VOICEVOX's
dictionary and preset storage under `voices/userdata` (`XDG_DATA_HOME` on Linux,
`LOCALAPPDATA` on Windows) instead of the real home directory. That keeps audio
generation working in a restricted sandbox or on a machine with a read-only
profile. On macOS the engine still uses
`~/Library/Application Support/voicevox-engine`, which must be writable. If you
launch the engine yourself it uses the platform data directory; on Windows you
can redirect that with a directory junction:

```
cmd /c mklink /J "%LOCALAPPDATA%\voicevox-engine" "<project>\voices\userdata"
```

Setup creates `voices/userdata`, so the link target exists if you choose to
create the link. It is only needed when you start the engine yourself:
kotoba-forge already points `LOCALAPPDATA` at `voices/userdata` for engines it
starts. `batch` and `one` warn only if the link exists but is broken or points
to another checkout; a missing link is normal. `--tts none` skips the warning
and VOICEVOX.

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

Templates live in `templates/`:

```
card1_front.html  card1_back.html
card2_front.html  card2_back.html
card3_front.html  card3_back.html
style.css
```

Edit them and rebuild for future packages. Once a deck is imported, Anki owns its
copy; use *Tools -> Manage Note Types -> Cards* from then on.

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
voices/userdata/       VOICEVOX data (gitignored, created by setup)
```

## Tests

```bash
python3 -m unittest discover -s tests -v
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
