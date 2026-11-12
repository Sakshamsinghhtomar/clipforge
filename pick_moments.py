"""Day 2 spike: transcript JSON -> validated clip candidates (via Gemini).

Usage:  python pick_moments.py transcripts/test1.json [num_moments]
Needs:  GEMINI_API_KEY environment variable
Output: moments/<video_name>.json
"""
import json
import os
import re
import sys
import time
from pathlib import Path

# Change this if the model is retired. Check https://aistudio.google.com for current free models.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

MIN_CLIP = 30   # seconds
MAX_CLIP = 60   # seconds
CHUNK_MIN = 8   # merge tiny segments until a chunk is at least this long (seconds)


def merge_segments(segments, min_len=CHUNK_MIN):
    """Merge tiny segments ('Yeah.', 'Okay.') into chunks of >= min_len seconds."""
    chunks, cur = [], None
    for seg in segments:
        if cur is None:
            cur = {"start": seg["start"], "end": seg["end"], "text": seg["text"]}
        else:
            cur["end"] = seg["end"]
            cur["text"] += " " + seg["text"]
        if cur["end"] - cur["start"] >= min_len:
            chunks.append(cur)
            cur = None
    if cur:
        chunks.append(cur)
    return chunks


def build_prompt(chunks, duration, n):
    transcript = "\n".join(f"[{c['start']:.1f}-{c['end']:.1f}] {c['text']}" for c in chunks)
    return f"""You are an editor who finds the best short-form clips (YouTube Shorts / Reels) in a video transcript.

The transcript below is split into lines. Each line starts with [start-end] in seconds.
The video is {duration:.0f} seconds long.

Pick the {n} best moments. Rules:
- Each clip must be between {MIN_CLIP} and {MAX_CLIP} seconds long. Aim for 40 to 60 seconds, because short clips lose their context.
- start and end MUST be copied from the line timestamps in the transcript. Never invent timestamps.
- The clip must make sense on its own, without needing the rest of the video.
- Start at the earliest chunk needed to include the full setup or question; never begin on a reply or on a sentence that continues from the preceding chunk.
- Prefer stretches where one person speaks continuously. Avoid back-and-forth filler like "Yeah." "Okay."
- Clips must not overlap each other.
- Never invent or change dialogue. Only describe what is in the transcript.

Return ONLY a JSON array, no other text. Each item has exactly these keys:
"start" (number), "end" (number), "title" (max 8 words), "hook" (the opening line), "reason" (one sentence on why this works)

Order the array from best to worst.

TRANSCRIPT:
{transcript}
"""


def call_llm(prompt, retries=3):
    from google import genai
    from google.genai import types

    client = genai.Client()  # reads GEMINI_API_KEY from the environment
    for attempt in range(1, retries + 1):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                ),
            )
            return resp.text
        except Exception as e:
            print(f"  LLM call failed (attempt {attempt}/{retries}): {e}")
            if attempt == retries:
                raise
            time.sleep(15 * attempt)


def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)  # strip code fences if present
    data = json.loads(text)
    if isinstance(data, dict):  # model wrapped the list in an object
        for v in data.values():
            if isinstance(v, list):
                return v
    return data


def snap(value, boundaries):
    """Return the boundary closest to value."""
    return min(boundaries, key=lambda b: abs(b - value))


def validate(candidates, chunks, duration):
    """Keep only valid, non-overlapping candidates. Returns (accepted, rejected)."""
    starts = [c["start"] for c in chunks]
    ends = [c["end"] for c in chunks]
    required = {"start", "end", "title", "hook", "reason"}
    accepted, rejected = [], []

    for i, cand in enumerate(candidates, 1):
        if not isinstance(cand, dict):
            rejected.append((f"#{i}", "not an object"))
            continue
        label = f"#{i} {str(cand.get('title', '?'))[:40]}"
        if not required <= cand.keys():
            rejected.append((label, "missing keys"))
            continue
        try:
            s, e = float(cand["start"]), float(cand["end"])
        except (TypeError, ValueError):
            rejected.append((label, "start/end not numbers"))
            continue

        s, e = snap(s, starts), snap(e, ends)  # fix small LLM timing errors
        start_index = starts.index(s)
        opening = chunks[start_index].get("text", "").lstrip()
        opening_word = opening.split(maxsplit=1)[0].strip(".,!?;:\"'()[]").lower() if opening else ""
        reply_openings = {"yeah", "yes", "no", "okay", "ok", "hmm", "right", "exactly"}
        if start_index and (opening[:1].islower() or opening_word in reply_openings):
            s = starts[start_index - 1]
        if e <= s:
            rejected.append((label, "end is before start after snapping"))
        elif s < 0 or e > duration + 1:
            rejected.append((label, "outside video length"))
        elif not (MIN_CLIP <= e - s <= MAX_CLIP):
            rejected.append((label, f"duration {e - s:.0f}s outside {MIN_CLIP}-{MAX_CLIP}s"))
        elif any(s < a["end"] and e > a["start"] for a in accepted):
            rejected.append((label, "overlaps a better clip"))
        else:
            accepted.append({**cand, "start": s, "end": e, "duration": round(e - s, 1)})

    return accepted, rejected


def pick_moments(transcript_path, n=5, output_dir="moments"):
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Set GEMINI_API_KEY first.  PowerShell:  $env:GEMINI_API_KEY='your-key'")

    path = Path(transcript_path)
    data = json.loads(path.read_text(encoding="utf-8"))

    chunks = merge_segments(data["segments"])
    print(f"{len(data['segments'])} segments -> {len(chunks)} chunks")

    prompt = build_prompt(chunks, data["duration"], n)
    print(f"Prompt size: ~{len(prompt) // 4} tokens. Asking {MODEL} ...")
    raw = call_llm(prompt)
    candidates = parse_json(raw)

    accepted, rejected = validate(candidates, chunks, data["duration"])

    print(f"\nAccepted {len(accepted)} / {len(candidates)}")
    for m in accepted:
        print(f"  {m['start']:7.1f}s -> {m['end']:7.1f}s ({m['duration']:.0f}s)  {m['title']}")
        print(f"      hook:   {m['hook']}")
        print(f"      reason: {m['reason']}")
    for label, why in rejected:
        print(f"  REJECTED {label}: {why}")

    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)
    out = out_dir / path.name
    out.write_text(
        json.dumps({"source": data["source"], "model": MODEL, "moments": accepted,
                    "rejected": [{"candidate": l, "reason": w} for l, w in rejected]},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved to {out}")
    return out


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("Usage: python pick_moments.py <transcript.json> [num_moments]")
        sys.exit(1)

    n = int(args[1]) if len(args) > 1 else 5
    try:
        pick_moments(args[0], n)
    except RuntimeError as error:
        print(error)
        sys.exit(1)


if __name__ == "__main__":
    main()
