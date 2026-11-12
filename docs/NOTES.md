Stage 1: `transcribe_video()` and `pick_moments()` expose reusable pipeline steps; each CLI `main()` parses arguments and delegates.
`merge_segments()` groups short transcript segments until they reach the minimum duration and retains a final short remainder.
Pytest covers the moment validator and chunk merging without invoking Gemini or downloading a transcription model.
Stage 2: The prompt requests the earliest chunk containing a complete setup and forbids reply or continuation openings.
Validation backs up a reply/continuation opening by one chunk and reapplies the existing duration limits.
Stage 3: FFmpeg cuts with `-ss` before input, center-crops to 1080x1920, and encodes H.264/yuv420p/AAC.
ASS captions use only words inside the clip and shift word times relative to its start; the renderer resolves a relative ASS filename from a temporary working directory.
Media tests generate a short source and probe rendered dimensions/duration; ASS tests check timing, clipping, and 3-5-word grouping.