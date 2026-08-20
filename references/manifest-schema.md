# manifest.json schema for author_fcpxml.py

One JSON file describes the whole handoff. All frame numbers are timeline frames at the project fps. All string rational rates use `"num/den"` (e.g. `"30000/1001"`) or plain integers (`"25"`).

```jsonc
{
  "project": {
    "name": "My Project",                      // FCP project name
    "event": "ChatCut Handoff",                // event name inside the library
    "library_bundle": "/abs/path/MyLib.fcpbundle",  // dedicated bundle; created on import
    "width": 1920, "height": 3840,             // sequence canvas
    "fps": "30000/1001",                       // sequence rate
    "duration_frames": 2275,
    "color_space": "1-1-1 (Rec. 709)",         // optional, default shown
    "caption_role": "iTT?captionFormat=ITT.zh",// optional; language via ITT.<lang>
    "caption_style": {                          // optional; FCP largely ignores caption styling,
      "font": "Noto Sans SC", "fontSize": "63", // kept for round-trip completeness
      "fontColor": "1 1 1 1", "bold": "1"
    }
  },

  "assets": {
    "aroll": {
      "path": "/abs/path/master.mov",
      "width": 2160, "height": 3840,           // omit or 0x0 for audio-only
      "frame_rate": "30000/1001",              // null for audio-only
      "has_video": true, "has_audio": true,    // MUST be ffprobe truth — see compatibility.md
      "audio_channels": 2, "audio_rate": 48000,
      "duration_s": "717.717"                  // ffprobe format duration
    },
    "music1": { "path": "/abs/path/track.mp3", "frame_rate": null,
                "has_video": false, "has_audio": true,
                "audio_channels": 2, "audio_rate": 44100, "duration_s": "152.23" }
  },

  "clips": [
    // Spine-lane video clip (lane 1 = primary picture, 2+ = overlays above it)
    { "id": "opening", "asset": "aroll", "lane": 1,
      "from": 0, "duration": 241,              // timeline frames
      "source_start_s": "301.7",               // seconds into the source (aligned to its frame grid)
      "scale_keyframes": [                     // slow push 1.0 -> 1.12 across the clip
        { "at": 0,   "value": 1.0 },           // "at" = frames from clip start
        { "at": 241, "value": 1.12 } ] },

    { "id": "kicker", "asset": "aroll", "lane": 1,
      "from": 460, "duration": 86, "source_start_s": "481.64",
      "scale": 1.5 },                          // static punch-in

    // 16:9 overlay covering a target rect inside a taller canvas (full-bleed crop)
    { "id": "broll1", "asset": "broll", "lane": 2,
      "from": 327, "duration": 72, "source_start_s": "9.7",
      "cover_rect": [1920, 3413.33],           // scale up (center-crop) until this rect is covered
      "volume_db": -60 },

    // Positioned overlay (e.g. an MG rendered at its display size)
    { "id": "mg1", "asset": "mgchat", "lane": 2,
      "from": 1410, "duration": 558, "source_start_s": "0",
      "position_px": [0, 551.1] },             // canvas pixels; +y moves the clip UP

    // Audio clip (negative lanes)
    { "id": "bgm", "asset": "music1", "lane": -1,
      "from": 0, "duration": 546, "source_start_s": "0.95",
      "volume_db": -17.72, "fade_in_s": 0.05, "fade_out_s": 0.3 }
  ],

  "captions": [
    { "from": 15, "to": 87, "text": "第一页字幕" },
    { "from": 90, "to": 122, "text": "第二页" }   // overlaps are clamped to the next start
  ]
}
```

## Field notes

- **`lane`**: positive = video (stacking order), negative = audio. All clips are connected to a single full-length gap in the spine (the verified pattern that keeps every track independent).
- **`source_start_s`** is snapped to the asset's own frame grid (`frame_rate`); audio-only assets snap to the project fps grid. Keeps `start` attributes frame-aligned so FCP doesn't re-quantize.
- **Geometry**: `scale`, `scale_keyframes` and `cover_rect` all drive the same scale channel, so they stay mutually exclusive (setting more than one warns and uses the first in that order). **`position_px` is independent and may be combined with any of them** — the ordinary "repositioned *and* resized overlay" case. Every video clip gets `adjust-conform type="fit"`; transforms compound on top (fit first, then your scale — a center-anchored multiply).
- **`enabled`**: optional, default `true`. Set `false` to carry a clip into FCP as a disabled connected clip (alternate takes, rejected options) instead of dropping it.
- **`cover_rect`** computes the uniform scale needed for the fitted image to cover the given pixel rect (typical use: a 16:9 asset full-bleeding the 9:16 picture rect inside a 1:2 canvas → rect `[canvasW, canvasW*16/9]`).
- **`position_px`** converts to FCP position units at canvasHeight/100 px per unit. Positive y is up.
- **`volume_db`** emits `adjust-volume`; fades nest inside `<param name="amount">` (the only DTD-legal spot).
- **Zoom starting mid-take?** Split the take into two clips at the boundary; give the second the shifted `source_start_s` (= first's start + first's duration/fps, exactly — keeps audio continuous).
- **Captions** get one local `text-style-def` each; punctuation policy is up to you — strip CJK marks globally and ASCII marks only at string end if the burn-in hid punctuation (protects tokens like `5.6`, `B-roll`).
