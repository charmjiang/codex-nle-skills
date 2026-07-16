#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
import shutil
import sys
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape, quoteattr


DEFAULT_FPS = 30.0
TIMEBASE = 3000


@dataclass
class TimelineItem:
    id: str
    start: float
    end: float
    track: str = ""
    name: str = ""
    source: str = ""
    source_start: Optional[float] = None
    source_end: Optional[float] = None
    kind: str = "unknown"

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class Caption:
    id: str
    start: float
    end: float
    text: str
    track: str = "S1"

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class Timeline:
    name: str
    fps: float = DEFAULT_FPS
    duration: float = 0.0
    source_path: str = ""
    source_format: str = "unknown"
    cuts: list[TimelineItem] = field(default_factory=list)
    captions: list[Caption] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def finalize(self) -> None:
        latest = 0.0
        for item in self.cuts:
            latest = max(latest, item.end)
        for caption in self.captions:
            latest = max(latest, caption.end)
        self.duration = max(self.duration, latest)
        self.cuts.sort(key=lambda item: (item.start, item.track, item.id))
        self.captions.sort(key=lambda caption: (caption.start, caption.track, caption.id))


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(element: ET.Element, name: str) -> str:
    for child in element:
        if local_name(child.tag) == name:
            return "".join(child.itertext()).strip()
    return ""


def descendants(element: ET.Element, name: str) -> list[ET.Element]:
    return [node for node in element.iter() if local_name(node.tag) == name]


def parse_rational_seconds(value: Optional[str], fps: float = DEFAULT_FPS) -> Optional[float]:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith("s"):
        raw = raw[:-1]
    try:
        if "/" in raw:
            numerator, denominator = raw.split("/", 1)
            return float(numerator) / float(denominator)
        return float(raw)
    except ValueError:
        pass
    if re.match(r"^\d{1,2}:\d{2}:\d{2}[:;,\.]\d{1,3}$", raw):
        return parse_timecode(raw, fps)
    return None


def parse_srt_time(value: str) -> float:
    hours, minutes, rest = value.strip().replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(rest)


def parse_timecode(value: str, fps: float = DEFAULT_FPS) -> float:
    match = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})[:;,\.](\d{1,3})$", value.strip())
    if not match:
        raise ValueError(f"Unsupported timecode: {value}")
    hours, minutes, seconds, frames = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(frames) / fps


