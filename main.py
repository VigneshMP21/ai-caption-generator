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
from core.subtitle_builder import build_caption_events, build_srt_file
from core.video_burner import burn_subtitles_to_video
import config

console = Console()


def select_video_file() -> str:
    """Opens the native Windows File Explorer to let the user select a video file."""
    console.print("\n[bold cyan]📂 Opening File Explorer... Please select your video file.[/bold cyan]")
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_path = filedialog.askopenfilename(
        title="Select Tamil Video File for Tanglish Captions",
        filetypes=[
            ("Video Files", "*.mp4 *.mkv *.mov *.avi *.webm *.flv *.wmv *.m4v"),
            ("All Files", "*.*"),
        ],
    )
    root.destroy()
    return file_path


def main():
    console.print(Panel.fit(
        "[bold green]🎬 AI TANGLISH CAPTION GENERATOR[/bold green]\n"
        "[white]Automatic Tamil Speech Recognition → Natural Tanglish → 100% Synced Captions[/white]",
        border_style="cyan",
    ))

    # ── Step 1: Select video ──────────────────────────────────────────────────
    video_path = select_video_file()
    if not video_path:
        console.print("[yellow]⚠️  No video file selected. Program cancelled.[/yellow]")
        return

    video_path = os.path.abspath(video_path)
    base_dir   = os.path.dirname(video_path)
    file_name  = os.path.splitext(os.path.basename(video_path))[0]

    console.print(f"[bold green]✓ Selected Video:[/bold green] [white]{video_path}[/white]")

    # Paths
    temp_dir         = os.path.join(base_dir, ".temp_captions")
    os.makedirs(temp_dir, exist_ok=True)
    temp_audio_path  = os.path.join(temp_dir, f"{file_name}_audio.wav")
    srt_path         = os.path.join(base_dir, f"{file_name}_tanglish.srt")
    output_video_path = os.path.join(base_dir, f"{file_name}_tanglish_captioned.mp4")

    start_total = time.time()

    try:
        # ── Step 2: Extract audio ─────────────────────────────────────────────
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
            t = p.add_task("[cyan]Extracting high-clarity 16 kHz audio from video...[/cyan]", total=None)
            extract_audio(video_path, temp_audio_path)
            p.update(t, completed=True)
        console.print("[bold green]✓ Audio Extracted Successfully.[/bold green]")

        # ── Step 3: Whisper transcription ──────────────────────────────────────
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
            t = p.add_task(
                f"[cyan]Analyzing Tamil speech & extracting timestamps (Whisper {config.WHISPER_MODEL_SIZE})...[/cyan]",
                total=None,
            )
            transcriber = AudioTranscriber()
            segments = transcriber.transcribe(temp_audio_path)
            p.update(t, completed=True)

        if not segments:
            console.print("[yellow]⚠️  No spoken Tamil speech was detected in the video.[/yellow]")
            return

        console.print(
            f"[bold green]✓ Speech Recognized:[/bold green] Found [cyan]{len(segments)}[/cyan] "
            "speech segments with exact timestamps."
        )

        # ── Step 4: Tamil → Tanglish conversion ───────────────────────────────
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as p:
            t = p.add_task("[cyan]Converting Tamil into natural, colloquial Tanglish...[/cyan]", total=None)
            segments = convert_segments_to_tanglish(segments)
            p.update(t, completed=True)

        # Preview table
        table = Table(title="Generated Tanglish Subtitles Preview", border_style="magenta", show_lines=True)
        table.add_column("Timing",               style="cyan",       width=18)
        table.add_column("Original Tamil",       style="dim white")
        table.add_column("Tanglish Subtitle",    style="bold yellow")
        for seg in segments[:5]:
            table.add_row(
                f"{seg['start']:.2f}s → {seg['end']:.2f}s",
                seg["text"],
                seg.get("tanglish", ""),
            )
        console.print(table)
        if len(segments) > 5:
            console.print(f"[dim]... and {len(segments) - 5} more segments[/dim]")

        # ── Step 5: Build caption events & SRT ───────────────────────────────
        caption_events = build_caption_events(segments)
        build_srt_file(segments, srt_path)
        console.print(
            f"[bold green]✓ Caption Events Built:[/bold green] "
            f"[cyan]{len(caption_events)}[/cyan] chunks, [white]{srt_path}[/white]"
        )

        # ── Step 6: Burn captions into video ──────────────────────────────────
        console.print(
            f"[cyan]⠿ Rendering pixel-perfect [{config.CAPTION_STYLE.upper()}] word-highlight "
            f"captions via Pillow + FFmpeg pipe...[/cyan]"
        )
        console.print("[dim](This processes every frame — please wait ~1-3 minutes)[/dim]")
        burn_subtitles_to_video(video_path, caption_events, output_video_path, config.CAPTION_STYLE)

        elapsed = time.time() - start_total
        console.print(Panel.fit(
            f"[bold green]🎉 SUCCESS! Captioned video created in {elapsed:.1f} s[/bold green]\n\n"
            f"[bold white]Output:[/bold white] [cyan]{output_video_path}[/cyan]\n"
            f"[bold white]Style:[/bold white]  [yellow]{config.CAPTION_STYLE.upper()}[/yellow] "
            f"— word-perfect highlight via Pillow font metrics",
            border_style="green",
        ))

        # Reveal in Explorer
        try:
            subprocess.run(["explorer", f"/select,{output_video_path}"], check=False)
        except Exception:
            pass

    except Exception as e:
        console.print(f"[bold red]❌ Error:[/bold red] {e}")
        import traceback
        console.print(traceback.format_exc())

    finally:
        # Cleanup temp audio
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
