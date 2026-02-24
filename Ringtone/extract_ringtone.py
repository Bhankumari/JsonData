#!/usr/bin/env python3
"""
Extract audio (MP3) from YouTube videos for ringtone creation.
Uses OpenAI to generate a clean, descriptive filename.
"""

import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

import yt_dlp
import sys


def generate_best_filename(title: str) -> str:
    """
    Use OpenAI to generate a clean, professional filename from a YouTube title.
    Removes promotional text, emoji, and formatting; produces a concise ringtone name.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        # Fallback: sanitize manually (no emoji, remove promotional text)
        clean = re.sub(r"\[.*?\]|\(.*?\)", "", title)
        clean = re.sub(r"[｜|]", " - ", clean)
        clean = re.sub(r"[^\w\s\-\.]", "", clean)
        clean = re.sub(r"\s*-\s*-+\s*", " - ", clean)  # collapse multiple hyphens
        clean = re.sub(r"\s+", " ", clean).strip(" -")
        return clean[:80] if clean else "ringtone"

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You generate short, clean filenames for ringtone MP3 files. "
                "Output ONLY the filename (no path, no .mp3 extension). "
                "Remove promotional text like 'Download Link', emoji, extra pipes/symbols. "
                "Use format: 'Song Name - Artist or Context' or similar. "
                "Use ASCII-safe characters, spaces and hyphens only. Max 60 chars.",
            },
            {
                "role": "user",
                "content": f"Generate the best filename for this YouTube title: {title}",
            },
        ],
        max_tokens=80,
    )
    name = response.choices[0].message.content.strip()
    name = re.sub(r"\.mp3$", "", name, flags=re.I)
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    return name[:80] if name else "ringtone"


def generate_youtube_metadata(title: str) -> tuple[str, str, str]:
    """
    Use OpenAI to generate YouTube-optimized title, description, and hashtags.
    
    Returns:
        (youtube_title, description, hashtags_string)
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        desc = (
            f"Ringtone from: {title}\n\n"
            "You can download this ringtone using BGM Ringtone app available on Play Store.\n\n"
            "#ringtone #BGM #music"
        )
        return title[:100], desc, "#ringtone #mp3 #bgm #music"

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You generate YouTube upload metadata for ringtone/BGM re-uploads. "
                "Respond in this exact format (no labels, use --- as separator):\n"
                "TITLE\n(max 100 chars, catchy, SEO-friendly)\n"
                "---\n"
                "DESCRIPTION\n(2-4 short paragraphs: intro, what it is, call-to-action. "
                "MUST include: 'You can download this ringtone using BGM Ringtone app available on Play Store.' "
                "Do NOT mention or include any download link. Hashtags at end.)\n"
                "---\n"
                "HASHTAGS\n(space-separated: #ringtone #SongName #BGM etc, 10-15 tags)",
            },
            {
                "role": "user",
                "content": f"Original video title: {title}\n\nGenerate YouTube title, description (include BGM Ringtone app from Play Store, no download links), and hashtags.",
            },
        ],
        max_tokens=500,
    )
    text = response.choices[0].message.content.strip()
    parts = [p.strip() for p in text.split("---") if p.strip()]
    yt_title = (parts[0].split("\n")[0][:100]) if parts else title[:100]
    description = (
        parts[1]
        if len(parts) > 1
        else f"Ringtone: {title}\n\nYou can download this ringtone using BGM Ringtone app available on Play Store.\n\n#ringtone #BGM #music"
    )
    hashtags = parts[2] if len(parts) > 2 else "#ringtone #mp3 #bgm #music"
    return yt_title, description, hashtags


def _safe_folder_name(name: str) -> str:
    """Make a string safe for use as a folder name."""
    safe = re.sub(r'[<>:"/\\|?*]', "", name)
    return safe.strip() or "ringtone"


