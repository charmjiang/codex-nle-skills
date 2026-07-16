# Codex NLE Skills

This repository contains two Codex skills for subtitle and editing-project interchange workflows.

## Skills

- `srt-fcpxml-subtitles`: generate SRT plus Final Cut Pro XML/FCPXML subtitles from timestamped transcript text.
- `nle-project-interchange`: extract cuts and captions into a canonical timeline model, then export interchange files for Final Cut Pro, DaVinci Resolve, Premiere Pro, and Jianying/CapCut.

## Install

Copy the desired folders into your Codex skills directory:

```bash
cp -R skills/srt-fcpxml-subtitles ~/.codex/skills/
cp -R skills/nle-project-interchange ~/.codex/skills/
```

Restart Codex or start a new task so the skills can be discovered.
