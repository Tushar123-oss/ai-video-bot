#!/usr/bin/env python3
import os, requests, subprocess, sys, time
from pathlib import Path
from gtts import gTTS

# Configuration
SCENE_DURATION = 6          # seconds per scene clip
OUTPUT_DIR = Path("output")
CLIPS_DIR = Path("clips")
SCRIPT_FILE = Path("script.txt")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")
ELEVEN_KEY = os.getenv("ELEVENLABS_API_KEY")  # optional

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

if not PEXELS_KEY:
    print("ERROR: Set PEXELS_API_KEY in environment (GitHub Secrets).")
    sys.exit(1)
if not SCRIPT_FILE.exists():
    print("ERROR: Create script.txt with your script (one line = one scene).")
    sys.exit(1)

def search_pexels_video(query):
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": PEXELS_KEY}
    params = {"query": query, "per_page": 1}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    videos = data.get("videos", [])
    if not videos:
        return None
    files = videos[0].get("video_files", [])
    if not files:
        return None
    files_sorted = sorted(files, key=lambda f: (abs(f.get("width", 0)-1280)))
    return files_sorted[0].get("link")

def download_file(url, dest):
    print(f"Downloading {url} -> {dest}")
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1024*1024):
            if chunk:
                f.write(chunk)

# Read script and split into scenes
with open(SCRIPT_FILE, "r", encoding="utf-8") as f:
    lines = [line.strip() for line in f.readlines() if line.strip()]

if not lines:
    print("No scenes found in script.txt")
    sys.exit(1)

clip_files = []
for i, scene in enumerate(lines, start=1):
    keywords = " ".join(scene.split()[:6])
    print(f"Scene {i}: searching for '{keywords}'")
    video_url = search_pexels_video(keywords)
    if not video_url:
        print("No video found for scene, skipping (will use a 6s black clip).")
        black_clip = CLIPS_DIR / f"black_{i}.mp4"
        subprocess.run([
            "ffmpeg","-y","-f","lavfi","-i",
            f"color=black:s=1280x720:d={SCENE_DURATION}",
            "-c:v","libx264","-t",str(SCENE_DURATION), str(black_clip)
        ], check=True)
        clip_files.append(str(black_clip))
        continue

    raw_path = CLIPS_DIR / f"raw_{i}.mp4"
    download_file(video_url, raw_path)
    trimmed = CLIPS_DIR / f"trimmed_{i}.mp4"
    subprocess.run([
        "ffmpeg","-y","-i", str(raw_path),
        "-ss","0","-t", str(SCENE_DURATION),
        "-vf","scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
        "-c:v","libx264","-preset","fast","-c:a","aac",str(trimmed)
    ], check=True)
    clip_files.append(str(trimmed))
    time.sleep(0.5)

concat_file = CLIPS_DIR / "list.txt"
with open(concat_file, "w", encoding="utf-8") as f:
    for cf in clip_files:
        f.write(f"file '{cf}'\n")

combined = OUTPUT_DIR / "combined.mp4"
subprocess.run([
    "ffmpeg","-y","-f","concat","-safe","0","-i",str(concat_file),
    "-c:v","libx264","-c:a","aac","-preset","fast", str(combined)
], check=True)

script_text = "\n".join(lines)
audio_file = OUTPUT_DIR / "audio.mp3"
tts = gTTS(text=script_text, lang='en')
tts.save(str(audio_file))

final = OUTPUT_DIR / "final.mp4"
subprocess.run([
    "ffmpeg","-y","-i", str(combined), "-i", str(audio_file),
    "-c:v","copy","-c:a","aac","-shortest", str(final)
], check=True)

print("Done! final video at:", final)
