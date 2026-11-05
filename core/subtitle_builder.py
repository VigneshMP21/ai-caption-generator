"""
subtitle_builder.py
====================
Builds .srt subtitle files and caption timing events for the Pillow renderer.

The old ASS-based build_ass_file() has been replaced by the Pillow pipeline
in core/caption_renderer.py + core/video_burner.py.

What remains here:
  • get_tanglish_word_timestamps() — maps Whisper acoustic timestamps onto
    Tanglish words using N:M acoustic interpolation when counts differ
  • build_caption_events()         — produces the structured timing data
    consumed by video_burner.py
  • build_srt_file()               — generates a standard .srt export
"""

import math
from typing import List, Dict, Any

import config


# ---------------------------------------------------------------------------
# Time formatters
# ---------------------------------------------------------------------------

def format_srt_time(seconds: float) -> str:
    """HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    hours   = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs    = int(seconds % 60)
    millis  = int(round((seconds - math.floor(seconds)) * 1000))
    if millis >= 1000:
        secs += 1; millis = 0
    if secs >= 60:
        minutes += 1; secs = 0
    if minutes >= 60:
        hours += 1; minutes = 0
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# ---------------------------------------------------------------------------
# Whisper → Tanglish word timestamp mapper
# ---------------------------------------------------------------------------

def get_tanglish_word_timestamps(segment: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Maps Whisper acoustic word timestamps onto the Tanglish words.

    Priority:
    0. Pre-built `tanglish_words` list from tanglish_engine (perfect 1:1)
    1. Direct 1:1 Whisper match
    2. N:M acoustic interpolation using Whisper anchors  ← NEW (fixes sync bug)
    3. Pure proportional character-count fallback
    """
    tanglish_text = segment.get("tanglish", segment.get("text", "")).strip()
    tanglish_text = tanglish_text.replace("{", "(").replace("}", ")")
    words = tanglish_text.split()
    if not words:
        return []

    whisper_words = segment.get("words", [])
    seg_start     = segment["start"]
    seg_end       = segment["end"]
    seg_duration  = max(0.1, seg_end - seg_start)

    # ── 0. Pre-built 1:1 list from tanglish_engine ───────────────────────────
    prebuilt = segment.get("tanglish_words", [])
    if prebuilt and len(prebuilt) == len(words):
        result = []
        for i, item in enumerate(prebuilt):
            w_start = item["start"]
            w_end   = item["end"]
            if i < len(prebuilt) - 1:
                nxt = prebuilt[i + 1]["start"]
                if nxt > w_end:
                    w_end = nxt
            result.append({"word": item["word"], "start": round(w_start, 3), "end": round(w_end, 3)})
        return result

    # ── 1. Perfect 1:1 Whisper match ────────────────────────────────────────
    if whisper_words and len(words) == len(whisper_words):
        result = []
        for i, (tw, ww) in enumerate(zip(words, whisper_words)):
            w_start = ww["start"]
            w_end   = ww["end"]
            if i < len(words) - 1:
                nxt = whisper_words[i + 1]["start"]
                if nxt > w_end:
                    w_end = nxt
            result.append({"word": tw, "start": round(w_start, 3), "end": round(w_end, 3)})
        return result

    # ── 2. N:M acoustic interpolation ────────────────────────────────────────
    # Tanglish word count ≠ Whisper word count.
    # Interpolate between Whisper acoustic anchors so highlights follow the
    # real speech rhythm rather than just equal character-count slices.
    if whisper_words:
        n_tgl  = len(words)
        n_wsp  = len(whisper_words)
        # Build (n_wsp+1) time anchors: starts of each whisper word + end
        anchors = [w["start"] for w in whisper_words] + [seg_end]
        anchors[0] = min(anchors[0], seg_start)
        for k in range(1, len(anchors)):
            if anchors[k] < anchors[k - 1]:
                anchors[k] = anchors[k - 1]

        result = []
        for i, word in enumerate(words):
            pos = i * n_wsp / max(1, n_tgl - 1) if n_tgl > 1 else 0.0
            lo  = int(pos);  hi = min(lo + 1, n_wsp);  frac = pos - lo
            w_start = anchors[lo] * (1 - frac) + anchors[hi] * frac

            if i < n_tgl - 1:
                npos = (i + 1) * n_wsp / max(1, n_tgl - 1)
                nlo  = int(npos); nhi = min(nlo + 1, n_wsp); nfrac = npos - nlo
                w_end = anchors[nlo] * (1 - nfrac) + anchors[nhi] * nfrac
            else:
                w_end = seg_end

            if w_end <= w_start:
                w_end = w_start + max(0.05, seg_duration / n_tgl)

            result.append({"word": word, "start": round(w_start, 3), "end": round(w_end, 3)})
        return result

    # ── 3. Pure proportional fallback (no Whisper word data) ─────────────────
    total_chars  = sum(max(1, len(w)) for w in words)
    result       = []
    current_time = seg_start
    for i, w in enumerate(words):
        w_dur   = (max(1, len(w)) / total_chars) * seg_duration
        w_start = round(current_time, 3)
        w_end   = round(current_time + w_dur, 3)
        if i == len(words) - 1:
            w_end = seg_end
        result.append({"word": w, "start": w_start, "end": w_end})
        current_time += w_dur
    return result


# ---------------------------------------------------------------------------
# Caption event builder (consumed by video_burner.py)
# ---------------------------------------------------------------------------

def build_caption_events(
    segments:  List[Dict[str, Any]],
    max_words: int = config.MAX_WORDS_PER_SCREEN,
) -> List[Dict[str, Any]]:
    """
    Builds a list of caption events from processed segments.

    Each event represents one "chunk" of words shown on screen simultaneously:
    {
        "words":       [ {"word": str, "start": float, "end": float}, … ],
        "chunk_start": float,   # time when chunk first appears
        "chunk_end":   float,   # time when chunk disappears
    }

    The video_burner uses this to determine which words to show at each frame
    and which word to highlight based on the frame's timestamp.
    """
    events = []
    for seg in segments:
        words_timed = get_tanglish_word_timestamps(seg)
        if not words_timed:
            continue

        for c_idx in range(0, len(words_timed), max_words):
            chunk = words_timed[c_idx : c_idx + max_words]
            if not chunk:
                continue

            # Ensure last word's end time covers to segment end (if last chunk)
            chunk_end = chunk[-1]["end"]

            events.append({
                "words":       chunk,
                "chunk_start": chunk[0]["start"],
                "chunk_end":   chunk_end,
            })

    return events


# ---------------------------------------------------------------------------
# SRT export (preserved as-is)
# ---------------------------------------------------------------------------

def build_srt_file(segments: List[Dict[str, Any]], output_path: str) -> str:
    """Builds a standard SubRip (.srt) subtitle file."""
    srt_lines = []
    idx = 1
    for seg in segments:
        text = seg.get("tanglish", seg.get("text", "")).strip()
        if not text:
            continue
        s = format_srt_time(seg["start"])
        e = format_srt_time(seg["end"])
        srt_lines.extend([str(idx), f"{s} --> {e}", text, ""])
        idx += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    return output_path
