import os
import imageio_ffmpeg

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

# Whisper transcription settings
# Choices: "tiny", "base", "small", "medium"
# "small" is the sweet spot for Tamil speech accuracy & speed on CPU
WHISPER_MODEL_SIZE = "small"
WHISPER_DEVICE = "cpu"
WHISPER_COMPUTE_TYPE = "int8"

# Caption Styling
# Available styles: "reels" | "impact"
#   "reels"  → Segoe UI Black, mixed-case, yellow rounded box, black text inside (Image 1 style)
#   "impact" → Impact ALL CAPS, purple rounded box, white text inside (Image 2 style)
CAPTION_STYLE = "impact"

# -------------------------------------------------------------
# DYNAMIC WORD-BY-WORD HIGHLIGHT SETTINGS
# -------------------------------------------------------------
# When enabled, the word being spoken is highlighted with a rounded background box!
WORD_HIGHLIGHT = True
MAX_WORDS_PER_SCREEN = 5          # Maximum words visible at a time for readability

# ------------------------------------------------------------------
# VIDEO RESOLUTION (must match ASS PlayResX/Y)
# ------------------------------------------------------------------
PLAY_RES_X = 1920
PLAY_RES_Y = 1080

# ------------------------------------------------------------------
# HIGHLIGHT BOX GEOMETRY (applies to BOTH styles)
# ------------------------------------------------------------------
HIGHLIGHT_PADDING_H = 18          # Horizontal padding (px) around word inside the box
HIGHLIGHT_PADDING_V = 6           # Vertical padding (px) — TIGHT (was 9 = too much)
HIGHLIGHT_BORDER_RADIUS = 12      # Rounded corner radius in ASS coordinate units

# ------------------------------------------------------------------
# REELS STYLE COLORS  (Image 1 — yellow box, black text)
# ------------------------------------------------------------------
REELS_BOX_COLOR      = "&H0000FFFF"   # Vibrant Yellow  (ASS AABBGGRR)
REELS_BOX_TEXT_COLOR = "&H00000000"   # Black text inside box

# ------------------------------------------------------------------
# IMPACT STYLE COLORS  (Image 2 — purple box, white text)
# ------------------------------------------------------------------
IMPACT_BOX_COLOR      = "&H00CC3273"  # Purple #7332CC → ASS AABBGGRR = CC3273
IMPACT_BOX_TEXT_COLOR = "&H00FFFFFF"  # White text inside box

# ------------------------------------------------------------------
# NORMAL (non-highlighted) WORD COLORS — same for both styles
# ------------------------------------------------------------------
NORMAL_TEXT_COLOR    = "&H00FFFFFF"   # White
NORMAL_OUTLINE_COLOR = "&H00000000"   # Black outline
NORMAL_SHADOW_COLOR  = "&H80000000"   # Semi-transparent drop shadow

# ------------------------------------------------------------------
# CHARACTER WIDTH ESTIMATES (pixels at 1x font size, then scaled)
# Used for word-width estimation to position \p1 rounded rect boxes.
# ------------------------------------------------------------------
# Impact at 48pt on 1080p: average ~22px per char (condensed font)
IMPACT_AVG_CHAR_WIDTH_PX   = 22
# Segoe UI Black at 44pt on 1080p: average ~24px per char
SEGOE_AVG_CHAR_WIDTH_PX    = 24
# Space width in pixels for each font
IMPACT_SPACE_WIDTH_PX      = 10
SEGOE_SPACE_WIDTH_PX       = 11

# ------------------------------------------------------------------
# BASE STYLE DEFINITIONS
# ------------------------------------------------------------------
STYLE_CONFIGS = {
    "reels": {
        "Fontname":      "Segoe UI Black",
        "Fontsize":      22,              # Doubled to 44pt for 1920x1080
        "PrimaryColour": "&H00FFFFFF",    # White
        "OutlineColour": "&H00000000",    # Black outline
        "BackColour":    "&H80000000",    # Semi-transparent shadow
        "Bold":          1,
        "Italic":        0,
        "BorderStyle":   1,
        "Outline":       2.5,
        "Shadow":        1.5,
        "Alignment":     2,               # Bottom-center
        "MarginV":       55,
        "AllCaps":       False,
        "AvgCharWidth":  SEGOE_AVG_CHAR_WIDTH_PX,
        "SpaceWidth":    SEGOE_SPACE_WIDTH_PX,
        "BoxColor":      REELS_BOX_COLOR,
        "BoxTextColor":  REELS_BOX_TEXT_COLOR,
    },
    "impact": {
        "Fontname":      "Impact",
        "Fontsize":      24,              # Doubled to 48pt for 1920x1080
        "PrimaryColour": "&H00FFFFFF",    # White
        "OutlineColour": "&H00000000",    # Black outline
        "BackColour":    "&H80000000",
        "Bold":          0,               # Impact is inherently bold
        "Italic":        0,
        "BorderStyle":   1,
        "Outline":       3.0,             # Strong black outline for Impact style
        "Shadow":        2.0,
        "Alignment":     2,               # Bottom-center
        "MarginV":       55,
        "AllCaps":       True,            # ALL CAPS for Impact style
        "AvgCharWidth":  IMPACT_AVG_CHAR_WIDTH_PX,
        "SpaceWidth":    IMPACT_SPACE_WIDTH_PX,
        "BoxColor":      IMPACT_BOX_COLOR,
        "BoxTextColor":  IMPACT_BOX_TEXT_COLOR,
    },
    "classic": {
        "Fontname":      "Arial",
        "Fontsize":      18,
        "PrimaryColour": "&H00FFFFFF",
        "OutlineColour": "&H00000000",
        "BackColour":    "&H80000000",
        "Bold":          0,
        "Italic":        0,
        "BorderStyle":   1,
        "Outline":       1.8,
        "Shadow":        1.0,
        "Alignment":     2,
        "MarginV":       30,
        "AllCaps":       False,
        "AvgCharWidth":  20,
        "SpaceWidth":    10,
        "BoxColor":      "&H0000FFFF",
        "BoxTextColor":  "&H00000000",
    }
}
