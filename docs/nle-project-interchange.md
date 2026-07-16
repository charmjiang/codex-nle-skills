# NLE 工程互通 Skill 说明书

Skill 名称：`nle-project-interchange`

这个 skill 用来从剪辑工程或交换文件里提取时间线信息，尤其是每一个 cut 的时间码和字幕信息，然后导出给 Final Cut Pro、DaVinci Resolve、Premiere Pro、剪映/CapCut 使用的交换文件。

## 核心思路

不要做软件之间的两两硬转。

这个 skill 先把任何输入转成统一的中间层：

```text
输入工程/交换文件
  -> timeline.json
  -> FCP / 达芬奇 / PR / 剪映输出
```

中间层主要保存：

- cut 的开始时间、结束时间、持续时间
- track 信息
- 素材名或素材路径
- 字幕开始时间、结束时间、文本
- 基础帧率和时间线时长

这样以后要支持新软件，只需要新增导入/导出适配器。

## 支持的输入

优先推荐公开交换格式：

- Final Cut Pro：`.fcpxml`、`.fcpxmld`、XML
- Premiere Pro：FCP7 XML、SRT、EDL
- DaVinci Resolve：FCPXML、XML、EDL、SRT
- 剪映/CapCut：工程文件夹里的 `draft_content.json`
- 通用：`.srt`、`.edl`、统一时间线 JSON

原生工程的边界：

- `.prproj`：只有在它是可读 XML 或 gzip XML 时才尝试解析。
- `.drp` / `.dra`：会尝试当作压缩包检查，但不保证可解析。
- 剪映草稿：`draft_content.json` 是非官方结构，版本变化较大。

如果原生工程解析失败，建议从源软件导出 XML / FCPXML / EDL / SRT 后再转换。

## 输出文件

运行后会生成一组文件：

```text
timeline.json
cutlist.csv
captions.srt
fcp.fcpxml
resolve.fcpxml
resolve.edl
premiere.xml
jianying_draft_content.json
report.md
```

用途：

- `timeline.json`：统一中间层，后续所有导出都基于它。
- `cutlist.csv`：给人检查 cut 时间码。
- `captions.srt`：字幕文件。
- `fcp.fcpxml`：Final Cut Pro 导入。
- `resolve.fcpxml`：DaVinci Resolve 导入。
- `resolve.edl`：DaVinci Resolve 或其他软件的基础剪辑点导入。
- `premiere.xml`：Premiere Pro 友好的 FCP7 XML。
- `jianying_draft_content.json`：剪映/CapCut 草稿 JSON 的 best-effort 输出。
- `report.md`：转换报告，说明保留了什么、丢失了什么、有哪些警告。

## 在 Codex 里怎么用

把工程文件或交换文件发给 Codex，然后说：

```text
帮我提取每一个 cut 时间码和字幕信息，
分别导出 FCP、达芬奇、PR、剪映能用的文件。
```

Codex 会读取文件、生成输出目录，并给你文件链接和导入建议。

## 直接运行脚本

```bash
python3 skills/nle-project-interchange/scripts/timeline_interchange.py INPUT --out-dir outputs --stem demo
```

例子：

```bash
python3 skills/nle-project-interchange/scripts/timeline_interchange.py project.fcpxml --out-dir outputs --stem project
```

输出文件会放在 `outputs/` 里。

## 各软件导入建议

Final Cut Pro：

- 使用 `fcp.fcpxml`
- 菜单：`File > Import > XML...`

DaVinci Resolve：

- 优先试 `resolve.fcpxml`
- 如果只需要剪辑点，试 `resolve.edl`
- 字幕使用 `captions.srt`

Premiere Pro：

- 使用 `premiere.xml`
- 字幕使用 `captions.srt`
- 注意：Premiere 更适合导入 FCP7 XML，不是现代 FCPXML。

剪映 / CapCut：

- 字幕优先使用 `captions.srt`
- `jianying_draft_content.json` 属于 best-effort 草稿 JSON
- 如果你要稳定导入完整剪映草稿，最好提供同版本剪映生成的空白草稿模板，让 Codex 在模板基础上 patch

## 保真范围

比较可靠：

- cut 时间码
- clip 名称
- 基础轨道信息
- 字幕文本和时间码
- SRT / EDL / XML / FCPXML 这类交换格式

不保证无损：

- 调色
- 转场
- 复杂特效
- 速度曲线
- 多机位
- 嵌套时间线
- 复合片段
- 音频自动化
- 字体样式完全一致
- PR / 达芬奇 / 剪映原生工程里的私有状态

## 为什么不用原生工程互转

很多剪辑软件的原生工程格式不是稳定公开协议。

例如：

- Premiere 的 `.prproj` 不适合手写生成。
- DaVinci 的 `.drp` 是项目包，不是轻量交换格式。
- 剪映的 `draft_content.json` 没有官方稳定文档，不同版本字段可能变化。

所以这个 skill 的策略是：

1. 能读原生就读。
2. 不能读就提示用户导出交换格式。
3. 能写公开交换格式就写公开交换格式。
4. 对私有草稿格式只做 best-effort，必要时基于用户提供的模板 patch。

## 排错

如果 cut 数量是 0：

- 源文件可能只有字幕或标题，没有真实媒体片段。
- 检查 `report.md` 里的 warning。
- 尝试从原软件导出 XML/FCPXML/EDL。

如果字幕不见了：

- 检查源文件里字幕是 caption、title 还是普通文字图层。
- 尝试同时提供 SRT。
- 给 Codex 一份原工程和导出的 SRT，让它合并时间线。

如果剪映导入失败：

- 优先使用 SRT 导入字幕。
- 提供一个同版本剪映的空白草稿文件夹。
- 让 Codex 以模板为基础 patch `draft_content.json`。

## 适合分享时怎么描述

一句话版本：

> 一个 Codex skill，把剪辑工程里的 cut 时间码和字幕抽成统一 timeline，再导出 FCP、达芬奇、PR、剪映可用的交换文件。

更准确版本：

> 它不是万能无损工程转换器，而是一个实用的剪辑时间线互通工具：优先保留 cut、字幕、时间码和基础轨道信息，再为不同软件生成最稳的导入格式。
