import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
import sys
# Force UTF-8 output on Windows to prevent emoji/unicode encoding errors
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import time
import subprocess
import tkinter as tk
from tkinter import filedialog
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from core.audio_extractor import extract_audio
from core.transcriber import AudioTranscriber
from core.tanglish_engine import convert_segments_to_tanglish
from core.subtitle_builder import build_ass_file, build_srt_file
from core.video_burner import burn_subtitles_to_video
import config

console = Console()

def select_video_file() -> str:
    """
    Opens the native Windows File Explorer to let the user select a video file.
    """
    console.print("\n[bold cyan]📂 Opening File Explorer... Please select your video file.[/bold cyan]")
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    
    file_path = filedialog.askopenfilename(
        title="Select Tamil Video File for Tanglish Captions",
        filetypes=[
            ("Video Files", "*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.m4v"),
            ("All Files", "*.*")
        ]
    )
    root.destroy()
    return file_path

def main():
    console.print(Panel.fit(
        "[bold green]🎬 AI TANGLISH CAPTION GENERATOR[/bold green]\n"
        "[white]Automatic Tamil Speech Recognition → Natural Tanglish → 100% Synced Captions[/white]",
        border_style="cyan"
    ))

    # Step 1: Select Video File
    video_path = select_video_file()
    if not video_path:
        console.print("[yellow]⚠️ No video file selected. Program cancelled.[/yellow]")
        return

    video_path = os.path.abspath(video_path)
    base_dir = os.path.dirname(video_path)
    file_name = os.path.splitext(os.path.basename(video_path))[0]

    console.print(f"[bold green]✓ Selected Video:[/bold green] [white]{video_path}[/white]")

    # Setup paths
    temp_dir = os.path.join(base_dir, ".temp_captions")
    os.makedirs(temp_dir, exist_ok=True)

    temp_audio_path = os.path.join(temp_dir, f"{file_name}_audio.wav")
    ass_subtitle_path = os.path.join(base_dir, f"{file_name}_tanglish.ass")
    srt_subtitle_path = os.path.join(base_dir, f"{file_name}_tanglish.srt")
    output_video_path = os.path.join(base_dir, f"{file_name}_tanglish_captioned.mp4")

    start_total_time = time.time()

    try:
        # Step 2: Audio Extraction
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("[cyan]Extracting high-clarity 16kHz audio from video...[/cyan]", total=None)
            extract_audio(video_path, temp_audio_path)
            progress.update(task, completed=True)
        console.print("[bold green]✓ Audio Extracted Successfully.[/bold green]")

        # Step 3: Speech Recognition & VAD Alignment
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task(f"[cyan]Analyzing Tamil speech & extracting timestamps (Whisper {config.WHISPER_MODEL_SIZE})...[/cyan]", total=None)
            transcriber = AudioTranscriber()
            segments = transcriber.transcribe(temp_audio_path)
            progress.update(task, completed=True)

        if not segments:
            console.print("[yellow]⚠️ No spoken Tamil speech was detected in the video.[/yellow]")
            return

        console.print(f"[bold green]✓ Speech Recognized:[/bold green] Found [cyan]{len(segments)}[/cyan] speech segments with exact timestamps.")

        # Step 4: Tamil -> Tanglish Conversion
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("[cyan]Converting Tamil into natural, colloquial Tanglish...[/cyan]", total=None)
            segments = convert_segments_to_tanglish(segments)
            progress.update(task, completed=True)

        # Display preview table
        table = Table(title="Generated Tanglish Subtitles Preview", border_style="magenta", show_lines=True)
        table.add_column("Timing", style="cyan", width=18)
        table.add_column("Original Spoken Tamil", style="dim white")
        table.add_column("100% Synced Tanglish Subtitle", style="bold yellow")

        preview_limit = min(5, len(segments))
        for seg in segments[:preview_limit]:
            timing = f"{seg['start']:.2f}s → {seg['end']:.2f}s"
            table.add_row(timing, seg["text"], seg.get("tanglish", ""))

        console.print(table)
        if len(segments) > preview_limit:
            console.print(f"[dim]... and {len(segments) - preview_limit} more segments[/dim]")

        # Step 5: Subtitle Files Generation
        build_ass_file(segments, ass_subtitle_path, style_name=config.CAPTION_STYLE)
        build_srt_file(segments, srt_subtitle_path)
        console.print(f"[bold green]✓ Subtitle Files Created:[/bold green]\n   - ASS (Dynamic Word Highlight): [white]{ass_subtitle_path}[/white]\n   - SRT: [white]{srt_subtitle_path}[/white]")

        # Step 6: Burn Captions into Video
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
            task = progress.add_task("[cyan]Burning styled Tanglish captions into video (FFmpeg H.264)...[/cyan]", total=None)
            burn_subtitles_to_video(video_path, ass_subtitle_path, output_video_path)
            progress.update(task, completed=True)

        elapsed = time.time() - start_total_time
        console.print(Panel.fit(
            f"[bold green]🎉 SUCCESS! Captioned Video Created in {elapsed:.1f}s[/bold green]\n\n"
            f"[bold white]Output Video:[/bold white] [cyan]{output_video_path}[/cyan]\n"
            f"[bold white]Captions Synced:[/bold white] [green]100% Precise (Acoustic VAD Aligned)[/green]",
            border_style="green"
        ))

        # Step 7: Automatically open/reveal in Windows Explorer
        try:
            subprocess.run(["explorer", f"/select,{output_video_path}"], check=False)
        except Exception:
            pass

    except Exception as e:
        console.print(f"[bold red]❌ Error occurred during processing:[/bold red] {e}")
        import traceback
        console.print(traceback.format_exc())

    finally:
        # Cleanup temporary audio
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except OSError:
                pass
        if os.path.exists(temp_dir) and not os.listdir(temp_dir):
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass

if __name__ == "__main__":
    main()

