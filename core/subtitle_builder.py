"""
subtitle_builder.py
====================
Builds .ass and .srt subtitle files with dynamic word-by-word highlight.

Word Highlight Architecture
----------------------------
Two distinct layers are emitted per active-word frame:

  Layer 0  →  DrawBox Dialogue  — a filled rounded-rectangle drawn via ASS \\p1
              The box is placed at the computed pixel position of the active word.

  Layer 1  →  Text Dialogue     — the full chunk text, where the active word uses
              the HighlightText style (coloured text, no outline, clean) and every
              other word uses the Normal style (white + black outline).

This gives true rounded corners (unlike BorderStyle 3 which is a plain rectangle)
and very tight, controllable padding.

Word-width estimation
---------------------
ASS doesn't expose glyph metrics at build time.  We estimate pixel widths using
per-font average character-width constants defined in config.py.  The estimate is
intentionally slightly generous so the box never clips a character.
"""

import math
from typing import List, Dict, Any, Tuple

import config

# ---------------------------------------------------------------------------
# Time formatters
# ---------------------------------------------------------------------------

def format_ass_time(seconds: float) -> str:
    """H:MM:SS.cs  (centiseconds, 2 decimal places)"""
    if seconds < 0:
        seconds = 0.0
    hours   = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs    = int(seconds % 60)
    centis  = int(round((seconds - math.floor(seconds)) * 100))
    if centis >= 100:
        secs   += 1; centis = 0
    if secs   >= 60:
        minutes += 1; secs   = 0
    if minutes >= 60:
        hours  += 1; minutes = 0
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def format_srt_time(seconds: float) -> str:
    """HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    hours   = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs    = int(seconds % 60)
    millis  = int(round((seconds - math.floor(seconds)) * 1000))
    if millis >= 1000:
        secs   += 1; millis = 0
    if secs   >= 60:
        minutes += 1; secs   = 0
    if minutes >= 60:
        hours  += 1; minutes = 0
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# ---------------------------------------------------------------------------
# Word-timestamp mapper
# ---------------------------------------------------------------------------

def get_tanglish_word_timestamps(segment: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Maps Whisper acoustic word timestamps onto the Tanglish words with precision.

    Strategy (in priority order):
    1. Perfect 1:1 match  — use Whisper timestamps directly (most accurate).
    2. N:M acoustic interpolation — when counts differ, linearly interpolate
       between Whisper word boundary anchors so the highlight still follows the
       actual voice rhythm (much better than a plain character-count split).
    3. Pure proportional fallback — no Whisper words at all; distribute evenly
       by character count across the segment duration.
    """
    seg_start    = segment["start"]
    seg_end      = segment["end"]
    seg_duration = max(0.1, seg_end - seg_start)

    # ── 0. Authoritative per-word acoustic mapping from tanglish_engine ───────
    # These are the exact words that will be displayed, paired 1:1 with Whisper's
    # acoustic timestamps.  We MUST use them even if the segment-level sentence
    # happens to contain a different number of words — otherwise the highlight
    # drifts away from the actual voice (the old bug).
    tanglish_words_prebuilt = segment.get("tanglish_words", [])
    if tanglish_words_prebuilt:
        result = []
        prev_start = seg_start
        for i, item in enumerate(tanglish_words_prebuilt):
            w_start = min(max(item["start"], prev_start), seg_end)
            w_end   = min(max(item["end"], w_start), seg_end)
            # Bridge tiny inter-word gaps so captions don't flicker
            if i < len(tanglish_words_prebuilt) - 1:
                nxt = min(max(tanglish_words_prebuilt[i + 1]["start"], w_start), seg_end)
                if nxt > w_end:
                    w_end = nxt
            result.append({"word": item["word"], "start": round(w_start, 3), "end": round(w_end, 3)})
            prev_start = w_start
        return result

    tanglish_text = segment.get("tanglish", segment.get("text", "")).strip()
    # Escape curly braces (ASS override tag delimiters)
    tanglish_text = tanglish_text.replace("{", "(").replace("}", ")")
    words = tanglish_text.split()
    if not words:
        return []

    whisper_words = segment.get("words", [])

    # ── 1. Perfect 1:1 match  ────────────────────────────────────────────────
    if whisper_words and len(words) == len(whisper_words):
        result = []
        for i, (tw, ww) in enumerate(zip(words, whisper_words)):
            w_start = ww["start"]
            w_end   = ww["end"]
            # Bridge tiny inter-word gaps so captions don't flicker
            if i < len(words) - 1:
                next_start = whisper_words[i + 1]["start"]
                if next_start > w_end:
                    w_end = next_start
            result.append({"word": tw, "start": round(w_start, 3), "end": round(w_end, 3)})
        return result

    # ── 2. N:M acoustic interpolation using Whisper anchors ─────────────────
    # Build a normalised [0..1] timeline from Whisper word boundaries.
    # Each Tanglish word index i is mapped to a floating-point position in that
    # timeline so the highlight moves at the real acoustic rhythm even when the
    # Tamil→Tanglish conversion changes the word count.
    if whisper_words:
        n_tgl = len(words)
        n_wsp = len(whisper_words)

        # Build boundary list: [wsp_start_0, wsp_start_1, ..., wsp_end_last]
        # This gives us (n_wsp + 1) time anchors.
        anchors = [w["start"] for w in whisper_words] + [seg_end]
        # Ensure anchors are non-decreasing and start at seg_start
        anchors[0] = min(anchors[0], seg_start)
        for k in range(1, len(anchors)):
            if anchors[k] < anchors[k - 1]:
                anchors[k] = anchors[k - 1]

        result = []
        for i, word in enumerate(words):
            # Map tanglish word index → floating whisper anchor index
            # i=0 → anchor 0, i=(n_tgl-1) → anchor n_wsp
            anchor_pos = i * n_wsp / max(1, n_tgl - 1) if n_tgl > 1 else 0.0
            lo = int(anchor_pos)
            hi = min(lo + 1, n_wsp)
            frac = anchor_pos - lo

            w_start = anchors[lo] * (1.0 - frac) + anchors[hi] * frac

            # End = start of next tanglish word (using same interpolation)
            if i < n_tgl - 1:
                next_pos = (i + 1) * n_wsp / max(1, n_tgl - 1)
                nlo = int(next_pos)
                nhi = min(nlo + 1, n_wsp)
                nfrac = next_pos - nlo
                w_end = anchors[nlo] * (1.0 - nfrac) + anchors[nhi] * nfrac
            else:
                w_end = seg_end

            if w_end <= w_start:
                w_end = w_start + max(0.05, seg_duration / n_tgl)

            result.append({"word": word, "start": round(w_start, 3), "end": round(w_end, 3)})
        return result

    # ── 3. Pure proportional fallback (no Whisper word data) ────────────────
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
# Pixel-width estimator
# ---------------------------------------------------------------------------

