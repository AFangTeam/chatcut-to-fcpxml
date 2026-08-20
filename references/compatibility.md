# Verified FCP compatibility notes

Everything below was measured against a real Final Cut Pro import (FCP 12.x), not inferred from documentation. Where a number appears, it was read back from FCP's Inspector.

## Contents

1. Feature policy table
2. Silent-drop traps
3. Position units & letterbox geometry
4. Zoom cloning (static + keyframed)
5. Captions
6. Frame-rate mapping
7. DTD traps (v1.10)
8. Verification techniques (incl. computer-use automation)

## 1. Feature policy

| ChatCut feature | FCPXML handoff | Policy |
|---|---|---|
| Cuts, order, gaps, source trims | Preserve | Frame-exact rational times |
| Multiple video tracks | Preserve | Gap-anchored spine; tracks become positive lanes |
| Multiple audio tracks | Preserve | Negative lanes; never mix down |
| Zoom effects (punch-in / slow push) | Preserve | Static / keyframed `adjust-transform` scale |
| Volume, fades | Preserve | `adjust-volume` + nested `param` fades |
| Captions | Timing/text only | iTT captions; styling is FCP's own |
| Motion Graphics (JSX) | Pre-render | ProRes 4444 with alpha via server render |
| Shaders / LUTs / plugin transitions | Not portable | Rebuild, pre-render, or omit — and report |
| Nested timelines | Risky | Expand only when semantics are known |

A successful XML parse does not prove visual parity. Verify in FCP.

## 2. Silent-drop traps

FCP imports "successfully" and just omits things. Check the imported project, never the exit code.

| Trap | Symptom | Rule |
|---|---|---|
| `hasAudio="0"` on media that really has an audio track | Asset **and every connected clip in the same gap** vanish, no warning | ffprobe every asset; declare `hasVideo`/`hasAudio` truthfully. Server-rendered MG movies typically carry a silent PCM track → `hasAudio="1"` + audio attrs |
| Asset `format` copied from the sequence format | Wrong conform/scale or dropped asset | Give each asset its own `<format>` matching real ffprobe dimensions and frame duration |
| Hand-rolled compensating `adjust-transform scale` on top of conform | Picture shrunk with bars on all four sides | Conform runs FIRST, your transform multiplies ON TOP. Let `fit` be the only source of *fitting* scale; add transforms only for intentional moves (zooms, full-bleed) |
| Same project name in two libraries | You verify the wrong timeline | Import each verification pass into a uniquely named library |

## 3. Position units & letterbox geometry

**`adjust-transform position` is NOT pixels.** One unit = **1% of canvas height** (canvasH/100 px). On a 3840-tall canvas that's 38.4 px/unit; a written value of `14.35` read back as 551.1 px in the Inspector. Positive y moves the clip up. Always read one value back from the Inspector before trusting a batch of positions.

**Aspect change → let `fit` letterbox and anchor overlays to the PICTURE RECT.** When placing a smaller-aspect source canvas (e.g. 9:16 content) inside a taller delivery canvas (e.g. 1:2):

- `adjust-conform type="fill"` was **ignored** by FCP — don't rely on it.
- `fit` maps the whole source canvas with one uniform factor and zero cropping. Every source coordinate survives: `factor = canvasW / srcW`, picture rect height `= srcH × factor`, `pic_top = (canvasH − pic_h)/2`. Overlay position = measured from the picture rect, not the canvas — anchoring to the canvas silently shifts everything by `pic_top`.
- Full-bleed 16:9 inside the vertical picture rect: after `fit` normalizes the asset to canvas width, apply `scale = picRectH / fittedH` (e.g. 3413.33/1080 ≈ 3.1605 — works for any resolution of the same aspect, since fit normalizes first). Inspector reads it as e.g. 316.05%.

**Server-rendered MGs come out at the timeline item's display size** (not the project canvas), so their placement needs only a position offset — no scale.

## 4. Zoom cloning — verified working

