---
name: chatcut-to-fcpxml
description: Clone a ChatCut project into Final Cut Pro via FCPXML with frame accuracy — cuts, multi-track overlays, zoom moves (static punch-ins and keyframed slow pushes), music/SFX with volumes and fades, and native iTT captions. Use this skill whenever a user wants to export, hand off, convert, or "open in Final Cut Pro / FCP" a ChatCut project or timeline, wants an .fcpxml file, or complains that an FCPXML import into FCP dropped media, looks wrong, or lost zooms/captions. Also use it to verify an FCPXML import inside Final Cut Pro.
license: MIT
---

# ChatCut → Final Cut Pro (FCPXML) handoff

Rebuild a ChatCut timeline as an editable FCP project. Everything in this skill was verified against a real Final Cut Pro import (FCP 12.x) — including the failure modes. The two rules that make or break the result:

1. **FCP fails silently.** A successful XML import proves nothing: assets vanish without warnings, transforms compound unexpectedly, captions restyle themselves. Always verify the imported project visually and with the Inspector — never by exit code.
2. **Declare media truthfully.** Every `<asset>` must state its real dimensions, frame rate, and audio presence, taken from `ffprobe` — not copied from the sequence format. Lying (even accidentally) triggers silent drops.

## Workflow

### 1. Inventory the ChatCut project

Get the full timeline truth from the ChatCut MCP tools:

- `read_project` (view: timeline) → every track's items with `fromFrame / durationInFrames / sourceStartFromInSeconds`, geometry (`left/top/width/height`), `decibelAdjustment`, fades, and effect entries (zooms with magnification + shape).
- `read_captions` with no frame window and a large `limit` → the authoritative caption pages (text + start/end frames). Window reads truncate pages at the edges; don't trust them.
- If `read_project` is temporarily unavailable (backend pool congestion), `manage_media_pool`, `read_captions`, and rendered-frame checks (`view_timeline_frames`) each use different backend paths and can fill most gaps.

### 2. Decide the target with the user

These are preferences, not constants — ask, don't assume:

- **Canvas & aspect**: same as the ChatCut canvas, or letterboxed into a different delivery aspect (e.g. 9:16 content inside a 1:2 canvas)? If letterboxing, use conform `fit` and anchor overlays to the **picture rect**, not the canvas (see compatibility notes; `fill` is unreliable).
- **Frame rate**: if the ChatCut timeline is nominally 30fps but the master footage is really 29.97 (30000/1001), author everything at `frames × 1001/30000s` — frame counts then map 1:1 with zero drift. Same idea for 25/50/24 material. Check the real source rate with ffprobe first.
- **Captions**: native iTT captions (exact timing/line breaks, but FCP applies its own styling), FCP titles (styleable but no background panels), a sidecar SRT, or none. iTT is the default recommendation; set expectations that burned-in caption *looks* never survive the trip.
- **Which layers**: some things don't translate (ChatCut shaders/LUTs, plugin transitions). Offer per-layer choices: rebuild, pre-render to a movie, or omit-and-report.

### 3. Collect media locally

FCPXML references local files. For each asset:

- Prefer the user's original local files (frame-accurate, no recompression).
- ChatCut-only assets (generated music, uploads): download via `request_asset_download`.
- Motion Graphics: render server-side with `export_motion_graphic_prores` → ProRes 4444 **with alpha**. Note it renders at the **timeline item's display size**, not the project canvas — so placement in FCP needs only a position offset, no scale. The output carries a silent PCM track: declare `hasAudio="1"` (truthfully) or FCP silently drops the asset *and every clip connected in the same gap*.
- `ffprobe` every file and record width/height/frame-rate/pix_fmt/audio channels/sample rate/duration. These feed the manifest.

### 4. Author the FCPXML

Write a `manifest.json` (schema: [references/manifest-schema.md](references/manifest-schema.md)) describing project, assets, clips, and captions, then run:

```bash
python3 scripts/author_fcpxml.py manifest.json output.fcpxml
```

