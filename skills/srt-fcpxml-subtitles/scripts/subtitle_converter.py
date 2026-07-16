#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import shutil
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape, quoteattr


TIME_PATTERN = r"\d{1,2}:\d{2}(?::\d{2})?(?:[\.,]\d{1,3})?"
LINE_RE = re.compile(
    rf"^\s*(?P<start>{TIME_PATTERN})\s*"
    rf"(?:(?:-->|-|–|—)\s*(?P<end>{TIME_PATTERN})\s*)?"
    rf"(?P<text>.*?)\s*$"
)


@dataclass
class Caption:
    start: float
    end: float
    text: str


@dataclass
class ParsedLine:
    start: float
    end: Optional[float]
    text: str
    source_line: int


def parse_time(value: str) -> float:
    normalized = value.replace(",", ".")
    parts = normalized.split(":")
    if len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1])
    elif len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    else:
        raise ValueError(f"Unsupported time value: {value}")
    return hours * 3600 + minutes * 60 + seconds


def clean_text(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text.startswith("(") and text.endswith(")"):
        return text[1:-1].strip()
    return text


def parse_lines(raw_text: str) -> list[ParsedLine]:
    parsed: list[ParsedLine] = []
    for line_number, raw_line in enumerate(raw_text.splitlines(), start=1):
        if not raw_line.strip():
            continue
        match = LINE_RE.match(raw_line)
        if not match:
            raise ValueError(f"Line {line_number} is not a supported timestamp line: {raw_line}")
        text = clean_text(match.group("text") or "")
        if not text:
            raise ValueError(f"Line {line_number} has no subtitle text: {raw_line}")
        start = parse_time(match.group("start"))
        end_value = match.group("end")
        end = parse_time(end_value) if end_value else None
        if end is not None and end <= start:
            raise ValueError(f"Line {line_number} end time must be after start time: {raw_line}")
        parsed.append(ParsedLine(start=start, end=end, text=text, source_line=line_number))
    if not parsed:
        raise ValueError("No subtitle lines found.")
    return parsed


def infer_captions(lines: list[ParsedLine], last_duration: float) -> list[Caption]:
    captions: list[Caption] = []
    for index, line in enumerate(lines):
        if line.end is not None:
            end = line.end
        elif index + 1 < len(lines) and lines[index + 1].start > line.start:
            end = lines[index + 1].start
        else:
            end = line.start + last_duration
        if end <= line.start:
            raise ValueError(f"Line {line.source_line} inferred an invalid duration.")
        captions.append(Caption(start=line.start, end=end, text=line.text))
    return captions


def srt_time(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def fcpxml_time(seconds: float, timebase: int = 3000) -> str:
    numerator = int(round(seconds * timebase))
    return f"{numerator}/{timebase}s"


def write_srt(captions: list[Caption], path: Path) -> None:
    blocks = []
    for index, caption in enumerate(captions, start=1):
        blocks.append(
            f"{index}\n{srt_time(caption.start)} --> {srt_time(caption.end)}\n{caption.text}"
        )
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def title_block(caption: Caption, index: int) -> str:
    title_name = f"{caption.text} - 自定"
    offset = fcpxml_time(caption.start)
    duration = fcpxml_time(caption.end - caption.start)
    text = escape(caption.text)
    quoted_title = quoteattr(title_name)
    return f"""<title name={quoted_title} lane="1" offset="{offset}" ref="r2" duration="{duration}">
<param name="位置" key="9999/10199/10201/1/100/101" value="0 -340"/>
<param name="对齐" key="9999/10199/10201/2/354/1002961760/401" value="1 (居中)"/>
<param name="Out Sequencing" key="9999/10199/10201/4/10233/201/202" value="0 (到)"/>

<text>
  <text-style ref="ts{index}">{text}</text-style>
</text>
<text-style-def id="ts{index}">
  <text-style font="PingFang SC" fontSize="62" fontFace="Semibold" fontColor="1 1 1 1" bold="1" strokeColor="0.329705 0.329721 0.329713 1" strokeWidth="-1" shadowColor="0 0 0 0.75" shadowOffset="3 315" kerning="1.24" alignment="center"/>
</text-style-def>
</title>"""


def write_fcpxml(
    captions: list[Caption],
    path: Path,
    project_name: str,
    library_location: str,
    sequence_padding: float,
) -> None:
    last_end = max(caption.end for caption in captions)
    sequence_duration = fcpxml_time(last_end + sequence_padding)
    event_uid = str(uuid.uuid4()).upper()
    project_uid = str(uuid.uuid4()).upper()
    mod_date = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    blocks = "\n".join(title_block(caption, index) for index, caption in enumerate(captions, start=1))
    quoted_project = quoteattr(project_name)
    quoted_library = quoteattr(library_location)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>

<fcpxml version="1.8">
  <resources>
    <format id="r1" name="FFVideoFormat1080p30" frameDuration="100/3000s" width="1920" height="1080" colorSpace="1-1-1 (Rec. 709)"/>
    <effect id="r2" name="自定" uid=".../Titles.localized/Build In:Out.localized/Custom.localized/Custom.moti"/>
  </resources>
  <library location={quoted_library}>
    <event name="crossub" uid="{event_uid}">
      <project name={quoted_project} uid="{project_uid}" modDate="{mod_date}">
        <sequence duration="{sequence_duration}" format="r1" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">
          <spine>
            <gap name="空隙" offset="0s" duration="{sequence_duration}">
{blocks}

            </gap>
          </spine>
        </sequence>
      </project>
    </event>
    <smart-collection name="项目" match="all">
      <match-clip rule="is" type="project"/>
    </smart-collection>
    <smart-collection name="所有视频" match="any">
      <match-media rule="is" type="videoOnly"/>
      <match-media rule="is" type="videoWithAudio"/>
    </smart-collection>
    <smart-collection name="仅音频" match="all">
      <match-media rule="is" type="audioOnly"/>
    </smart-collection>
    <smart-collection name="静止图像" match="all">
      <match-media rule="is" type="stills"/>
    </smart-collection>
    <smart-collection name="个人收藏" match="all">
      <match-ratings value="favorites"/>
    </smart-collection>
  </library>
</fcpxml>
"""
    path.write_text(xml, encoding="utf-8")


def validate_xml(path: Path) -> None:
    if shutil.which("xmllint") is None:
        return
    import subprocess

    subprocess.run(["xmllint", "--noout", str(path)], check=True)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate SRT and Final Cut Pro FCPXML subtitle files.")
    parser.add_argument("input", type=Path, help="Plain text file containing timestamped subtitle lines.")
    parser.add_argument("--out-dir", type=Path, default=Path("outputs"), help="Directory for generated files.")
    parser.add_argument("--stem", help="Output filename stem. Defaults to the input filename stem.")
    parser.add_argument("--project-name", help="Final Cut Pro project name. Defaults to the output stem.")
    parser.add_argument("--last-duration", type=float, default=2.0, help="Seconds for final subtitle without an end.")
    parser.add_argument("--sequence-padding", type=float, default=1.0, help="Seconds added after the last subtitle in FCPXML.")
    parser.add_argument(
        "--library-location",
        default="file:///Users/wu/Movies/365days.fcpbundle/",
        help="FCPXML library location URL.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    try:
        raw_text = args.input.read_text(encoding="utf-8")
        lines = parse_lines(raw_text)
        captions = infer_captions(lines, last_duration=args.last_duration)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        stem = args.stem or args.input.stem
        project_name = args.project_name or stem
        srt_path = args.out_dir / f"{stem}.srt"
        xml_path = args.out_dir / f"{stem}.xml"
        fcpxml_path = args.out_dir / f"{stem}.fcpxml"

        write_srt(captions, srt_path)
        write_fcpxml(captions, xml_path, project_name, args.library_location, args.sequence_padding)
        fcpxml_path.write_text(xml_path.read_text(encoding="utf-8"), encoding="utf-8")
        validate_xml(xml_path)
        validate_xml(fcpxml_path)
    except Exception as exc:
        print(f"subtitle_converter: {exc}", file=sys.stderr)
        return 1

    print(srt_path)
    print(xml_path)
    print(fcpxml_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
