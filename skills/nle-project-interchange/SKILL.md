---
name: nle-project-interchange
description: Extract and interchange edit timeline data across NLE project formats. Use when the user provides or asks about DaVinci Resolve, Final Cut Pro, Premiere Pro, CapCut/Jianying/剪映, FCPXML, XML, EDL, SRT, PRPROJ, DRP, DRT, or draft_content.json files and wants cuts, edit timecodes, subtitles, or export bundles for Resolve/FCP/Premiere/Jianying.
---

# NLE Project Interchange

## Core Rule

Use a canonical timeline model as the bridge:

1. Ingest any supplied project/interchange file.
2. Extract edit events as `cuts` and subtitle/title events as `captions`.
3. Save `timeline.json` as the source of truth.
4. Export per-app deliverables from that model.
5. Include a report that states what was preserved, approximated, or unsupported.

Do not promise lossless native project round-tripping. Treat cut timing, track order, source names/paths, and subtitles as the reliable interchange layer. Effects, transitions, compound/nested timelines, speed ramps, color, audio automation, generators, motion graphics, fonts, and proprietary app state are best-effort only.

## Quick Start

Run the bundled converter:

```bash
python3 /Users/cce/.codex/skills/nle-project-interchange/scripts/timeline_interchange.py INPUT --out-dir outputs --stem timeline
```

Primary outputs:

- `timeline.json`: canonical extracted cuts/captions.
- `cutlist.csv`: cut/event rows for inspection.
- `captions.srt`: subtitles only.
- `fcp.fcpxml`: Final Cut Pro import target.
- `resolve.fcpxml` and `resolve.edl`: DaVinci Resolve import targets.
- `premiere.xml`: Premiere-friendly FCP7-style XML target.
- `jianying_draft_content.json`: best-effort CapCut/Jianying draft-content style JSON.
- `report.md`: warnings and fidelity notes.

Validate XML outputs with `xmllint --noout` when available.

## Supported Inputs

Prefer open interchange exports when the user can provide them:

- FCP/FCPX: `.fcpxml`, `.fcpxmld` bundle, XML exported from Final Cut Pro.
- Premiere Pro: Final Cut Pro XML export (`.xml`) or SRT/EDL sidecars. Native `.prproj` is only parsed if it is readable XML/gzip XML.
- DaVinci Resolve: `.fcpxml`, `.xml`, `.edl`, `.srt`; native `.drp` is inspected as an archive when possible but should be treated as non-stable.
- CapCut/Jianying/剪映: project folder or `draft_content.json`; format is unofficial and version-sensitive.
- Generic: `.srt`, `.edl`, JSON timeline model.

If the user provides native `.prproj`, `.drp`, or an opaque app bundle and parsing fails, ask them to export XML/FCPXML/EDL/SRT from the source app, then rerun.

## Export Policy

- For Final Cut Pro, export FCPXML.
- For DaVinci Resolve, export FCPXML plus EDL and SRT because Resolve can import common interchange formats.
- For Premiere Pro, export FCP7-style XML plus SRT. Premiere does not directly import modern FCPXML from Final Cut Pro X without conversion.
- For Jianying/CapCut, export SRT plus best-effort draft JSON. If exact project import is required, ask for a blank/template Jianying draft from the same app version and patch that template rather than inventing a full native draft.

Read [references/format-support.md](references/format-support.md) when a task depends on exact app limitations or the user asks why a format cannot be losslessly converted.

## Handling User Files

1. Copy or read the supplied project file/folder without modifying it.
2. Run the converter into a user-facing `outputs/` folder.
3. Inspect `report.md` and the first rows of `timeline.json`/`cutlist.csv`.
4. If cuts or captions are unexpectedly missing, inspect the source file structure manually and update the parser or produce a focused explanation.
5. Return links to generated files and say which import path to use in each app.

## Quality Checks

Always check:

- XML files parse successfully.
- Caption count matches expectations from source subtitles/titles.
- Cut count is nonzero for timeline projects with media edits.
- Timeline duration is at least the latest cut or caption end.
- Report includes warnings for unsupported native/proprietary formats.

Use exact absolute file links in the final response for generated deliverables.
