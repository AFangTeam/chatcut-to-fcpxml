#!/usr/bin/env bash
# Synthesize throwaway media with ffmpeg, then run the full author -> validate pipeline.
# Use this to check the scripts work on your machine before pointing them at a real project.
# Nothing here touches Final Cut Pro; it only writes into this examples/ folder.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL="$(dirname "$HERE")"
MEDIA="$HERE/media"

command -v ffmpeg  >/dev/null || { echo "ffmpeg not found — install it first"; exit 1; }
command -v ffprobe >/dev/null || { echo "ffprobe not found — install it first"; exit 1; }

mkdir -p "$MEDIA"

echo "==> synthesizing media"
# A-roll: 1920x1080, 29.97fps, 12s, stereo 48k
ffmpeg -y -loglevel error \
  -f lavfi -i "testsrc2=size=1920x1080:rate=30000/1001:duration=12" \
  -f lavfi -i "sine=frequency=220:sample_rate=48000:duration=12" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -ac 2 -ar 48000 -shortest \
  "$MEDIA/aroll.mov"

# B-roll: 1920x1080, 25fps, 6s, NO audio (exercises the truthful hasAudio="0" path)
ffmpeg -y -loglevel error \
  -f lavfi -i "smptebars=size=1920x1080:rate=25:duration=6" \
  -c:v libx264 -pix_fmt yuv420p -an \
  "$MEDIA/broll.mov"

# Music: audio only, 44.1k stereo, 15s
ffmpeg -y -loglevel error \
  -f lavfi -i "sine=frequency=440:sample_rate=44100:duration=15" \
  -c:a aac -ac 2 -ar 44100 \
  "$MEDIA/music.m4a"

echo "==> writing manifest.demo.json (absolute paths, probed durations)"
python3 - "$HERE" <<'PY'
import json, subprocess, sys
from pathlib import Path

here = Path(sys.argv[1])
media = here / "media"

def probe_duration(p):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(p)],
        capture_output=True, text=True, check=True)
    return out.stdout.strip()

m = json.loads((here / "manifest.example.json").read_text(encoding="utf-8"))
m["project"]["library_bundle"] = str(here / "ChatCutHandoffDemo.fcpbundle")
for key, filename in (("aroll", "aroll.mov"), ("broll", "broll.mov"), ("music", "music.m4a")):
    path = media / filename
    m["assets"][key]["path"] = str(path)
    m["assets"][key]["duration_s"] = probe_duration(path)

(here / "manifest.demo.json").write_text(
    json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"  {here / 'manifest.demo.json'}")
PY

echo "==> author_fcpxml.py"
python3 "$SKILL/scripts/author_fcpxml.py" "$HERE/manifest.demo.json" "$HERE/demo.fcpxml"

echo "==> validate_fcpxml.py"
python3 "$SKILL/scripts/validate_fcpxml.py" "$HERE/demo.fcpxml"

echo
echo "Done. Open it in Final Cut Pro with:  open '$HERE/demo.fcpxml'"
echo "Import into a FRESHLY NAMED library, then verify visually — a clean exit code proves nothing."
