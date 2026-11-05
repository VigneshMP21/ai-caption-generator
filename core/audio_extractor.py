import os
import subprocess
from config import FFMPEG_PATH

def extract_audio(video_path: str, output_wav_path: str) -> str:
    """
    Extracts audio from a video file and converts it to 16kHz mono WAV,
    the optimal format for Whisper speech recognition and VAD.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    dirname = os.path.dirname(output_wav_path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    cmd = [
        FFMPEG_PATH,
        "-y",               # Overwrite existing
        "-i", video_path,   # Input video
        "-vn",              # Disable video recording
        "-acodec", "pcm_s16le",
        "-ar", "16000",     # 16kHz sample rate
        "-ac", "1",         # Mono channel
        output_wav_path
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio extraction failed with error:\n{result.stderr}")

    if not os.path.exists(output_wav_path) or os.path.getsize(output_wav_path) == 0:
        raise RuntimeError("Audio extraction failed: output WAV file is empty or missing.")

    return output_wav_path
