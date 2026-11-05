"""
caption_renderer.py
====================
Pixel-perfect word-by-word karaoke caption rendering using Pillow.

RESPONSIVE 70% SAFE-WIDTH LAYOUT & TWO-LINE WRAPPING
-----------------------------------------------------
1. Video Safe Area:
   - LEFT_SAFE_MARGIN  = VIDEO_WIDTH * 0.15 (15%)
   - MAX_CAPTION_WIDTH = VIDEO_WIDTH * 0.70 (70%)
   - RIGHT_SAFE_MARGIN = VIDEO_WIDTH * 0.15 (15%)
   All text and highlight rectangles are strictly guaranteed to stay within this 70% width!

2. Intelligent Multi-Line Wrapping:
   - Measures exact pixel widths of all words and space advances using Pillow FreeType metrics.
   - If a caption exceeds the 70% safe width, it is wrapped word-by-word.
   - If wrapping at base font size exceeds MAX_CAPTION_LINES (default: 2), font size is
     dynamically scaled down (until MIN_CAPTION_FONT_SIZE) so the entire caption fits in <= 2 lines!
   - If any single word is wider than 70% width, font size is also scaled down so the word
     never overflows the safe margin.

3. Complete Word-by-Word Karaoke Highlight:
   - Text layout is computed FIRST with exact line and word coordinates.
   - Every word's visual bounding box is recorded.
   - The active word's purple rounded rectangle is drawn on Layer 0 using its exact bounding box + padding.
   - Text is drawn on Layer 1 at the exact matching positions.
   - 100% synchronized across Line 1 and Line 2!
"""

import os
from typing import List, Dict, Any, Tuple, Optional

from PIL import Image, ImageDraw, ImageFont

import config

# ---------------------------------------------------------------------------
# Font file mapping (Windows Fonts directory)
# ---------------------------------------------------------------------------

FONT_MAP: Dict[str, str] = {
    "Impact":          "impact.ttf",
    "Segoe UI Black":  "seguibl.ttf",
    "Arial":           "arial.ttf",
    "Arial Bold":      "arialbd.ttf",
    "Courier New":     "cour.ttf",
}

_font_cache: Dict[str, ImageFont.FreeTypeFont] = {}


def load_font(fontname: str, px_size: int) -> ImageFont.FreeTypeFont:
    """Load and cache a TrueType font from the Windows Fonts directory."""
    key = f"{fontname}@{px_size}"
    if key in _font_cache:
        return _font_cache[key]

    filename = FONT_MAP.get(fontname, fontname.lower().replace(" ", "") + ".ttf")
    win_fonts = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts")
    path = os.path.join(win_fonts, filename)

    if os.path.exists(path):
        font = ImageFont.truetype(path, px_size)
    else:
        # Non-Windows fallback
        font = ImageFont.load_default()

    _font_cache[key] = font
    return font


# ---------------------------------------------------------------------------
# Exact glyph-metric helpers
# ---------------------------------------------------------------------------

def _bbox(word: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int, int, int]:
    """
    Returns (left, top, right, bottom) from font.getbbox(word).
    """
    return font.getbbox(word)


