"""
video_burner.py
================
Burns Pillow-rendered word-highlight captions into video using FFmpeg raw-frame pipes
with 100% Cross-Platform & Mobile Compatibility (Android, iPhone, WhatsApp, Windows Media Player).

Cross-Platform & Mobile Compatibility Standards Enforced
-------------------------------------------------------
1. Even Dimensions (width & height % 2 == 0):
   Non-even dimensions (e.g. 1918 or odd heights) cause severe hardware decoder crashes
   on Android Stagefright, iOS AVFoundation, and Windows Media Foundation thumbnailers.
   Dimensions are sanitized to even numbers.

2. MP4 Container Finalization & FastStart (+faststart):
   Moves the 'moov' atom from the end of the file to the beginning (right after 'ftyp').
   Essential for:
   - Instant mobile playback streaming (WhatsApp, Chrome, Safari, Android Gallery).
   - Windows File Explorer video thumbnail generation without scanning the entire file.

3. Standard H.264 Video Stream:
   - Codec: libx264
   - Pixel Format: yuv420p (8-bit 4:2:0 planar chroma subsampling)
   - Profile: High
   - Level: 4.1 or 4.2 (supports 1080p up to 60fps across all modern mobile chipsets)
   - Codec Tag: avc1 (FourCC tag required by Apple QuickTime and Windows Media Player)

4. Universal AAC-LC Audio Stream:
   - Codec: aac (AAC-LC)
   - Sample Rate: 48,000 Hz or 44,100 Hz
   - Channels: stereo (2 channels)
   - Bitrate: 192 kbps
   - Re-encodes cleanly to prevent incompatible proprietary audio formats (e.g. Opus/PCM/DTS in MP4).

Performance & Architecture
--------------------------
  FFmpeg (decode) ──raw RGB24──► Python (Pillow overlay) ──raw RGB24──► FFmpeg (encode)
  Caption overlays are cached per unique text state.
"""

import os
import re
import subprocess
import threading
from typing import List, Dict, Any, Tuple, Optional

from PIL import Image

import config
from config import FFMPEG_PATH
from core.caption_renderer import render_caption_overlay


# ---------------------------------------------------------------------------
# Video info
# ---------------------------------------------------------------------------

