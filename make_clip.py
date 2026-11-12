"""Render vertical, captioned clips from video and transcript data."""
import subprocess
import tempfile
from pathlib import Path


def cut_clip(video_path, start, end, output_path):
    """Cut and encode a clip, seeking before the input so timestamps restart at zero."""
    if start < 0 or end <= start:
        raise ValueError("clip end must be greater than a non-negative start")

    video = Path(video_path).resolve()
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{start:.3f}",
        "-i", str(video),
        "-t", f"{end - start:.3f}",
        "-map", "0:v:0", "-map", "0:a:0?",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-movflags", "+faststart",
        str(output),
    ]
    subprocess.run(command, check=True)
    return output


def crop_clip(input_path, output_path):
    """Center-crop a video to fill a 1080x1920 frame."""
    source = Path(input_path).resolve()
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-map", "0:v:0", "-map", "0:a:0?",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-movflags", "+faststart",
        str(output),
    ]
    subprocess.run(command, check=True)
    return output


def _ass_time(seconds):
    centiseconds = max(0, int(round(seconds * 100)))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    whole_seconds, fractional = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{whole_seconds:02d}.{fractional:02d}"


def _caption_groups(words, words_per_line):
    groups = []
    offset = 0
    while offset < len(words):
        remaining = len(words) - offset
        if remaining <= 5:
            group = words[offset:]
            if len(group) < 3:
                if groups and len(groups[-1]) + len(group) <= 5:
                    groups[-1].extend(group)
                else:
                    break
            else:
                groups.append(group)
            break

        group_size = words_per_line
        if 0 < remaining - group_size < 3:
            group_size = remaining - 3
        groups.append(words[offset:offset + group_size])
        offset += group_size
    return groups


def _escape_ass_text(text):
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


def generate_ass_subtitles(segments, clip_start, clip_end, words_per_line=4):
    """Build bottom-centered ASS captions using only words fully inside the clip."""
    if clip_end <= clip_start:
        raise ValueError("clip end must be greater than clip start")
    if not 3 <= words_per_line <= 5:
        raise ValueError("words_per_line must be between 3 and 5")

    words = []
    for segment in segments:
        for word in segment.get("words") or []:
            start, end = float(word["start"]), float(word["end"])
            text = word.get("word", "").strip()
            if text and start >= clip_start and end <= clip_end and end > start:
                words.append({"word": text, "start": start, "end": end})

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "ScaledBorderAndShadow: yes",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,64,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,3,1,2,80,80,160,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for group in _caption_groups(words, words_per_line):
        start = max(0, group[0]["start"] - clip_start)
        end = min(clip_end - clip_start, group[-1]["end"] - clip_start)
        if end <= start:
            continue
        text = " ".join(_escape_ass_text(word["word"]) for word in group)
        lines.append(
            f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Default,,0,0,0,,{text}"
        )
    return "\n".join(lines) + "\n"


def render_clip(video_path, clip_start, clip_end, segments, output_path):
    """Cut, center-crop, caption, and encode one phone-ready MP4."""
    if clip_start < 0 or clip_end <= clip_start:
        raise ValueError("clip end must be greater than a non-negative start")

    video = Path(video_path).resolve()
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    ass_text = generate_ass_subtitles(segments, clip_start, clip_end)
    filter_graph = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,subtitles=captions.ass"
    )

    with tempfile.TemporaryDirectory(prefix="clipforge_", dir=output.parent) as work_dir:
        (Path(work_dir) / "captions.ass").write_text(ass_text, encoding="utf-8")
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-ss", f"{clip_start:.3f}",
            "-i", str(video),
            "-t", f"{clip_end - clip_start:.3f}",
            "-vf", filter_graph,
            "-map", "0:v:0", "-map", "0:a:0?",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-movflags", "+faststart",
            str(output),
        ]
        subprocess.run(command, cwd=work_dir, check=True)
    return output