- **Instant punch-in**: static `<adjust-transform scale="1.5 1.5"/>` on the clip. Compounds with conform `fit` as a center-anchored multiply — exactly a punch-in. Inspector: 150.0%.
- **Slow push**: `<adjust-transform><param name="scale"><keyframeAnimation><keyframe …/>`. Keyframe `time` values are in **source-time coordinates** (the clip's `start` … `start + duration`). Verified: a 1.0→1.12 push read 111.85% at the theoretically interpolated moment — exact linear interpolation, editable keyframes in FCP.
- Zoom boundaries that fall mid-clip: split the clip into two asset-clips in the XML. Keep the source contiguous (second `start` = first `start` + duration) so audio stays seamless.

## 5. Captions

`<caption role="iTT?captionFormat=ITT.<lang>">` carries text + timing + line breaks faithfully and stays editable in FCP's caption lane. But FCP renders with its **own caption styling and ignores** declared `fontSize`/`fontColor`/stroke. Never promise burn-in look parity through captions; offer restyling in FCP or a rendered burn-in instead.

- Captions in one lane must not overlap — clamp each page's end to the next page's start.
- If the source burn-in hid punctuation at render time, the transcript still contains it: strip CJK marks globally but ASCII marks only at string end (protects `5.6`, `B-roll`).
- `text-style ref` targets a `text-style-def` declared locally inside the same caption — that's valid; don't flag it as a broken resource ref.

## 6. Frame-rate mapping

- If the "30fps" timeline's master footage is really 29.97 (30000/1001) — common for camera files — author everything at `frames × 1001/30000s`. Frame counts then map one-to-one; landmark cuts land on the exact TC (verified to the frame).
- Mixed-rate sources (24/25 fps B-roll on a 29.97 timeline) are fine: give each asset its true `<format>`; align each clip's `start` to the source's own frame grid; FCP conforms playback.
- Audio-only assets have no frame grid; snap their source offsets to the timeline grid.

## 7. DTD traps (FCPXMLv1.10)

- `fadeIn`/`fadeOut` may NOT be direct children of `adjust-volume`. DTD: `adjust-volume (param*)`, `param (fadeIn?, fadeOut?, keyframeAnimation?, param*)` → nest fades inside `<param name="amount">`.
- `<text placement="…">` is not a legal attribute anymore — omit it.
- Validate against FCP's bundled DTD when present: `/Applications/Final Cut Pro.app/Contents/Frameworks/Interchange.framework/Versions/A/Resources/FCPXMLv1_10.dtd`. `xmllint --dtdvalid` may print only a summary line with no detail — extract element rules from the DTD (`grep "ELEMENT <name>"`) to debug.

## 8. Verification techniques

Checklist order that pays off: specs bar → clip durations in the Inspector header → keyframe diamonds present → one interpolated zoom value mid-push → per-lane content at 5–6 landmark TCs → one audio clip's dB readback → caption spot checks.

Frame ↔ TC arithmetic: at 29.97 NDF, frame N displays as `N div 30 : N mod 30` (e.g. frame 2099 → 1:09:29). Landing landmarks exactly is the fastest whole-pipeline integrity check.

Automating with computer-use style tools:

- A phantom helper window (e.g. `com.apple.talagent`) can float invisibly over FCP and swallow synthetic clicks, with click gates misattributing the target app. Workarounds that worked: AppleScript System Events `click at {x,y}` (coordinates in display points — convert from screenshot pixels by `displayPtWidth / screenshotWidth`), and Quartz `CGEventCreateMouseEvent` with `kCGMouseEventClickState=2` for real double-clicks.
- Positioning the playhead: clicking the **timeline ruler** is far more reliable than the timecode field or `Ctrl+P` with synthetic keystrokes. Compute x from `rulerX0 + seconds × pxPerSecond`.
- FCP's XML import dialog (choose/new library) is also reachable via System Events button clicks when direct clicks are blocked.
- Compare rendered stills: park the playhead at a landmark, screenshot the viewer, and diff against the source system's render of the same frame.