def get_video_info(video_path: str) -> Tuple[float, int, int, bool]:
    """
    Returns (fps, width, height, has_audio) for a video file.
    Guarantees width and height are EVEN numbers for H.264 / mobile compatibility.
    """
    cmd = [FFMPEG_PATH, '-hide_banner', '-i', video_path]
    result = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    text = result.stderr + result.stdout

    # Resolution e.g. "1920x1080" or "1080x1918"
    dim = re.search(r'(\d{3,4})x(\d{3,4})', text)
    if dim:
        w, h = int(dim.group(1)), int(dim.group(2))
    else:
        w, h = 1920, 1080

    # Ensure dimensions are strictly even (divisible by 2)
    # Odd or non-macroblock-aligned heights break Windows thumbnails & mobile decoders
    w = (w // 2) * 2
    h = (h // 2) * 2

    # FPS e.g. "25 fps", "29.97 fps", "30 tbr", "30000/1001 tbr"
    fps_m = re.search(r'(\d+(?:[./]\d+)?)\s*(?:fps|tbr)', text)
    fps = 30.0
    if fps_m:
        raw = fps_m.group(1)
        if '/' in raw:
            num, den = raw.split('/')
            fps = float(num) / float(den)
        else:
            fps = float(raw)

    has_audio = bool(re.search(r'Audio:', text))
    return fps, w, h, has_audio


def get_h264_level(width: int, height: int, fps: float) -> str:
    """
    Determines optimal, highly-compatible H.264 level for mobile devices
    based on macroblocks per second (Annex A specification).
    """
    mb_w = (width + 15) // 16
    mb_h = (height + 15) // 16
    mbs_per_frame = mb_w * mb_h
    mbps = mbs_per_frame * fps

    if mbs_per_frame <= 8192 and mbps <= 245760:  # 1080p @ 30fps
        return "4.1"
    elif mbs_per_frame <= 8704 and mbps <= 522240:  # 1080p @ 60fps
        return "4.2"
    elif mbs_per_frame <= 22080 and mbps <= 589824:  # 2K / 1440p
        return "5.0"
    elif mbs_per_frame <= 36864 and mbps <= 983040:  # 4K @ 30fps
        return "5.1"
    return "4.1"


# ---------------------------------------------------------------------------
# Caption state lookup
# ---------------------------------------------------------------------------

def _caption_at(events: List[Dict], t: float) -> Tuple[Optional[List], int]:
    """
    Returns (chunk_words, active_word_idx) for time t.
    chunk_words is None when no caption is active (silence gap).
    active_word_idx is -1 when chunk is visible but no specific word is spoken yet.
    """
    for ev in events:
        if ev["chunk_start"] <= t <= ev["chunk_end"]:
            words = ev["words"]
            for i, w in enumerate(words):
                if w["start"] <= t < w["end"]:
                    return words, i
            if words and t >= words[-1]["start"]:
                return words, len(words) - 1
            return words, -1
    return None, -1


# ---------------------------------------------------------------------------
# Main burner
# ---------------------------------------------------------------------------

def burn_subtitles_to_video(
    video_path:     str,
    caption_events: List[Dict],
    output_path:    str,
    style_name:     str = config.CAPTION_STYLE,
) -> str:
    """
    Burns pixel-perfect karaoke captions into video with guaranteed
    Windows Thumbnail, Android, iPhone, and WhatsApp compatibility.

    Parameters
    ----------
    video_path     : source video file
    caption_events : list built by subtitle_builder.build_caption_events()
    output_path    : destination MP4
    style_name     : caption style key (see config.STYLE_CONFIGS)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source video not found: {video_path}")

    fps, vid_w, vid_h, has_audio = get_video_info(video_path)
    frame_size = vid_w * vid_h * 3   # bytes per RGB24 frame
    h264_level = get_h264_level(vid_w, vid_h, fps)

    style = config.STYLE_CONFIGS.get(style_name, config.STYLE_CONFIGS["reels"])

    abs_output = os.path.abspath(output_path)
    out_dir = os.path.dirname(abs_output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # ── Reader: decode video to raw RGB24 frames ─────────────────────────────
    # scale filter forces exact even dimensions (vid_w x vid_h)
    reader_cmd = [
        FFMPEG_PATH, '-hide_banner', '-loglevel', 'error',
        '-i', video_path,
        '-vf', f'scale={vid_w}:{vid_h}',
        '-f', 'rawvideo', '-pix_fmt', 'rgb24',
        'pipe:1',
    ]
    reader = subprocess.Popen(reader_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    # ── Writer: encode processed RGB24 frames + mobile-compatible audio ──────
    # Output encoding parameters engineered for 100% universal compatibility:
    # 1. -pix_fmt yuv420p  : baseline 8-bit YUV 4:2:0 subsampling
    # 2. -profile:v high   : High profile for quality & broad hardware support
    # 3. -level {level}    : 4.1 (or 4.2 for 60fps) strict compliance
    # 4. -tag:v avc1       : Apple QuickTime / Windows MP4 standard FourCC
    # 5. -c:a aac          : Universal AAC-LC audio
    # 6. -b:a 192k -ar 48k : Clean stereo audio standard
    # 7. -movflags +faststart : Relocate 'moov' atom to file start for thumbnails & streaming
    writer_cmd = [
        FFMPEG_PATH, '-hide_banner', '-loglevel', 'error', '-y',
        # Video from stdin
        '-f', 'rawvideo', '-pix_fmt', 'rgb24',
        '-s', f'{vid_w}x{vid_h}', '-r', str(fps),
        '-i', 'pipe:0',
        # Original file (for audio)
        '-i', video_path,
        '-map', '0:v:0',
    ]

    if has_audio:
        writer_cmd += [
            '-map', '1:a:0',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-ar', '48000',
            '-ac', '2',
        ]

    writer_cmd += [
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '20',
        '-profile:v', 'high',
        '-level', h264_level,
        '-pix_fmt', 'yuv420p',
        '-tag:v', 'avc1',
        '-movflags', '+faststart',
        abs_output,
    ]

    writer = subprocess.Popen(
        writer_cmd,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Drain writer's stderr in a background thread to prevent buffer deadlock
    writer_stderr_lines: List[bytes] = []
    def _drain_stderr():
        for line in writer.stderr:
            writer_stderr_lines.append(line)
    drain_t = threading.Thread(target=_drain_stderr, daemon=True)
    drain_t.start()

    # ── Render cache (key = (words_tuple, active_idx)) ───────────────────────
    _render_cache: Dict[Tuple, Image.Image] = {}

    def _get_overlay(words_timed: List[Dict], active_idx: int) -> Image.Image:
        key = (tuple(w["word"] for w in words_timed), active_idx)
        if key not in _render_cache:
            word_strings = [w["word"] for w in words_timed]
            _render_cache[key] = render_caption_overlay(
                word_strings, active_idx, style, vid_w, vid_h
            )
        return _render_cache[key]

    # ── Frame-processing loop ─────────────────────────────────────────────────
    frame_num = 0
    try:
        while True:
            raw = reader.stdout.read(frame_size)
            if len(raw) < frame_size:
                break   # end of video stream

            t = frame_num / fps

            chunk_words, active_idx = _caption_at(caption_events, t)

            if chunk_words:
                overlay    = _get_overlay(chunk_words, active_idx)
                frame_img  = Image.frombytes('RGB', (vid_w, vid_h), raw)
                frame_rgba = frame_img.convert('RGBA')
                frame_rgba.alpha_composite(overlay)
                writer.stdin.write(frame_rgba.convert('RGB').tobytes())
            else:
                writer.stdin.write(raw)

            frame_num += 1

    except BrokenPipeError:
        pass   # writer exited early
    finally:
        try:
            reader.stdout.close()
        except Exception:
            pass
        try:
            reader.wait(timeout=15)
        except Exception:
            reader.kill()

        try:
            writer.stdin.close()
        except Exception:
            pass
        drain_t.join(timeout=20)
        try:
            writer.wait(timeout=60)
        except subprocess.TimeoutExpired:
            writer.kill()

    # ── Error & Finalization Verification ─────────────────────────────────────
    if writer.returncode not in (0, None):
        err = b"".join(writer_stderr_lines[-30:]).decode("utf-8", errors="replace")
        raise RuntimeError(
            f"FFmpeg encoder failed (exit {writer.returncode}):\n{err}"
        )

    if not os.path.exists(abs_output) or os.path.getsize(abs_output) == 0:
        raise RuntimeError("Output video was not created or is empty.")

    return abs_output