def _add_ringtone_to_json(project_root: Path, display_name: str, filename: str) -> None:
    """Add ringtone entry to New Ringtones (and All Ringtones) in Ringtone.json."""
    json_path = project_root / "Ringtone.json"
    if not json_path.exists():
        return
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    if "New Ringtones" not in data:
        data["New Ringtones"] = []
    if "All Ringtones" not in data:
        data["All Ringtones"] = []
    # GitHub raw URL: New%20Ringtones/filename.mp3 (quote filename for spaces/special chars)
    url_path = f"New%20Ringtones/{quote(filename, safe='-.')}"
    ringtone_url = f"https://github.com/Bhankumari/BGM-Ringtone-app/raw/main/{url_path}"
    entry = {"name": display_name, "ringtone": ringtone_url}
    # Remove existing entry with same name to avoid duplicates
    data["New Ringtones"] = [e for e in data["New Ringtones"] if e.get("name") != display_name]
    data["New Ringtones"].insert(0, entry)
    data["All Ringtones"] = [e for e in data["All Ringtones"] if e.get("name") != display_name]
    data["All Ringtones"].insert(0, entry)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_audio_as_mp3(url: str, output_dir: str = ".", use_openai: bool = True) -> tuple[str, str, str | None, str]:
    """
    Download audio and thumbnail, save each ringtone in its own folder.
    Replaces previous thumbnail and .youtube.txt on re-run.
    Creates output_dir/ringtone_name/ with .mp3, thumbnail, and .youtube.txt.

    Returns:
        (path to MP3, original video title, path to thumbnail or None, ringtone display name)
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    base_path = Path(output_dir)
    output_template = str(base_path / "%(id)s.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": output_template,
        "writethumbnail": True,
        "quiet": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info is None:
            raise ValueError("Could not extract video info")

        video_id = info.get("id", "audio")
        title = info.get("title", "ringtone")
        temp_path = base_path / f"{video_id}.mp3"

        thumb_path = None
        for ext in (".webp", ".jpg", ".png"):
            p = base_path / f"{video_id}{ext}"
            if p.exists():
                thumb_path = p
                break

        best_name = generate_best_filename(title) if use_openai else _safe_folder_name(title)[:60]
        folder_path = base_path / best_name
        folder_path.mkdir(parents=True, exist_ok=True)

        # Replace previous thumbnail and .youtube.txt on re-run
        for old_file in (folder_path / f"{best_name}.png", folder_path / f"{best_name}.youtube.txt"):
            if old_file.exists():
                old_file.unlink()

        final_path = folder_path / f"{best_name}.mp3"
        if temp_path.exists():
            temp_path.rename(final_path)

        final_thumb = None
        if thumb_path:
            png_path = folder_path / f"{best_name}.png"
            if thumb_path.suffix.lower() == ".png":
                thumb_path.rename(png_path)
            else:
                from PIL import Image
                Image.open(thumb_path).save(png_path, "PNG")
                thumb_path.unlink()
            final_thumb = png_path

        display_name = best_name.replace("-", " ").strip()
        return str(final_path), title, str(final_thumb) if final_thumb else None, display_name


def main():
    default_url = "https://youtu.be/o8yYglqmmqw?si=_wfy9L_dCWEv7PZS"
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]

    url = args[0] if args else default_url
    use_openai = "--no-openai" not in flags

    if use_openai and not os.environ.get("OPENAI_API_KEY"):
        print("Tip: Set OPENAI_API_KEY for AI-generated filenames (otherwise using fallback cleanup)")

    print(f"Extracting audio from: {url}")
    print("Downloading and converting to MP3...")

    try:
        script_dir = Path(__file__).resolve().parent
        output_path, video_title, thumb_path, display_name = extract_audio_as_mp3(
            url, output_dir=str(script_dir), use_openai=use_openai
        )
        print(f"\nDone! MP3 saved to: {output_path}")
        if thumb_path:
            print(f"Thumbnail saved to: {thumb_path}")

        if os.environ.get("OPENAI_API_KEY"):
            yt_title, description, hashtags = generate_youtube_metadata(video_title)
        else:
            yt_title, description, hashtags = (
                video_title[:100],
                f"Ringtone: {video_title}\n\nYou can download this ringtone using BGM Ringtone app available on Play Store.\n\n#ringtone #BGM",
                "#ringtone #mp3 #bgm #music",
            )

        meta_path = Path(output_path).with_suffix(".youtube.txt")
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(f"{yt_title}\n\n{description}\n\n{hashtags}\n")
        print(f"YouTube metadata saved to: {meta_path}")
        print(f"\n  Title: {yt_title}\n  Description: (see file)\n  Hashtags: {hashtags}")

        # Copy to New Ringtones and add to Ringtone.json
        project_root = Path(__file__).resolve().parent.parent
        new_ringtones_dir = project_root / "New Ringtones"
        new_ringtones_dir.mkdir(parents=True, exist_ok=True)
        mp3_path = Path(output_path)
        filename = mp3_path.name
        dest_mp3 = new_ringtones_dir / filename
        shutil.copy2(mp3_path, dest_mp3)
        print(f"Copied to New Ringtones: {dest_mp3}")
        _add_ringtone_to_json(project_root, display_name, filename)
        print("Added to Ringtone.json (New Ringtones)")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