The script handles the verified-correct patterns: per-asset formats, gap-anchored spine with positive/negative lanes, conform `fit`, static and keyframed transform scales (zoom cloning), cover/full-bleed geometry, volume + fades nested legally, iTT captions with overlap clamping, and a dedicated library bundle path so imports can't pollute an open library.

Zoom cloning specifics (all verified in FCP):

- **Instant punch-in (e.g. 150%)** → static `scale` on the clip. It compounds with conform `fit` as a center-anchored multiply — exactly a punch-in.
- **Slow push (e.g. 1.0→1.12)** → `scale_keyframes`. Keyframe times are in **source-time coordinates** (clip `start` … `start + duration`); the script converts from clip-relative frames for you. Linear interpolation confirmed: a mid-clip Inspector readback matches the theoretical value.
- A zoom that starts mid-item in ChatCut → split that clip into two asset-clips in the manifest at the zoom boundary.

### 5. Validate statically

```bash
python3 scripts/validate_fcpxml.py output.fcpxml
```

Checks structure, resource refs, media existence, and validates against FCP's own DTD when installed. DTD pass ≠ import success — it only catches malformed XML. Two DTD traps the script's patterns already avoid: `fadeIn/fadeOut` must nest inside a `<param name="amount">` (not directly under `adjust-volume`), and `<text placement=...>` is no longer a legal attribute.

### 6. Verify inside Final Cut Pro

`open output.fcpxml` and import into a **freshly named library** (never an existing one — same-named projects in two libraries cause you to verify the wrong timeline). Then run this checklist, fixing the XML and re-importing until every line passes:

1. **Project specs** in the viewer header: canvas, fps, audio layout; total duration matches `duration_frames` exactly (frame math: TC `mm:ss:ff` at your rate).
2. **Cut spots**: pick 3–5 landmark edits, park the playhead on each, confirm the TC equals the expected frame and the clip name/duration in the Inspector matches the manifest.
3. **Zooms**: select a pushed clip — keyframe diamonds visible; park mid-push and check the Inspector scale equals the interpolated value. Select a punch-in clip — scale reads exactly (e.g. 150.0%).
4. **Overlay geometry**: read one converted `position` back from the Inspector before trusting the batch — position XML units are **1% of canvas height each** (e.g. 38.4 px/unit on a 3840-tall canvas). Compare rendered frames at landmarks against ChatCut renders of the same frames.
5. **Audio**: every music/SFX clip present at the right offset (silent-drop check!), one volume read back in dB.
6. **Captions**: caption lane present, page count right, spot-check 3 pages' text and in/out times.

Automating this with computer-use? See the tips at the end of [references/compatibility.md](references/compatibility.md) (synthetic-click pitfalls, playhead positioning via the timeline ruler).

### 7. Deliver

Ship the `.fcpxml` next to a `Media/` folder containing every referenced file (or document absolute paths if referencing in place), plus a short compatibility report: what cloned exactly, what's approximated (e.g. caption styling), what was omitted.

## Known limits (state these up front)

- iTT captions keep text/timing/line breaks but render in FCP's own caption style — fonts, sizes, and background panels do not carry over.
- ChatCut shaders/filters/LUTs and plugin transitions have no FCPXML equivalent: rebuild in FCP, pre-render, or omit.
- Cross-frame-rate sources (24/25 fps material on a 29.97 timeline) import fine — FCP conforms them — but frame-exact *source* trims quantize to the source's own frame grid.

## Reference files

- [references/compatibility.md](references/compatibility.md) — every verified FCP behavior: silent-drop table, position units, conform/transform compounding, letterbox math, caption fidelity, DTD traps, keyframe recipes, verification techniques. **Read before authoring anything non-trivial.**
- [references/manifest-schema.md](references/manifest-schema.md) — the manifest.json format for `author_fcpxml.py`.
- [examples/manifest.example.json](examples/manifest.example.json) — a filled-in manifest to copy from. `examples/make_demo.sh` synthesizes throwaway media with ffmpeg and runs the whole author→validate pipeline, for checking the scripts work before touching a real project.
