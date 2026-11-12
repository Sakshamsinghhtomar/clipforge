import json
import subprocess

from make_clip import crop_clip, cut_clip, generate_ass_subtitles, render_clip


def make_sample_video(tmp_path):
    source = tmp_path / "sample input.mp4"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "testsrc=size=640x480:rate=25",
            "-f", "lavfi", "-i", "sine=frequency=1000:sample_rate=44100",
            "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", str(source),
        ],
        check=True,
    )
    return source


def probe(path):
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries",
            "format=start_time,duration:stream=width,height", "-of", "json", str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_cut_clip_duration_is_within_half_second(tmp_path):
    sample_video = make_sample_video(tmp_path)
    output = cut_clip(sample_video, 0.4, 1.8, tmp_path / "cut clip.mp4")

    media = probe(output)["format"]
    duration = float(media["duration"])
    assert abs(duration - 1.4) <= 0.5
    assert abs(float(media["start_time"])) <= 0.05


def test_crop_clip_is_vertical_1080_by_1920(tmp_path):
    sample_video = make_sample_video(tmp_path)
    cut = cut_clip(sample_video, 0.4, 1.8, tmp_path / "cut clip.mp4")
    output = crop_clip(cut, tmp_path / "vertical clip.mp4")

    info = probe(output)
    video_stream = next(stream for stream in info["streams"] if "width" in stream)
    assert (video_stream["width"], video_stream["height"]) == (1080, 1920)
    assert abs(float(info["format"]["duration"]) - 1.4) <= 0.5


def test_ass_generator_uses_clip_relative_word_times_and_complete_groups():
    segments = [{"words": [
        {"word": "before", "start": 9.5, "end": 9.9},
        {"word": "Hello", "start": 10.1, "end": 10.3},
        {"word": "there", "start": 10.3, "end": 10.6},
        {"word": "friend", "start": 10.6, "end": 11.0},
        {"word": "how", "start": 11.1, "end": 11.2},
        {"word": "are", "start": 11.2, "end": 11.3},
        {"word": "you", "start": 11.3, "end": 11.6},
        {"word": "outside", "start": 14.8, "end": 15.1},
    ]}]

    ass = generate_ass_subtitles(segments, clip_start=10, clip_end=15)
    events = [line.split(",", 9) for line in ass.splitlines() if line.startswith("Dialogue:")]

    assert len(events) == 2
    assert events[0][1:3] == ["0:00:00.10", "0:00:01.00"]
    assert events[1][1:3] == ["0:00:01.10", "0:00:01.60"]
    assert [len(event[9].split()) for event in events] == [3, 3]
    assert all(not event[1].startswith("-") and "before" not in event[9] and "outside" not in event[9] for event in events)
    assert "Style: Default,Arial,64,&H00FFFFFF" in ass
    assert ",2,80,80,160,1" in ass


def test_ass_generator_omits_caption_with_fewer_than_three_words():
    segments = [{"words": [
        {"word": "Only", "start": 10.1, "end": 10.3},
        {"word": "two", "start": 10.3, "end": 10.6},
    ]}]

    ass = generate_ass_subtitles(segments, clip_start=10, clip_end=15)

    assert not any(line.startswith("Dialogue:") for line in ass.splitlines())


def test_render_clip_burns_ass_in_windows_safe_working_directory(tmp_path):
    sample_video = make_sample_video(tmp_path)
    segments = [{"words": [
        {"word": "One", "start": 0.5, "end": 0.7},
        {"word": "two", "start": 0.7, "end": 0.9},
        {"word": "three", "start": 0.9, "end": 1.1},
        {"word": "four", "start": 1.1, "end": 1.3},
    ]}]
    output = tmp_path / "folder with spaces" / "captioned clip.mp4"

    rendered = render_clip(sample_video, 0.4, 1.8, segments, output)

    info = probe(rendered)
    video_stream = next(stream for stream in info["streams"] if "width" in stream)
    assert (video_stream["width"], video_stream["height"]) == (1080, 1920)
    assert abs(float(info["format"]["duration"]) - 1.4) <= 0.5
    assert not list(output.parent.glob("clipforge_*"))