# Ringtone Maker

Extract audio from YouTube videos as MP3 for ringtone creation. Uses OpenAI to generate clean, professional filenames (optional).

## Requirements

- **Python 3.7+**
- **FFmpeg** – required for audio conversion (yt-dlp uses it to convert to MP3)
- **OpenAI API Key** (optional) – for AI-generated filenames. Set `OPENAI_API_KEY` env var. Without it, uses a basic cleanup fallback.

### Install FFmpeg

- **macOS (Homebrew):** `brew install ffmpeg`
- **Ubuntu/Debian:** `sudo apt install ffmpeg`
- **Windows:** Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### Using the default video (the one you provided)

```bash
python extract_ringtone.py
```

### Using a custom YouTube URL

```bash
python extract_ringtone.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

### Specify output directory

Edit `extract_ringtone.py` and pass a second argument, or modify the script to accept `--output` for a custom folder.

The MP3 will be saved in the current directory (or your specified output folder) with the video title as the filename.
