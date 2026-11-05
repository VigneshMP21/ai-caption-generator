import os
import imageio_ffmpeg

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# ---------------------------------------------------------------------------
# Whisper transcription settings
# ---------------------------------------------------------------------------
WHISPER_MODEL_SIZE   = "small"   # tiny | base | small | medium
WHISPER_DEVICE       = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

# ---------------------------------------------------------------------------
# Caption style
# "impact" → Impact ALL-CAPS, purple rounded box  (matches Image 2 reference)
# "reels"  → Segoe UI Black, mixed-case, yellow rounded box (Image 1 reference)
# ---------------------------------------------------------------------------
CAPTION_STYLE = "impact"

# ---------------------------------------------------------------------------
# Word-highlight settings
# ---------------------------------------------------------------------------
WORD_HIGHLIGHT       = True
MAX_WORDS_PER_SCREEN = 5          # max words visible in one chunk

# ---------------------------------------------------------------------------
# Video Safe Area & Automatic Text Wrapping (70% Safe-Width Layout)
# ---------------------------------------------------------------------------
MAX_CAPTION_WIDTH_PERCENT  = 70   # Maximum width for captions (70% of video width)
LEFT_SAFE_MARGIN_PERCENT   = 15   # 15% safe margin on left
RIGHT_SAFE_MARGIN_PERCENT  = 15   # 15% safe margin on right

AUTO_TEXT_WRAPPING         = True # Automatic word-based wrapping
MAX_CAPTION_LINES          = 2    # Maximum caption lines per screen
CAPTION_LINE_SPACING       = 14   # Vertical spacing between wrapped lines (px)
MIN_CAPTION_FONT_SIZE      = 38   # Minimum font size when auto-scaling long words/lines

# ---------------------------------------------------------------------------
# Pillow rendering — default reference resolution
# ---------------------------------------------------------------------------
PLAY_RES_X = 1920
PLAY_RES_Y = 1080

# Highlight box geometry
HIGHLIGHT_PADDING_H     = 18  # horizontal pad (px) around active word
HIGHLIGHT_PADDING_V     = 8   # vertical pad (px) — tight, controlled
HIGHLIGHT_BORDER_RADIUS = 10  # rounded corner radius (px)

# ---------------------------------------------------------------------------
# Per-style configuration (Pillow-native hex colors & base typography)
# ---------------------------------------------------------------------------
STYLE_CONFIGS = {
    # ── IMPACT style (Image 2 reference) ────────────────────────────────────
    "impact": {
        # Font
        "Fontname":          "Impact",
        "FontPx":            70,         # Base pixel size for 1080w video
        "AllCaps":           True,

        # Colors  (hex strings for Pillow)
        "BoxColor":          "#7332CC",  # purple highlight box (#7332CC / #853BDB)
        "BoxTextColor":      "#FFFFFF",  # white text inside box
        "NormalTextColor":   "#FFFFFF",  # white text for other words
        "OutlineColor":      "#000000",  # black stroke
        "OutlineWidth":      5,          # stroke width for normal words (px)
        "ActiveOutlineWidth": 2,         # stroke width for active word on purple box

        # Layout
        "MarginBottom":      120,        # px from canvas bottom to text block bottom
        "LineSpacing":       14,         # extra px between wrapped lines
    },

    # ── REELS style (Image 1 reference) ─────────────────────────────────────
    "reels": {
        "Fontname":          "Segoe UI Black",
        "FontPx":            62,
        "AllCaps":           False,

        "BoxColor":          "#FFFF00",  # yellow highlight box
        "BoxTextColor":      "#000000",  # black text inside box
        "NormalTextColor":   "#FFFFFF",
        "OutlineColor":      "#000000",
        "OutlineWidth":      4,
        "ActiveOutlineWidth": 0,

        "MarginBottom":      110,
        "LineSpacing":       12,
    },

    # ── CLASSIC style ────────────────────────────────────────────────────────
    "classic": {
        "Fontname":          "Arial",
        "FontPx":            52,
        "AllCaps":           False,

        "BoxColor":          "#FFFF00",
        "BoxTextColor":      "#000000",
        "NormalTextColor":   "#FFFFFF",
        "OutlineColor":      "#000000",
        "OutlineWidth":      3,
        "ActiveOutlineWidth": 0,

        "MarginBottom":      90,
        "LineSpacing":       10,
    },
}
