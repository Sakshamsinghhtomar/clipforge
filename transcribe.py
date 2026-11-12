"""Day 1 spike: video -> timestamped transcript JSON.

Usage:  python transcribe.py path/to/video.mp4 [model_size]
Output: transcripts/<video_name>.json
"""
import json
import sys
import time
from pathlib import Path

from faster_whisper import WhisperModel


def transcribe_video(video_path, model_size="small", output_dir="transcripts"):
    video = Path(video_path)
    if not video.exists():
        raise FileNotFoundError(video)

    print(f"Loading model '{model_size}' (first run downloads it)...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    print(f"Transcribing {video.name} ...")
    start = time.time()
    segments_iter, info = model.transcribe(
        str(video),
        word_timestamps=True,
        vad_filter=True,  # skips silence, faster and fewer hallucinations
    )

    segments = []
    for seg in segments_iter:  # generator: transcription happens here
        segments.append({
            "id": seg.id,
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
            "words": [
                {"word": w.word.strip(), "start": round(w.start, 2), "end": round(w.end, 2)}
                for w in (seg.words or [])
            ],
        })
        print(f"  [{seg.start:7.1f}s] {seg.text.strip()[:70]}")

    elapsed = time.time() - start
    result = {
        "source": video.name,
        "language": info.language,
        "duration": round(info.duration, 2),
        "model": model_size,
        "transcribe_seconds": round(elapsed, 1),
        "segments": segments,
    }

    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"{video.stem}.json"
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    speed = info.duration / elapsed if elapsed else 0
    print("\n--- DONE ---")
    print(f"Language:       {info.language}")
    print(f"Video length:   {info.duration / 60:.1f} min")
    print(f"Time taken:     {elapsed / 60:.1f} min ({speed:.1f}x realtime)")
    print(f"Segments:       {len(segments)}")
    print(f"Saved to:       {out_file}")
    return out_file


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("Usage: python transcribe.py <video_file> [model_size]")
        sys.exit(1)

    video = Path(args[0])
    model_size = args[1] if len(args) > 1 else "small"
    try:
        transcribe_video(video, model_size)
    except FileNotFoundError:
        print(f"File not found: {video}")
        sys.exit(1)


if __name__ == "__main__":
    main()
