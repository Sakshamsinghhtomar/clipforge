Stage 1: `transcribe_video()` and `pick_moments()` expose reusable pipeline steps; each CLI `main()` parses arguments and delegates.
`merge_segments()` groups short transcript segments until they reach the minimum duration and retains a final short remainder.
Pytest covers the moment validator and chunk merging without invoking Gemini or downloading a transcription model.
Stage 2: The prompt requests the earliest chunk containing a complete setup and forbids reply or continuation openings.
Validation backs up a reply/continuation opening by one chunk and reapplies the existing duration limits.