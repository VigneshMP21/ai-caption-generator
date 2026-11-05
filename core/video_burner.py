import os
import subprocess
import logging
from config import FFMPEG_PATH

logger = logging.getLogger(__name__)

def burn_subtitles_to_video(video_path: str, subtitle_path: str, output_path: str) -> str:
    """
    Burns .ass or .srt subtitles directly onto the video using FFmpeg.
    Ensures Windows path escaping works reliably.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source video not found: {video_path}")
    if not os.path.exists(subtitle_path):
        raise FileNotFoundError(f"Subtitle file not found: {subtitle_path}")

    # Prepare paths
    abs_video = os.path.abspath(video_path)
    abs_sub = os.path.abspath(subtitle_path)
    abs_output = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)

    # In FFmpeg -vf subtitles filter on Windows:
    # Colons and backslashes must be properly escaped
    # Format: C\:/path/to/subtitle.ass
    escaped_sub = abs_sub.replace("\\", "/").replace(":", "\\:")

    # Build FFmpeg command
    # -c:a copy copies the original audio without re-encoding (preserves 100% original quality)
    # -c:v libx264 encodes the video with burned subtitles
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", abs_video,
        "-vf", f"subtitles='{escaped_sub}'",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "21",
        "-c:a", "copy",
        abs_output
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        logger.error(f"FFmpeg burning error: {result.stderr}")
        # Fallback: run from subtitle directory with simple filename to avoid any path escaping issues
        sub_dir = os.path.dirname(abs_sub)
        sub_filename = os.path.basename(abs_sub)
        fallback_cmd = [
            FFMPEG_PATH,
            "-y",
            "-i", abs_video,
            "-vf", f"subtitles={sub_filename}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "21",
            "-c:a", "copy",
            abs_output
        ]
        fb_result = subprocess.run(fallback_cmd, cwd=sub_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if fb_result.returncode != 0:
            raise RuntimeError(f"FFmpeg subtitle burning failed:\n{fb_result.stderr}")

    if not os.path.exists(abs_output) or os.path.getsize(abs_output) == 0:
        raise RuntimeError("Video processing failed: output file is empty or was not created.")

    return abs_output