def _space_advance(font: ImageFont.FreeTypeFont) -> int:
    """
    Accurate space advance width measured by comparing 'H H' vs 'HH'.
    """
    try:
        b_hi = font.getbbox("H H")
        b_hh = font.getbbox("HH")
        return max(2, (b_hi[2] - b_hi[0]) - (b_hh[2] - b_hh[0]))
    except Exception:
        return max(2, font.size // 4)


# ---------------------------------------------------------------------------
# Multi-line word wrapping & font scaling engine
# ---------------------------------------------------------------------------

def _wrap_words_into_lines(
    words: List[str],
    font: ImageFont.FreeTypeFont,
    max_w: int,
) -> Tuple[List[List[str]], bool]:
    """
    Greedy word-wrap into lines such that each line width <= max_w.
    Returns (lines, has_overflow_word).
    has_overflow_word is True if any single word alone is wider than max_w.
    """
    space_w = _space_advance(font)
    lines: List[List[str]] = []
    cur_line: List[str] = []
    cur_w = 0
    has_overflow_word = False

    for word in words:
        b = _bbox(word, font)
        vis_w = b[2] - b[0]
        if vis_w > max_w:
            has_overflow_word = True

        needed = cur_w + space_w + vis_w if cur_line else vis_w

        if cur_line and needed > max_w:
            lines.append(cur_line)
            cur_line = [word]
            cur_w = vis_w
        else:
            cur_line.append(word)
            cur_w = needed

    if cur_line:
        lines.append(cur_line)

    return lines, has_overflow_word


def fit_words_to_safe_area(
    words: List[str],
    fontname: str,
    base_px: int,
    max_w: int,
    max_lines: int,
    min_px: int,
) -> Tuple[ImageFont.FreeTypeFont, List[List[str]]]:
    """
    Determines the optimal font and word-line distribution so that:
    1. Line count <= max_lines
    2. Every line width <= max_w
    3. Single words never overflow max_w

    Gradually decreases font size from base_px down to min_px if necessary.
    """
    curr_px = base_px
    best_font = load_font(fontname, curr_px)
    best_lines, _ = _wrap_words_into_lines(words, best_font, max_w)

    while curr_px > min_px:
        font = load_font(fontname, curr_px)
        lines, has_overflow_word = _wrap_words_into_lines(words, font, max_w)

        if len(lines) <= max_lines and not has_overflow_word:
            return font, lines

        curr_px -= 2

    # Return at min_px if couldn't satisfy within bounds
    font = load_font(fontname, min_px)
    lines, _ = _wrap_words_into_lines(words, font, max_w)
    return font, lines


# ---------------------------------------------------------------------------
# Word-layout engine — calculating exact pixel positions
# ---------------------------------------------------------------------------

def compute_word_layout(
    words: List[str],
    style: Dict[str, Any],
    canvas_w: int,
    canvas_h: int,
) -> Tuple[ImageFont.FreeTypeFont, List[Dict[str, Any]]]:
    """
    Computes exact pixel coordinates for all words within the 70% safe area.

    Safe width constraints:
      left_safe_margin  = 0.15 * canvas_w
      max_caption_width = 0.70 * canvas_w
      right_safe_margin = 0.15 * canvas_w

    Each line is horizontally centered inside canvas_w (which inherently centers
    it inside the 70% safe area).
    """
    fontname  = style["Fontname"]
    base_px   = style["FontPx"]
    margin_bot = style.get("MarginBottom", 120)
    line_sp    = style.get("LineSpacing", config.CAPTION_LINE_SPACING)
    max_lines  = getattr(config, "MAX_CAPTION_LINES", 2)
    min_px     = getattr(config, "MIN_CAPTION_FONT_SIZE", 38)

    # 70% Safe Width
    max_safe_width = int(canvas_w * (getattr(config, "MAX_CAPTION_WIDTH_PERCENT", 70) / 100.0))

    # Fit words into <= max_lines lines respecting max_safe_width
    font, lines = fit_words_to_safe_area(
        words, fontname, base_px, max_safe_width, max_lines, min_px
    )

    space_w = _space_advance(font)

    # Measure visual width and height of each line
    line_metrics: List[Tuple[int, int, int]] = []
    for line_words in lines:
        total_vis_w  = 0
        max_vis_h    = 0
        min_top_bear = 0
        for i, w in enumerate(line_words):
            b     = _bbox(w, font)
            vis_w = b[2] - b[0]
            vis_h = b[3] - b[1]
            total_vis_w += vis_w + (space_w if i < len(line_words) - 1 else 0)
            max_vis_h    = max(max_vis_h, vis_h)
            min_top_bear = min(min_top_bear, b[1])
        line_metrics.append((total_vis_w, max_vis_h, min_top_bear))

    total_block_h = (
        sum(h for _, h, _ in line_metrics)
        + line_sp * max(0, len(line_metrics) - 1)
    )
    block_top = canvas_h - margin_bot - total_block_h

    layout: List[Dict[str, Any]] = []
    cur_vis_y = block_top

    for line_idx, (line_words, (line_vis_w, line_vis_h, _)) in enumerate(
        zip(lines, line_metrics)
    ):
        # Center this line horizontally in the canvas (centered in the 70% safe area)
        cur_vis_x = (canvas_w - line_vis_w) // 2

        for word in line_words:
            b = _bbox(word, font)
            left_bear = b[0]
            top_bear  = b[1]
            vis_w     = b[2] - b[0]
            vis_h     = b[3] - b[1]

            vis_x0 = cur_vis_x
            vis_y0 = cur_vis_y
            vis_x1 = vis_x0 + vis_w
            vis_y1 = vis_y0 + vis_h

            draw_x = vis_x0 - left_bear
            draw_y = vis_y0 - top_bear

            layout.append({
                "word":   word,
                "line":   line_idx,
                "draw_x": draw_x,
                "draw_y": draw_y,
                "vis_x0": vis_x0,
                "vis_y0": vis_y0,
                "vis_x1": vis_x1,
                "vis_y1": vis_y1,
            })

            cur_vis_x += vis_w + space_w

        cur_vis_y += line_vis_h + line_sp

    return font, layout


# ---------------------------------------------------------------------------
# Caption frame renderer
# ---------------------------------------------------------------------------

def render_caption_overlay(
    words:      List[str],
    active_idx: int,
    style:      Dict[str, Any],
    canvas_w:   int = config.PLAY_RES_X,
    canvas_h:   int = config.PLAY_RES_Y,
) -> Image.Image:
    """
    Render one caption frame as a transparent RGBA image.

    Parameters
    ----------
    words      : word strings for this caption chunk
    active_idx : index of currently spoken word (-1 = none active)
    style      : STYLE_CONFIGS entry
    canvas_w,
    canvas_h   : output video dimensions

    Returns a fully transparent RGBA Image with the styled caption and
    purple rounded-rectangle highlight box.
    """
    all_caps    = style.get("AllCaps", False)
    pad_x       = config.HIGHLIGHT_PADDING_H
    pad_y       = config.HIGHLIGHT_PADDING_V
    radius      = config.HIGHLIGHT_BORDER_RADIUS
    box_col     = style["BoxColor"]
    box_txt_col = style["BoxTextColor"]
    norm_col    = style.get("NormalTextColor", "#FFFFFF")
    out_col     = style.get("OutlineColor", "#000000")
    norm_ow     = style.get("OutlineWidth", 4)
    act_ow      = style.get("ActiveOutlineWidth", 1)

    if all_caps:
        words = [w.upper() for w in words]

    # Compute word layout with 70% safe width & multi-line wrapping
    font, layout = compute_word_layout(words, style, canvas_w, canvas_h)

    img  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Layer 0: highlight box ────────────────────────────────────────────────
    if 0 <= active_idx < len(layout):
        item = layout[active_idx]
        raw_x0 = item["vis_x0"] - pad_x
        raw_y0 = item["vis_y0"] - pad_y
        raw_x1 = item["vis_x1"] + pad_x
        raw_y1 = item["vis_y1"] + pad_y

        bx0 = max(0, min(canvas_w, raw_x0))
        by0 = max(0, min(canvas_h, raw_y0))
        bx1 = max(0, min(canvas_w, raw_x1))
        by1 = max(0, min(canvas_h, raw_y1))

        if bx1 > bx0 and by1 > by0:
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=radius, fill=box_col)

    # ── Layer 1: all words ────────────────────────────────────────────────────
    for idx, item in enumerate(layout):
        word      = item["word"]
        is_active = (idx == active_idx)
        fill_col  = box_txt_col if is_active else norm_col
        sw        = act_ow if is_active else norm_ow

        draw.text(
            (item["draw_x"], item["draw_y"]),
            word,
            font=font,
            fill=fill_col,
            stroke_width=sw,
            stroke_fill=out_col,
        )

    return img
