"""
video_burner.py
================
Burns Pillow-rendered word-highlight captions into video using FFmpeg raw-frame pipes.

Pipeline
--------
  FFmpeg (decode) ──raw RGB24──► Python (Pillow overlay) ──raw RGB24──► FFmpeg (encode)

FFmpeg decodes the source video to uncompressed RGB24 frames.
Python composites the RGBA caption overlay onto each frame with alpha_composite().
FFmpeg re-encodes the captioned frames back to H.264, copying the original audio.

Performance
-----------
• Caption overlays are cached: each unique (chunk_words, active_word_idx) state
  is rendered by Pillow exactly ONCE. Subsequent frames with the same state just
  do an alpha_composite (< 2 ms per 1920×1080 frame).
• For a 37 s / 25 fps / 1080p video: ~925 frames, ~90 unique states →
  ~90 Pillow renders + 925 composites. Total Python time ≈ 5–10 s.
  FFmpeg encode dominates at ~60 s.
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
    Uses FFmpeg stderr to parse stream metadata.
    """
    cmd = [FFMPEG_PATH, '-hide_banner', '-i', video_path]
    result = subprocess.run(cmd, capture_output=True, text=True, errors='replace')
    text = result.stderr + result.stdout

    # Resolution  e.g. "1920x1080"
    dim = re.search(r'(\d{3,4})x(\d{3,4})', text)
    w, h = (1920, 1080) if not dim else (int(dim.group(1)), int(dim.group(2)))

    # FPS  e.g. "25 fps"  or "29.97 fps"  or "30000/1001 tbr"
    fps_m = re.search(r'(\d+(?:[./]\d+)?)\s*(?:fps|tbr)', text)
    fps = 25.0
    if fps_m:
        raw = fps_m.group(1)
        if '/' in raw:
            num, den = raw.split('/')
            fps = float(num) / float(den)
        else:
            fps = float(raw)

    has_audio = bool(re.search(r'Audio:', text))
    return fps, w, h, has_audio


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
            # Find exact active word
            for i, w in enumerate(words):
                if w["start"] <= t < w["end"]:
                    return words, i
            # Past last word's end but still in chunk → keep last word highlighted
            if words and t >= words[-1]["start"]:
                return words, len(words) - 1
            # In chunk but before first word starts → show chunk, no highlight
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
    Burns pixel-perfect karaoke captions into *video_path* → *output_path*.

    Parameters
    ----------
    video_path     : source video file
    caption_events : list built by subtitle_builder.build_caption_events()
                     [ { "words": [{word,start,end}], "chunk_start", "chunk_end" }, … ]
    output_path    : destination MP4
    style_name     : caption style key (see config.STYLE_CONFIGS)
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source video not found: {video_path}")

    fps, vid_w, vid_h, has_audio = get_video_info(video_path)
    frame_size = vid_w * vid_h * 3   # bytes per RGB24 frame

    style = config.STYLE_CONFIGS.get(style_name, config.STYLE_CONFIGS["reels"])

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # ── Reader: decode video to raw RGB24 frames ─────────────────────────────
    reader_cmd = [
        FFMPEG_PATH, '-hide_banner', '-loglevel', 'error',
        '-i', video_path,
        '-f', 'rawvideo', '-pix_fmt', 'rgb24',
        '-vf', f'scale={vid_w}:{vid_h}',
        'pipe:1',
    ]
    reader = subprocess.Popen(reader_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    # ── Writer: encode processed RGB24 frames + original audio ───────────────
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
        writer_cmd += ['-map', '1:a:0', '-c:a', 'copy']
    writer_cmd += [
        '-c:v', 'libx264', '-preset', 'fast', '-crf', '21',
        output_path,
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
                break   # end of stream

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
        pass   # writer exited early (error handled below)
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

    # ── Error check ───────────────────────────────────────────────────────────
    if writer.returncode not in (0, None):
        err = b"".join(writer_stderr_lines[-30:]).decode("utf-8", errors="replace")
        raise RuntimeError(
            f"FFmpeg encoder failed (exit {writer.returncode}):\n{err}"
        )

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("Output video was not created or is empty.")

    return output_path
