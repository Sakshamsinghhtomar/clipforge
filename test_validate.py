from pick_moments import merge_segments, validate


CHUNKS = [
    {"start": 0, "end": 10},
    {"start": 10, "end": 45},
    {"start": 45, "end": 55},
    {"start": 55, "end": 100},
]
DURATION = 600


def make_candidate(start, end, **overrides):
    candidate = {
        "start": start,
        "end": end,
        "title": "Test clip",
        "hook": "A compelling opening line.",
        "reason": "It stands on its own.",
    }
    candidate.update(overrides)
    return candidate


def test_valid_45_second_clip_is_accepted():
    accepted, rejected = validate([make_candidate(0, 45)], CHUNKS, DURATION)

    assert len(accepted) == 1
    assert accepted[0]["start"] == 0
    assert accepted[0]["end"] == 45
    assert accepted[0]["duration"] == 45
    assert rejected == []


def test_overlapping_second_clip_is_rejected():
    first = make_candidate(0, 45, title="First clip")
    second = make_candidate(10, 55, title="Overlapping clip")

    accepted, rejected = validate([first, second], CHUNKS, DURATION)

    assert [clip["title"] for clip in accepted] == ["First clip"]
    assert len(rejected) == 1
    assert rejected[0][1] == "overlaps a better clip"


def test_10_second_clip_is_rejected():
    accepted, rejected = validate([make_candidate(0, 10)], CHUNKS, DURATION)

    assert accepted == []
    assert len(rejected) == 1
    assert "outside 30-60s" in rejected[0][1]


def test_100_second_clip_is_rejected():
    accepted, rejected = validate([make_candidate(0, 100)], CHUNKS, DURATION)

    assert accepted == []
    assert len(rejected) == 1
    assert "outside 30-60s" in rejected[0][1]


def test_candidate_missing_required_key_is_rejected():
    candidate = make_candidate(0, 45)
    del candidate["reason"]

    accepted, rejected = validate([candidate], CHUNKS, DURATION)

    assert accepted == []
    assert len(rejected) == 1
    assert rejected[0][1] == "missing keys"


def test_candidate_with_non_numeric_start_is_rejected():
    accepted, rejected = validate([make_candidate("not-a-number", 45)], CHUNKS, DURATION)

    assert accepted == []
    assert len(rejected) == 1
    assert rejected[0][1] == "start/end not numbers"


def test_merge_segments_combines_until_minimum_length():
    segments = [
        {"start": 0, "end": 3, "text": "First."},
        {"start": 3, "end": 7, "text": "Second."},
        {"start": 7, "end": 10, "text": "Third."},
    ]

    chunks = merge_segments(segments, min_len=8)

    assert chunks == [{"start": 0, "end": 10, "text": "First. Second. Third."}]


def test_merge_segments_keeps_trailing_short_chunk():
    segments = [
        {"start": 0, "end": 4, "text": "First."},
        {"start": 4, "end": 8, "text": "Second."},
        {"start": 8, "end": 10, "text": "Trailing."},
    ]

    chunks = merge_segments(segments, min_len=8)

    assert chunks == [
        {"start": 0, "end": 8, "text": "First. Second."},
        {"start": 8, "end": 10, "text": "Trailing."},
    ]