---
name: srt-fcpxml-subtitles
description: Generate subtitle deliverables from rough timestamped transcript text. Use when the user asks for SRT, XML, FCPXML, Final Cut Pro subtitle/title XML, Crossub-like custom title XML, or provides lines such as "00:02 text" or "00:05 - 00:06 text" and wants subtitle files.
---

# SRT FCPXML Subtitles

## Overview

Generate `.srt`, `.xml`, and `.fcpxml` subtitle files from rough timestamped text. The bundled script produces standard SRT plus Final Cut Pro `fcpxml` 1.8 using custom title nodes similar to Crossub exports.

## Workflow

1. Read the user's timestamped text and any provided sample `.fcpxml`.
2. If a sample `.fcpxml` is provided, inspect it before generating and mirror its important settings: FCPXML version, sequence format, title effect, text style, position, alignment, and duration representation.
3. Preserve the user's subtitle wording exactly, except remove one pair of wrapping parentheses when the entire subtitle is written like `(text)`.
4. Infer missing end times from the next subtitle start. For the final subtitle, use a 2 second default unless the user specifies another duration.
5. Run `scripts/subtitle_converter.py` with the transcript text saved in a temporary input file.
6. Validate generated XML/FCPXML with `xmllint --noout` when available.
7. Return links to the user-facing `.srt`, `.xml`, and `.fcpxml` files.

## Script Usage

Use the bundled script from the skill directory:

```bash
python3 /Users/cce/.codex/skills/srt-fcpxml-subtitles/scripts/subtitle_converter.py input.txt --out-dir outputs --stem subtitle_name
```

Common options:

- `--stem`: output filename stem; defaults to the input filename stem.
- `--out-dir`: output directory; defaults to `outputs`.
- `--project-name`: Final Cut Pro project name; defaults to the stem.
- `--last-duration`: seconds for a final subtitle without an explicit end; defaults to `2`.
- `--sequence-padding`: seconds added after the last subtitle for the FCPXML sequence duration; defaults to `1`.
- `--library-location`: FCPXML library URL; defaults to the known `365days.fcpbundle` style used by the sample.

The script writes three files:

- `<stem>.srt`
- `<stem>.xml`
- `<stem>.fcpxml`

The `.xml` and `.fcpxml` contents are identical Final Cut Pro XML; the `.fcpxml` extension is more convenient for direct import into Final Cut Pro.

## Input Format

Accepted timestamp lines:

```text
00:02 Don't predict
00:05 - 00:06 Don't predict
00:15 -00:17 Don't predict
00:13 (Don't predict, it's Paradoxe.)
01:02:03.500 Subtitle with hours and milliseconds
```

Rules:

- Interpret `MM:SS` as minutes and seconds.
- Interpret `HH:MM:SS` as hours, minutes, and seconds.
- Accept optional milliseconds with `.` or `,`.
- Ignore blank lines.
- Treat text after the start/end time as the subtitle body.

## Final Cut Pro Defaults

When no user sample overrides them, generate FCPXML with:

- `fcpxml version="1.8"`
- `FFVideoFormat1080p30`, `frameDuration="100/3000s"`, `1920x1080`, Rec. 709
- Custom title effect uid: `.../Titles.localized/Build In:Out.localized/Custom.localized/Custom.moti`
- Title position `0 -340`, centered alignment
- Font `PingFang SC`, size `62`, Semibold, white text, subtle stroke and shadow
- Time values as `<seconds * 3000>/3000s`, matching the sample export style

Ask a concise clarification only when the target XML dialect is ambiguous or the missing timing assumptions would materially change the edit.
