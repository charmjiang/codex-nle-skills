# Codex NLE Skills

两个面向剪辑工作流的 Codex skills：

- `srt-fcpxml-subtitles`：把粗时间码文本生成 SRT、Final Cut Pro XML/FCPXML 字幕文件。
- `nle-project-interchange`：从剪辑工程或交换文件中提取 cut 时间码和字幕，再导出给 FCP、达芬奇、PR、剪映使用的交换文件。

## 说明书

- [SRT/FCPXML 字幕生成 Skill 说明书](docs/srt-fcpxml-subtitles.md)
- [NLE 工程互通 Skill 说明书](docs/nle-project-interchange.md)

## 安装

把需要的 skill 文件夹复制到 Codex skills 目录：

```bash
cp -R skills/srt-fcpxml-subtitles ~/.codex/skills/
cp -R skills/nle-project-interchange ~/.codex/skills/
```

然后重启 Codex，或新开一个任务，让 Codex 重新发现 skill。

## 仓库结构

```text
skills/
  srt-fcpxml-subtitles/
    SKILL.md
    scripts/subtitle_converter.py
  nle-project-interchange/
    SKILL.md
    scripts/timeline_interchange.py
    references/format-support.md
docs/
  srt-fcpxml-subtitles.md
  nle-project-interchange.md
```

## 适用场景

- 快速把口播时间码变成 SRT 和 FCP 可导入字幕。
- 把 FCPXML、XML、EDL、SRT、剪映草稿 JSON 等文件抽成统一时间线。
- 给 Final Cut Pro、DaVinci Resolve、Premiere Pro、剪映/CapCut 生成可导入的交换文件。

## 重要边界

这些 skills 优先保证 cut 时间码、字幕文本、字幕时间、基础轨道信息的互通。它们不会承诺无损还原所有剪辑软件原生工程能力，例如复杂特效、转场、调色、速度曲线、嵌套时间线、音频自动化、动态图形模板等。

如果需要最高兼容性，优先从剪辑软件导出公开交换格式，例如 FCPXML、FCP7 XML、EDL、SRT。

## License

MIT License. See [LICENSE](LICENSE).