def seconds_to_srt(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def seconds_to_fcpxml(seconds: float) -> str:
    return f"{int(round(seconds * TIMEBASE))}/{TIMEBASE}s"


def seconds_to_timecode(seconds: float, fps: float = DEFAULT_FPS) -> str:
    total_frames = int(round(seconds * fps))
    frames_per_hour = int(round(fps * 3600))
    frames_per_minute = int(round(fps * 60))
    hours, remainder = divmod(total_frames, frames_per_hour)
    minutes, remainder = divmod(remainder, frames_per_minute)
    secs, frames = divmod(remainder, int(round(fps)))
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


def read_text_maybe_compressed(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\x1f\x8b"):
        data = gzip.decompress(data)
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def find_project_payload(path: Path, warnings: list[str]) -> Path:
    if path.is_dir():
        if path.suffix.lower() == ".fcpxmld":
            candidates = sorted(path.rglob("*.fcpxml")) + sorted(path.rglob("*.xml"))
            if candidates:
                return candidates[0]
        draft = path / "draft_content.json"
        if draft.exists():
            return draft
        timeline_drafts = sorted(path.rglob("draft_content.json"))
        if timeline_drafts:
            return timeline_drafts[0]
        raise ValueError(f"No supported project payload found in folder: {path}")

    if path.suffix.lower() in {".drp", ".dra", ".zip"} and zipfile.is_zipfile(path):
        temp_dir = Path(tempfile.mkdtemp(prefix="nle-project-"))
        with zipfile.ZipFile(path) as archive:
            archive.extractall(temp_dir)
        for pattern in ("*.fcpxml", "*.xml", "*.edl", "*.srt", "draft_content.json", "*.json"):
            candidates = sorted(temp_dir.rglob(pattern))
            if candidates:
                warnings.append(f"Read {path.name} as archive and used {candidates[0].name}.")
                return candidates[0]
        warnings.append(f"{path.name} was an archive but no supported timeline payload was found.")
    return path


def parse_srt(path: Path) -> Timeline:
    text = read_text_maybe_compressed(path)
    timeline = Timeline(name=path.stem, source_path=str(path), source_format="srt")
    block_re = re.compile(
        r"(?ms)^\s*(\d+)?\s*\n?\s*(\d{2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{1,3}).*?\n(.*?)(?=\n\s*\n|\Z)"
    )
    for index, match in enumerate(block_re.finditer(text), start=1):
        body = "\n".join(line.strip() for line in match.group(4).strip().splitlines()).strip()
        if body:
            timeline.captions.append(
                Caption(
                    id=f"cap-{index:04d}",
                    start=parse_srt_time(match.group(2)),
                    end=parse_srt_time(match.group(3)),
                    text=body,
                )
            )
    if not timeline.captions:
        timeline.warnings.append("No SRT captions found.")
    timeline.finalize()
    return timeline


def detect_fps_from_fcpxml(root: ET.Element) -> float:
    for node in descendants(root, "format"):
        frame_duration = parse_rational_seconds(node.attrib.get("frameDuration"))
        if frame_duration and frame_duration > 0:
            return 1.0 / frame_duration
    return DEFAULT_FPS


def parse_fcpxml(path: Path) -> Timeline:
    text = read_text_maybe_compressed(path)
    root = ET.fromstring(text)
    fps = detect_fps_from_fcpxml(root)
    timeline = Timeline(name=path.stem, fps=fps, source_path=str(path), source_format="fcpxml")
    project = next((node for node in root.iter() if local_name(node.tag) == "project"), None)
    if project is not None and project.attrib.get("name"):
        timeline.name = project.attrib["name"]
    sequence = next((node for node in root.iter() if local_name(node.tag) == "sequence"), None)
    if sequence is not None:
        duration = parse_rational_seconds(sequence.attrib.get("duration"), fps)
        if duration:
            timeline.duration = duration

    for index, title in enumerate(descendants(root, "title"), start=1):
        start = parse_rational_seconds(title.attrib.get("offset"), fps)
        if start is None:
            start = parse_rational_seconds(title.attrib.get("start"), fps) or 0.0
        duration = parse_rational_seconds(title.attrib.get("duration"), fps) or 0.0
        text_value = " ".join(
            " ".join(part.strip() for part in node.itertext() if part.strip())
            for node in descendants(title, "text")
        ).strip()
        if not text_value:
            text_value = title.attrib.get("name", "").replace(" - 自定", "").strip()
        if text_value:
            timeline.captions.append(
                Caption(id=f"cap-{index:04d}", start=start, end=start + duration, text=text_value)
            )

    cut_tags = {"asset-clip", "clip", "video", "audio", "sync-clip", "multicam-clip", "ref-clip"}
    skip_ancestors = {"title"}
    cut_index = 1
    for node in root.iter():
        tag = local_name(node.tag)
        if tag not in cut_tags:
            continue
        if any(local_name(parent.tag) in skip_ancestors for parent in []):
            continue
        duration = parse_rational_seconds(node.attrib.get("duration"), fps)
        if not duration or duration <= 0:
            continue
        start = parse_rational_seconds(node.attrib.get("offset"), fps)
        if start is None:
            start = parse_rational_seconds(node.attrib.get("start"), fps) or 0.0
        name = node.attrib.get("name", tag)
        source_start = parse_rational_seconds(node.attrib.get("start"), fps)
        timeline.cuts.append(
            TimelineItem(
                id=f"cut-{cut_index:04d}",
                start=start,
                end=start + duration,
                track="V1" if tag != "audio" else "A1",
                name=name,
                source=node.attrib.get("ref", ""),
                source_start=source_start,
                source_end=source_start + duration if source_start is not None else None,
                kind="audio" if tag == "audio" else "video",
            )
        )
        cut_index += 1
    if not timeline.cuts:
        timeline.warnings.append("No media cut nodes found; file may contain subtitles/titles only.")
    timeline.finalize()
    return timeline


def parse_xmeml(path: Path) -> Timeline:
    text = read_text_maybe_compressed(path)
    root = ET.fromstring(text)
    fps = DEFAULT_FPS
    timebase = next((node for node in root.iter() if local_name(node.tag) == "timebase"), None)
    if timebase is not None and timebase.text and timebase.text.strip().isdigit():
        fps = float(timebase.text.strip())
    sequence = next((node for node in root.iter() if local_name(node.tag) == "sequence"), None)
    name = child_text(sequence, "name") if sequence is not None else path.stem
    timeline = Timeline(name=name or path.stem, fps=fps, source_path=str(path), source_format="xmeml")
    duration_text = child_text(sequence, "duration") if sequence is not None else ""
    if duration_text.isdigit():
        timeline.duration = int(duration_text) / fps

    index = 1
    for clipitem in descendants(root, "clipitem"):
        start_text = child_text(clipitem, "start")
        end_text = child_text(clipitem, "end")
        if not (start_text.lstrip("-").isdigit() and end_text.lstrip("-").isdigit()):
            continue
        start_frame = max(0, int(start_text))
        end_frame = max(start_frame, int(end_text))
        name_text = child_text(clipitem, "name") or clipitem.attrib.get("id", f"clip-{index}")
        pathurl = child_text(clipitem, "pathurl")
        timeline.cuts.append(
            TimelineItem(
                id=f"cut-{index:04d}",
                start=start_frame / fps,
                end=end_frame / fps,
                track="V1",
                name=name_text,
                source=pathurl,
                kind="video",
            )
        )
        index += 1

    cap_index = 1
    for generator in descendants(root, "generatoritem"):
        text_value = " ".join(part.strip() for part in generator.itertext() if part.strip())
        start_text = child_text(generator, "start")
        end_text = child_text(generator, "end")
        if text_value and start_text.isdigit() and end_text.isdigit():
            timeline.captions.append(
                Caption(
                    id=f"cap-{cap_index:04d}",
                    start=int(start_text) / fps,
                    end=int(end_text) / fps,
                    text=text_value,
                )
            )
            cap_index += 1
    timeline.finalize()
    return timeline


def parse_edl(path: Path, fps: float = DEFAULT_FPS) -> Timeline:
    text = read_text_maybe_compressed(path)
    timeline = Timeline(name=path.stem, fps=fps, source_path=str(path), source_format="edl")
    event_re = re.compile(
        r"^\s*(\d{3,})\s+(\S+)\s+([AVB]+)\s+([CDW]\S*)\s+"
        r"(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})\s+"
        r"(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})"
    )
    for line in text.splitlines():
        match = event_re.match(line)
        if not match:
            continue
        event_id, reel, track, transition, src_in, src_out, rec_in, rec_out = match.groups()
        start = parse_timecode(rec_in, fps)
        end = parse_timecode(rec_out, fps)
        timeline.cuts.append(
            TimelineItem(
                id=f"cut-{event_id}",
                start=start,
                end=end,
                track=track,
                name=reel,
                source=reel,
                source_start=parse_timecode(src_in, fps),
                source_end=parse_timecode(src_out, fps),
                kind="video" if "V" in track else "audio",
            )
        )
    if not timeline.cuts:
        timeline.warnings.append("No CMX3600-style EDL events found.")
    timeline.finalize()
    return timeline


def normalize_seconds(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None
    if not isinstance(value, (int, float)) or math.isnan(float(value)):
        return None
    numeric = float(value)
    if abs(numeric) >= 10_000:
        return numeric / 1_000_000.0
    return numeric


def extract_text_from_material(material: dict[str, Any]) -> str:
    candidates = [
        material.get("content"),
        material.get("text"),
        material.get("name"),
        material.get("recognize_text"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    for value in material.values():
        if isinstance(value, dict):
            nested = extract_text_from_material(value)
            if nested:
                return nested
        if isinstance(value, list):
            parts = []
            for item in value:
                if isinstance(item, dict):
                    nested = extract_text_from_material(item)
                    if nested:
                        parts.append(nested)
            if parts:
                return " ".join(parts)
    return ""


def walk_json(value: Any) -> Any:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def timerange_seconds(node: dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
    timerange = node.get("target_timerange") or node.get("timerange") or node.get("time_range")
    if isinstance(timerange, dict):
        start = normalize_seconds(timerange.get("start"))
        duration = normalize_seconds(timerange.get("duration"))
        if start is not None and duration is not None:
            return start, start + duration
    start = normalize_seconds(node.get("start"))
    duration = normalize_seconds(node.get("duration"))
    end = normalize_seconds(node.get("end"))
    if start is not None and duration is not None:
        return start, start + duration
    if start is not None and end is not None:
        return start, end
    return None, None


def parse_jianying_json(path: Path) -> Timeline:
    data = json.loads(read_text_maybe_compressed(path))
    timeline = Timeline(name=path.stem, source_path=str(path), source_format="jianying-json")
    timeline.warnings.append("CapCut/Jianying project JSON is unofficial and version-sensitive; output is best-effort.")
    fps = data.get("fps") or data.get("frame_rate")
    if isinstance(fps, (int, float)) and fps > 0:
        timeline.fps = float(fps)
    duration = normalize_seconds(data.get("duration"))
    if duration:
        timeline.duration = duration

    text_by_id: dict[str, str] = {}
    materials = data.get("materials")
    if isinstance(materials, dict):
        text_materials = materials.get("texts") or materials.get("text") or []
        if isinstance(text_materials, list):
            for material in text_materials:
                if isinstance(material, dict):
                    material_id = str(material.get("id") or material.get("material_id") or "")
                    text = extract_text_from_material(material)
                    if material_id and text:
                        text_by_id[material_id] = text

    cut_index = 1
    cap_index = 1
    seen_segments: set[int] = set()
    for node in walk_json(data):
        if not isinstance(node, dict) or id(node) in seen_segments:
            continue
        start, end = timerange_seconds(node)
        if start is None or end is None or end <= start:
            continue
        material_id = str(node.get("material_id") or node.get("id") or node.get("ref_id") or "")
        text = text_by_id.get(material_id, "")
        if not text:
            text = extract_text_from_material(node) if node.get("type") in {"text", "subtitle", "caption"} else ""
        if text:
            timeline.captions.append(
                Caption(id=f"cap-{cap_index:04d}", start=start, end=end, text=text, track="S1")
            )
            cap_index += 1
        else:
            name = str(node.get("name") or node.get("type") or material_id or f"segment-{cut_index}")
            timeline.cuts.append(
                TimelineItem(
                    id=f"cut-{cut_index:04d}",
                    start=start,
                    end=end,
                    track=str(node.get("track") or node.get("track_type") or "V1"),
                    name=name,
                    source=material_id,
                    kind=str(node.get("type") or "segment"),
                )
            )
            cut_index += 1
        seen_segments.add(id(node))
    timeline.finalize()
    return timeline


def parse_canonical_json(path: Path) -> Timeline:
    data = json.loads(read_text_maybe_compressed(path))
    if data.get("schema") != "nle-timeline-v1":
        return parse_jianying_json(path)
    timeline = Timeline(
        name=data.get("name") or path.stem,
        fps=float(data.get("fps") or DEFAULT_FPS),
        duration=float(data.get("duration") or 0),
        source_path=str(path),
        source_format="canonical-json",
    )
    for item in data.get("cuts", []):
        timeline.cuts.append(
            TimelineItem(
                id=str(item.get("id") or f"cut-{len(timeline.cuts) + 1:04d}"),
                start=float(item.get("start") or 0),
                end=float(item.get("end") or 0),
                track=str(item.get("track") or ""),
                name=str(item.get("name") or ""),
                source=str(item.get("source") or ""),
                source_start=item.get("source_start"),
                source_end=item.get("source_end"),
                kind=str(item.get("kind") or "unknown"),
            )
        )
    for item in data.get("captions", []):
        timeline.captions.append(
            Caption(
                id=str(item.get("id") or f"cap-{len(timeline.captions) + 1:04d}"),
                start=float(item.get("start") or 0),
                end=float(item.get("end") or 0),
                text=str(item.get("text") or ""),
                track=str(item.get("track") or "S1"),
            )
        )
    timeline.warnings.extend(data.get("warnings", []))
    timeline.finalize()
    return timeline


def parse_input(input_path: Path) -> Timeline:
    warnings: list[str] = []
    payload = find_project_payload(input_path, warnings)
    suffix = payload.suffix.lower()
    text_prefix = ""
    if payload.is_file() and suffix in {".xml", ".fcpxml", ".drt", ".prproj"}:
        text_prefix = read_text_maybe_compressed(payload)[:500].lstrip()

    if suffix == ".srt":
        timeline = parse_srt(payload)
    elif suffix in {".fcpxml", ".drt"} or text_prefix.startswith("<fcpxml"):
        timeline = parse_fcpxml(payload)
    elif suffix == ".edl":
        timeline = parse_edl(payload)
    elif suffix in {".json"}:
        timeline = parse_canonical_json(payload)
    elif suffix in {".xml", ".prproj"} or text_prefix.startswith("<"):
        if "<fcpxml" in text_prefix[:100]:
            timeline = parse_fcpxml(payload)
        else:
            timeline = parse_xmeml(payload)
    else:
        raise ValueError(f"Unsupported or opaque input format: {input_path}")
    timeline.warnings = warnings + timeline.warnings
    if input_path != payload:
        timeline.source_path = str(input_path)
    timeline.finalize()
    return timeline


def timeline_to_dict(timeline: Timeline) -> dict[str, Any]:
    return {
        "schema": "nle-timeline-v1",
        "name": timeline.name,
        "fps": timeline.fps,
        "duration": timeline.duration,
        "source_path": timeline.source_path,
        "source_format": timeline.source_format,
        "cuts": [
            {
                "id": item.id,
                "start": item.start,
                "end": item.end,
                "duration": item.duration,
                "track": item.track,
                "name": item.name,
                "source": item.source,
                "source_start": item.source_start,
                "source_end": item.source_end,
                "kind": item.kind,
            }
            for item in timeline.cuts
        ],
        "captions": [
            {
                "id": caption.id,
                "start": caption.start,
                "end": caption.end,
                "duration": caption.duration,
                "track": caption.track,
                "text": caption.text,
            }
            for caption in timeline.captions
        ],
        "warnings": timeline.warnings,
    }


def write_json(timeline: Timeline, path: Path) -> None:
    path.write_text(json.dumps(timeline_to_dict(timeline), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_cutlist_csv(timeline: Timeline, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "track", "kind", "start", "end", "duration", "name", "source", "source_start", "source_end"])
        for item in timeline.cuts:
            writer.writerow([item.id, item.track, item.kind, item.start, item.end, item.duration, item.name, item.source, item.source_start or "", item.source_end or ""])


def write_srt(timeline: Timeline, path: Path) -> None:
    blocks = []
    for index, caption in enumerate(timeline.captions, start=1):
        blocks.append(f"{index}\n{seconds_to_srt(caption.start)} --> {seconds_to_srt(caption.end)}\n{caption.text}")
    path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")


def fcpxml_title(caption: Caption, index: int) -> str:
    return f"""<title name={quoteattr(caption.text + " - 自定")} lane="1" offset="{seconds_to_fcpxml(caption.start)}" ref="r2" duration="{seconds_to_fcpxml(caption.duration)}">
<param name="位置" key="9999/10199/10201/1/100/101" value="0 -340"/>
<param name="对齐" key="9999/10199/10201/2/354/1002961760/401" value="1 (居中)"/>
<text>
  <text-style ref="ts{index}">{escape(caption.text)}</text-style>
</text>
<text-style-def id="ts{index}">
  <text-style font="PingFang SC" fontSize="62" fontFace="Semibold" fontColor="1 1 1 1" bold="1" strokeColor="0.329705 0.329721 0.329713 1" strokeWidth="-1" shadowColor="0 0 0 0.75" shadowOffset="3 315" kerning="1.24" alignment="center"/>
</text-style-def>
</title>"""


def fcpxml_marker(item: TimelineItem, index: int) -> str:
    value = item.name or item.source or f"Cut {index:03d}"
    return f'<marker start="{seconds_to_fcpxml(item.start)}" value={quoteattr(value)} completed="0"/>'


def write_fcpxml(timeline: Timeline, path: Path, project_name: str) -> None:
    duration = seconds_to_fcpxml(max(timeline.duration, 1.0))
    markers = "\n".join(fcpxml_marker(item, index) for index, item in enumerate(timeline.cuts, start=1))
    titles = "\n".join(fcpxml_title(caption, index) for index, caption in enumerate(timeline.captions, start=1))
    body = "\n".join(part for part in (markers, titles) if part)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>

<fcpxml version="1.8">
  <resources>
    <format id="r1" name="FFVideoFormat1080p30" frameDuration="100/3000s" width="1920" height="1080" colorSpace="1-1-1 (Rec. 709)"/>
    <effect id="r2" name="自定" uid=".../Titles.localized/Build In:Out.localized/Custom.localized/Custom.moti"/>
  </resources>
  <library>
    <event name="interchange" uid="{str(uuid.uuid4()).upper()}">
      <project name={quoteattr(project_name)} uid="{str(uuid.uuid4()).upper()}">
        <sequence duration="{duration}" format="r1" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">
          <spine>
            <gap name="interchange-placeholder" offset="0s" duration="{duration}">
{body}
            </gap>
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
"""
    path.write_text(xml, encoding="utf-8")


def write_edl(timeline: Timeline, path: Path) -> None:
    lines = [f"TITLE: {timeline.name}", "FCM: NON-DROP FRAME", ""]
    events = timeline.cuts or [
        TimelineItem(id="cut-0001", start=0, end=max(timeline.duration, 1), name="PLACEHOLDER", source="AX", kind="video")
    ]
    for index, item in enumerate(events, start=1):
        reel = (item.source or item.name or "AX")[:8].replace(" ", "_").upper()
        src_in = seconds_to_timecode(item.source_start if item.source_start is not None else 0, timeline.fps)
        src_out = seconds_to_timecode(
            item.source_end if item.source_end is not None else (item.source_start or 0) + item.duration,
            timeline.fps,
        )
        rec_in = seconds_to_timecode(item.start, timeline.fps)
        rec_out = seconds_to_timecode(item.end, timeline.fps)
        lines.append(f"{index:03d}  {reel:<8} V     C        {src_in} {src_out} {rec_in} {rec_out}")
        lines.append(f"* FROM CLIP NAME: {item.name or reel}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_premiere_xml(timeline: Timeline, path: Path) -> None:
    fps = int(round(timeline.fps or DEFAULT_FPS))
    duration_frames = int(round(max(timeline.duration, 1.0) * fps))
    clipitems = []
    events = timeline.cuts or [
        TimelineItem(id="cut-0001", start=0, end=max(timeline.duration, 1), name="PLACEHOLDER", source="", kind="video")
    ]
    for index, item in enumerate(events, start=1):
        start = int(round(item.start * fps))
        end = int(round(item.end * fps))
        name = escape(item.name or item.source or f"Cut {index:03d}")
        clipitems.append(
            f"""          <clipitem id="clipitem-{index}">
            <name>{name}</name>
            <duration>{max(1, end - start)}</duration>
            <start>{start}</start>
            <end>{end}</end>
            <enabled>TRUE</enabled>
          </clipitem>"""
        )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE xmeml>
<xmeml version="4">
  <sequence id="sequence-1">
    <name>{escape(timeline.name)}</name>
    <duration>{duration_frames}</duration>
    <rate>
      <timebase>{fps}</timebase>
      <ntsc>FALSE</ntsc>
    </rate>
    <media>
      <video>
        <track>
{chr(10).join(clipitems)}
        </track>
      </video>
    </media>
  </sequence>
</xmeml>
"""
    path.write_text(xml, encoding="utf-8")


def write_jianying_json(timeline: Timeline, path: Path) -> None:
    texts = []
    text_segments = []
    for index, caption in enumerate(timeline.captions, start=1):
        material_id = f"text-{index:04d}"
        texts.append({"id": material_id, "type": "text", "content": caption.text})
        text_segments.append(
            {
                "id": f"segment-{index:04d}",
                "material_id": material_id,
                "target_timerange": {
                    "start": int(round(caption.start * 1_000_000)),
                    "duration": int(round(caption.duration * 1_000_000)),
                },
            }
        )
    data = {
        "_note": "Best-effort CapCut/Jianying draft_content-like export. For reliable import, patch a template draft from the same app version.",
        "duration": int(round(max(timeline.duration, 1.0) * 1_000_000)),
        "fps": timeline.fps,
        "materials": {"texts": texts},
        "tracks": [{"type": "text", "segments": text_segments}],
        "source_interchange_schema": "nle-timeline-v1",
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_report(timeline: Timeline, path: Path) -> None:
    lines = [
        f"# Interchange Report",
        "",
        f"- Source: `{timeline.source_path}`",
        f"- Detected format: `{timeline.source_format}`",
        f"- Timeline name: `{timeline.name}`",
        f"- FPS: `{timeline.fps:.3f}`",
        f"- Duration: `{timeline.duration:.3f}s`",
        f"- Cuts: `{len(timeline.cuts)}`",
        f"- Captions: `{len(timeline.captions)}`",
        "",
        "## Fidelity Notes",
        "",
        "- Cut timing and captions are the primary preserved data.",
        "- Generated app files are interchange targets, not guaranteed native lossless project clones.",
        "- Premiere output is FCP7-style XML. Final Cut Pro/Resolve outputs are FCPXML/EDL/SRT based.",
        "- Jianying output is best-effort JSON unless patching a same-version template draft.",
    ]
    if timeline.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in timeline.warnings)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_xml(path: Path) -> None:
    if shutil.which("xmllint") is None:
        return
    import subprocess

    subprocess.run(["xmllint", "--noout", str(path)], check=True)


def export_bundle(timeline: Timeline, out_dir: Path, stem: str) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "timeline": out_dir / f"{stem}.timeline.json",
        "cutlist": out_dir / f"{stem}.cutlist.csv",
        "captions": out_dir / f"{stem}.captions.srt",
        "fcp": out_dir / f"{stem}.fcp.fcpxml",
        "resolve_fcpxml": out_dir / f"{stem}.resolve.fcpxml",
        "resolve_edl": out_dir / f"{stem}.resolve.edl",
        "premiere": out_dir / f"{stem}.premiere.xml",
        "jianying": out_dir / f"{stem}.jianying_draft_content.json",
        "report": out_dir / f"{stem}.report.md",
    }
    write_json(timeline, paths["timeline"])
    write_cutlist_csv(timeline, paths["cutlist"])
    write_srt(timeline, paths["captions"])
    write_fcpxml(timeline, paths["fcp"], f"{stem}_fcp")
    write_fcpxml(timeline, paths["resolve_fcpxml"], f"{stem}_resolve")
    write_edl(timeline, paths["resolve_edl"])
    write_premiere_xml(timeline, paths["premiere"])
    write_jianying_json(timeline, paths["jianying"])
    write_report(timeline, paths["report"])
    validate_xml(paths["fcp"])
    validate_xml(paths["resolve_fcpxml"])
    validate_xml(paths["premiere"])
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract cuts/captions and export NLE interchange files.")
    parser.add_argument("input", type=Path, help="Project/interchange file or folder.")
    parser.add_argument("--out-dir", type=Path, default=Path("outputs"), help="Output directory.")
    parser.add_argument("--stem", help="Output filename stem. Defaults to input stem.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        timeline = parse_input(args.input)
        stem = args.stem or (args.input.stem if args.input.is_file() else args.input.name)
        paths = export_bundle(timeline, args.out_dir, stem)
    except Exception as exc:
        print(f"timeline_interchange: {exc}", file=sys.stderr)
        return 1
    for path in paths.values():
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
