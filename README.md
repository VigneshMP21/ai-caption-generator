# 🎬 AI Tanglish Caption Generator for Tamil Videos

An automated Python tool that takes any Tamil audio/video file, transcribes the speech with **millisecond-accurate acoustic timestamps**, converts the text into **natural, modern, conversational Tanglish** (e.g. *"Vanakkam nanbargale, innaiku naama oru super project paaka porom"*), and burns styled, **100% synchronized captions** directly onto the video.

---

## ✨ Features
- **📂 Automatic File Picker**: Running the program instantly opens native Windows File Explorer to select any video.
- **🎯 100% Audio-Video Sync**: Uses Voice Activity Detection (VAD) and cross-attention acoustic alignment (`faster-whisper`) to lock subtitle boundaries to speech down to the millisecond.
- **✨ Dynamic Word-by-Word Highlight**: When the speaker speaks, **that exact word** highlights in a different color inside an opaque background rectangle shape (Alex Hormozi / CapCut / Instagram Reels style)!
- **🗣️ Natural Conversational Tanglish**: Uses AI (Gemini 3.5 Flash) with fallback to an offline phonetic engine to produce readable social-media style Tanglish.
- **🎨 Modern Caption Styling**:
  - **Reels / Shorts Style (Default)**: Bold Segoe UI / Arial with vibrant yellow text, deep black stroke, and subtle drop shadow.
  - **Classic Cinema Style**: Clean white lower-third subtitles.
- **⚡ Zero External Installations**: Uses bundled FFmpeg from `imageio-ffmpeg` — no need to mess with Windows PATH or system environment variables.
- **🚀 Auto-Reveal**: Automatically opens Windows File Explorer and selects your finished video once completed.

---

## 🚀 How to Run

Simply open terminal in this folder and run:

```bash
python main.py
```

1. A file explorer window will open.
2. Select your Tamil video (`.mp4`, `.mkv`, `.mov`, etc.).
3. The program will:
   - Extract audio.
   - Recognize spoken Tamil with millisecond timestamps.
   - Convert to Tanglish.
   - Burn captions into the video.
   - Open File Explorer showing `<filename>_tanglish_captioned.mp4`!

---

## ⚙️ Configuration (`config.py`)

You can customize everything in `config.py`:
- `WHISPER_MODEL_SIZE`: Choose `"tiny"`, `"base"`, `"small"`, or `"medium"`. (Default: `"small"` for high Tamil accuracy).
- `CAPTION_STYLE`: Choose `"reels"` or `"classic"`.
- Font size, colors, outline thickness, and bottom margins.