def estimate_word_px_width(word: str, avg_char_px: int, space_px: int) -> int:
    """
    Estimate the rendered pixel width of *word* (no trailing space).
    Uses per-character average width from config; slightly over-estimates
    so the highlight box is never too tight.
    """
    if not word:
        return 0
    return max(1, len(word)) * avg_char_px


def estimate_line_px_width(words: List[str], avg_char_px: int, space_px: int) -> int:
    """Total pixel width of a list of words joined by single spaces."""
    total = sum(estimate_word_px_width(w, avg_char_px, space_px) for w in words)
    total += space_px * max(0, len(words) - 1)
    return total


# ---------------------------------------------------------------------------
# ASS draw-command: filled rounded rectangle
# ---------------------------------------------------------------------------

def rounded_rect_draw(x0: int, y0: int, x1: int, y1: int, r: int) -> str:
    """
    Returns an ASS \\p1 drawing command string for a filled rounded rectangle.
    Uses cubic Bézier corners.  Coordinates are in ASS drawing units (pixels
    when \\p1 and ScaledBorderAndShadow:yes with no extra scaling).

    ASS draw coordinate origin is top-left of the PlayRes canvas.
    """
    r = min(r, (x1 - x0) // 2, (y1 - y0) // 2)   # clamp radius
    # Shorthand points
    top    = y0
    bot    = y1
    left   = x0
    right  = x1
    # Bézier corner weight (control points identical to anchor for 90° arcs)
    cmd = (
        f"m {left+r} {top} "
        f"l {right-r} {top} "
        f"b {right} {top} {right} {top} {right} {top+r} "
        f"l {right} {bot-r} "
        f"b {right} {bot} {right} {bot} {right-r} {bot} "
        f"l {left+r} {bot} "
        f"b {left} {bot} {left} {bot} {left} {bot-r} "
        f"l {left} {top+r} "
        f"b {left} {top} {left} {top} {left+r} {top}"
    )
    return cmd


# ---------------------------------------------------------------------------
# ASS styles block builder
# ---------------------------------------------------------------------------

def _build_ass_styles(style: Dict[str, Any], fontsize: int, fontname: str) -> List[str]:
    """
    Returns the [V4+ Styles] lines for Normal, HighlightText, and DrawBox styles.

    Normal        — white text, strong black outline, used for non-active words.
    HighlightText — coloured text (box text colour) with NO outline, sits on top
                    of the Layer 0 DrawBox rectangle.
    DrawBox       — invisible text size-1 style used only to anchor \\p1 drawing.
    """
    box_text_color = style["BoxTextColor"]

    # Normal style: white + outline + shadow
    normal = (
        f"Style: Normal,{fontname},{fontsize},"
        f"{config.NORMAL_TEXT_COLOR},{config.NORMAL_TEXT_COLOR},"
        f"{config.NORMAL_OUTLINE_COLOR},{config.NORMAL_SHADOW_COLOR},"
        f"{style['Bold']},{style['Italic']},0,0,"
        f"100,100,0,0,"
        f"1,{style['Outline'] * 1.8:.1f},{style['Shadow'] * 1.5:.1f},"
        f"{style['Alignment']},25,25,{style['MarginV'] * 2},1"
    )

    # HighlightText: same font, box-text colour, NO outline (box provides the bg)
    highlight_text = (
        f"Style: HighlightText,{fontname},{fontsize},"
        f"{box_text_color},{box_text_color},"
        f"&H00000000,&H00000000,"
        f"{style['Bold']},{style['Italic']},0,0,"
        f"100,100,0,0,"
        f"1,0,0,"
        f"{style['Alignment']},25,25,{style['MarginV'] * 2},1"
    )

    # DrawBox: tiny font, alignment 7 (top-left absolute), no outline/shadow
    # PrimaryColour = box fill colour
    draw_box = (
        f"Style: DrawBox,{fontname},1,"
        f"{style['BoxColor']},{style['BoxColor']},"
        f"&H00000000,&H00000000,"
        f"0,0,0,0,"
        f"100,100,0,0,"
        f"1,0,0,"
        f"7,0,0,0,1"   # Alignment 7 = top-left; zero margins so \pos is absolute
    )

    return [normal, highlight_text, draw_box]


# ---------------------------------------------------------------------------
# Per-word box coordinate calculator
# ---------------------------------------------------------------------------

def compute_word_box(
    chunk_words: List[str],
    active_idx: int,
    style: Dict[str, Any],
    fontsize: int,
) -> Tuple[int, int, int, int]:
    """
    Returns (x0, y0, x1, y1) in ASS canvas pixels for the highlight box
    around chunk_words[active_idx].

    Layout assumptions
    ------------------
    * Text is bottom-center aligned (Alignment=2).
    * The text baseline sits at:  canvas_y = PlayResY - MarginV*2
    * Font height (ascent + descent) ≈ fontsize * 1.15
    * The entire chunk renders as a single line centered at x = PlayResX/2.
    """
    avg_char_px = style["AvgCharWidth"]
    space_px    = style["SpaceWidth"]
    pad_h       = config.HIGHLIGHT_PADDING_H
    pad_v       = config.HIGHLIGHT_PADDING_V

    # Estimate total line pixel width
    line_px = estimate_line_px_width(chunk_words, avg_char_px, space_px)

    # X start of the whole line (centered)
    cx = config.PLAY_RES_X // 2
    line_x0 = cx - line_px // 2

    # Accumulate X offset to find the active word's left edge
    word_x_offset = 0
    for i, w in enumerate(chunk_words):
        if i == active_idx:
            break
        word_x_offset += estimate_word_px_width(w, avg_char_px, space_px) + space_px

    word_px = estimate_word_px_width(chunk_words[active_idx], avg_char_px, space_px)
    word_x0 = line_x0 + word_x_offset

    # Box X bounds
    box_x0 = word_x0 - pad_h
    box_x1 = word_x0 + word_px + pad_h

    # Box Y bounds — text sits at the bottom of the canvas
    margin_v   = style["MarginV"] * 2
    font_h     = int(fontsize * 1.15)   # approximate glyph height
    # Bottom of text block (above margin)
    text_bot   = config.PLAY_RES_Y - margin_v
    text_top   = text_bot - font_h

    box_y0 = text_top - pad_v
    box_y1 = text_bot + pad_v

    return box_x0, box_y0, box_x1, box_y1


# ---------------------------------------------------------------------------
# Main .ass file builder
# ---------------------------------------------------------------------------

def build_ass_file(
    segments: List[Dict[str, Any]],
    output_path: str,
    style_name: str = config.CAPTION_STYLE,
) -> str:
    """
    Builds an Advanced SubStation Alpha (.ass) subtitle file.

    When WORD_HIGHLIGHT is True:
      * Layer 0: DrawBox Dialogue — \\p1 filled rounded rectangle under the word
      * Layer 1: Text Dialogue    — full chunk text with active word in HighlightText

    When WORD_HIGHLIGHT is False:
      * Simple static lines using Normal style.
    """
    style    = config.STYLE_CONFIGS.get(style_name, config.STYLE_CONFIGS["reels"])
    fontsize = style["Fontsize"] * 2    # scale up for 1920×1080
    fontname = style["Fontname"]
    all_caps = style.get("AllCaps", False)
    radius   = config.HIGHLIGHT_BORDER_RADIUS

    style_lines = _build_ass_styles(style, fontsize, fontname)

    ass_header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {config.PLAY_RES_X}",
        f"PlayResY: {config.PLAY_RES_Y}",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ] + style_lines + [
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    ass_lines = list(ass_header)
    max_chunk = config.MAX_WORDS_PER_SCREEN

    for seg in segments:
        words = get_tanglish_word_timestamps(seg)
        if not words:
            continue

        # Apply ALL CAPS if the style demands it
        if all_caps:
            for w in words:
                w["word"] = w["word"].upper()

        if not getattr(config, "WORD_HIGHLIGHT", True):
            # --- Static line mode (no highlight) ---
            line_text = " ".join(w["word"] for w in words)
            s = format_ass_time(seg["start"])
            e = format_ass_time(seg["end"])
            ass_lines.append(f"Dialogue: 0,{s},{e},Normal,,0,0,0,,{line_text}")
            continue

        # --- Word-by-word highlight mode ---
        for c_idx in range(0, len(words), max_chunk):
            chunk     = words[c_idx : c_idx + max_chunk]
            chunk_end = chunk[-1]["end"]

            chunk_word_strings = [item["word"] for item in chunk]

            for i, active_word in enumerate(chunk):
                w_start = active_word["start"]
                w_end   = chunk[i + 1]["start"] if i < len(chunk) - 1 else chunk_end
                if w_end <= w_start:
                    w_end = w_start + 0.1

                s = format_ass_time(w_start)
                e = format_ass_time(w_end)

                # ── Layer 0: rounded rectangle ──────────────────────────────
                bx0, by0, bx1, by1 = compute_word_box(chunk_word_strings, i, style, fontsize)
                draw_cmd = rounded_rect_draw(bx0, by0, bx1, by1, radius)
                # \p1 activates drawing mode; \p0 ends it.
                # \pos(0,0) anchors the drawing origin at the canvas top-left
                # (DrawBox style has Alignment 7 so \pos is relative to that corner).
                draw_text = f"{{\\p1\\pos(0,0)}}{draw_cmd}{{\\p0}}"
                ass_lines.append(f"Dialogue: 0,{s},{e},DrawBox,,0,0,0,,{draw_text}")

                # ── Layer 1: text ───────────────────────────────────────────
                # Active word → HighlightText style; others → Normal style
                tokens = []
                for j, item in enumerate(chunk):
                    token = item["word"]
                    if j == i:
                        tokens.append(f"{{\\rHighlightText}}{token}{{\\rNormal}}")
                    else:
                        tokens.append(token)

                full_line = " ".join(tokens)
                ass_lines.append(f"Dialogue: 1,{s},{e},Normal,,0,0,0,,{full_line}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(ass_lines))

    return output_path


# ---------------------------------------------------------------------------
# .srt file builder
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
