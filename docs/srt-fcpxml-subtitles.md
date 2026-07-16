# SRT/FCPXML 字幕生成 Skill 说明书

Skill 名称：`srt-fcpxml-subtitles`

这个 skill 用来把粗略的字幕时间码文本，生成标准 `.srt` 字幕，以及 Final Cut Pro 可导入的 `.xml` / `.fcpxml` 字幕工程文件。

## 适合谁用

- 你有一段口播、采访、短视频字幕时间码。
- 你想快速生成 SRT。
- 你想把字幕作为 Final Cut Pro 的标题层导入。
- 你手里有 Crossub/FCPXML 样例，希望以后生成同样风格的 XML。

## 能做什么

- 读取类似 `00:02 文案` 的时间码文本。
- 支持单点时间码和开始-结束时间码。
- 自动推断缺失的结束时间。
- 生成三个文件：
  - `.srt`
  - `.xml`
  - `.fcpxml`
- FCPXML 默认使用 1080p30、居中白字、描边、阴影、底部标题位置。

## 输入格式

支持这些写法：

```text
00:02 Don't predict
00:03 Don't predict
00:05 - 00:06 Don't predict
00:13 (Don't predict, it's Paradoxe.)
00:15 -00:17 Don't predict
01:02:03.500 Subtitle with hours and milliseconds
```

规则：

- `MM:SS` 会被理解成分秒。
- `HH:MM:SS` 会被理解成时分秒。
- 毫秒可以用 `.` 或 `,`。
- 如果一行没有结束时间，就用下一句的开始时间作为结束时间。
- 最后一行没有结束时间时，默认持续 2 秒。
- 如果整句被一层括号包住，例如 `(text)`，会去掉外层括号。

## 在 Codex 里怎么用

安装后，在 Codex 里直接这样说：

```text
00:02 Don't predict
00:03 Don't predict
00:05 - 00:06 Don't predict

帮我出 srt 和 FCPXML
```

Codex 会自动触发 skill，并输出可点击的文件链接。

## 直接运行脚本

也可以不通过 Codex，直接运行脚本：

```bash
python3 skills/srt-fcpxml-subtitles/scripts/subtitle_converter.py input.txt --out-dir outputs --stem demo
```

输出：

```text
outputs/demo.srt
outputs/demo.xml
outputs/demo.fcpxml
```

常用参数：

```bash
--stem demo
--out-dir outputs
--project-name demo_project
--last-duration 2
--sequence-padding 1
```

## 导入 Final Cut Pro

推荐导入 `.fcpxml`：

1. 打开 Final Cut Pro。
2. 选择 `File > Import > XML...`。
3. 选择生成的 `.fcpxml` 文件。
4. 字幕会以标题层形式进入时间线。

如果 FCP 对 `.xml` 扩展名不敏感，优先使用 `.fcpxml`。

## 默认 FCPXML 样式

默认字幕样式接近 Crossub / FCP 自定标题导出的结构：

- FCPXML 版本：`1.8`
- 时间线：1080p30
- 字体：`PingFang SC`
- 字号：`62`
- 字重：Semibold
- 颜色：白色
- 位置：底部居中
- 描边和阴影：开启

如果你提供一份样例 `.fcpxml`，Codex 会优先参考样例的时间写法、标题 effect、位置、对齐和文本样式。

## 注意事项

- 这个 skill 主要处理字幕，不处理完整剪辑工程。
- 它不会自动识别视频中的声音，需要你提供时间码文本。
- FCPXML 的样式参数依赖 Final Cut Pro 标题模板，不同机器或版本可能略有差异。
- 如果导入 FCP 后样式不一致，可以给 Codex 一份你机器上导出的 FCPXML 样例，再重新生成。

## 排错

如果 XML 导入失败：

- 确认使用的是 `.fcpxml` 文件。
- 确认字幕文本里没有奇怪的控制字符。
- 让 Codex 运行 XML 结构检查。
- 给 Codex 一份你当前 FCP 能成功导入的 XML 样例，让它镜像格式。
