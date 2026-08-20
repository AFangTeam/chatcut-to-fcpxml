#!/usr/bin/env python3
"""Author a complete FCPXML from a manifest.json (see references/manifest-schema.md).

Encodes only patterns verified against a real Final Cut Pro import:
per-asset truthful formats, gap-anchored spine with signed lanes, conform=fit,
static & keyframed transform scale (keyframe times in SOURCE-time coordinates),
cover-rect full-bleed geometry, position in canvas px -> FCP units (canvasH/100),
adjust-volume with DTD-legal nested fades, iTT captions with overlap clamping,
dedicated library bundle. Usage: author_fcpxml.py manifest.json output.fcpxml
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, indent, ElementTree


def parse_rate(value):
    if value in (None, "", 0):
        return None
    return Fraction(str(value))


def rational_s(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}s"


def main() -> int:
    manifest_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    prj = m["project"]
    fps = parse_rate(prj["fps"])
    canvas_w, canvas_h = int(prj["width"]), int(prj["height"])
    pos_unit = Decimal(canvas_h) / 100  # px per FCP position unit (verified)

    def tsec(frames) -> str:  # timeline frames -> rational seconds
        return rational_s(Fraction(int(frames), 1) / fps)

    def ssec(seconds_str, rate: Fraction | None) -> str:  # source secs, frame-grid aligned
        grid = rate or fps
        fr = int((Decimal(str(seconds_str)) * Decimal(grid.numerator) / Decimal(grid.denominator))
                 .quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return rational_s(Fraction(fr, 1) / grid)

    root = Element("fcpxml", {"version": "1.10"})
    res = SubElement(root, "resources")
    color = prj.get("color_space", "1-1-1 (Rec. 709)")
    SubElement(res, "format", {"id": "r1", "frameDuration": rational_s(1 / fps),
                               "width": str(canvas_w), "height": str(canvas_h), "colorSpace": color})

    fmt_ids: dict[tuple, str] = {}
    asset_ids: dict[str, str] = {}
    rates: dict[str, Fraction | None] = {}
    missing: list[str] = []
    for i, (key, a) in enumerate(m["assets"].items(), 2):
        p = Path(a["path"])
        if not p.exists():
            missing.append(str(p))
        rate = parse_rate(a.get("frame_rate"))
        if a.get("has_video") and rate is None:
            # A video asset with no frame_rate used to crash with a bare TypeError on 1/rate.
            # Fall back to the project rate and say so; a wrong-but-declared rate is recoverable,
            # a traceback in the middle of a handoff is not.
            print(f"WARNING asset {key!r} has_video but no frame_rate; using project fps {fps}")
            rate = fps
        rates[key] = rate
        attrs = {"id": f"r{i}", "name": p.name, "start": "0/1s",
                 "duration": rational_s(Fraction(Decimal(str(a["duration_s"])))),
                 "hasVideo": "1" if a.get("has_video") else "0",
                 "hasAudio": "1" if a.get("has_audio") else "0"}
        if a.get("has_video"):
            sig = (a["width"], a["height"], str(rate))
            if sig not in fmt_ids:
                fmt_ids[sig] = f"rf{len(fmt_ids) + 1}"
                SubElement(res, "format", {"id": fmt_ids[sig], "frameDuration": rational_s(1 / rate),
                                           "width": str(a["width"]), "height": str(a["height"]),
                                           "colorSpace": color})
            attrs["format"] = fmt_ids[sig]
        if a.get("has_audio"):
            attrs.update({"audioSources": "1", "audioChannels": str(a.get("audio_channels", 2)),
                          "audioRate": str(a.get("audio_rate", 48000))})
        node = SubElement(res, "asset", attrs)
        SubElement(node, "media-rep", {"kind": "original-media", "src": p.resolve().as_uri()})
        asset_ids[key] = f"r{i}"

    lib = SubElement(root, "library")
    if prj.get("library_bundle"):
        lib.set("location", Path(prj["library_bundle"]).resolve().as_uri())
    event = SubElement(lib, "event", {"name": prj.get("event", "ChatCut Handoff")})
    proj = SubElement(event, "project", {"name": prj["name"]})
    seq = SubElement(proj, "sequence", {"format": "r1", "duration": tsec(prj["duration_frames"]),
                                        "tcStart": "0/1s", "tcFormat": "NDF",
                                        "audioLayout": "stereo", "audioRate": "48k",
                                        "renderFormat": "FFRenderFormatProRes422"})
    spine = SubElement(seq, "spine")
    gap = SubElement(spine, "gap", {"name": "ChatCut Timeline", "offset": "0/1s",
                                    "duration": tsec(prj["duration_frames"])})

    for c in m["clips"]:
        key, lane = c["asset"], int(c["lane"])
        rate = rates[key]
        start = ssec(c["source_start_s"], rate)
        clip = SubElement(gap, "asset-clip", {"name": c["id"], "ref": asset_ids[key],
                                              "offset": tsec(c["from"]), "start": start,
                                              "duration": tsec(c["duration"]),
                                              "lane": str(lane),
                                              "enabled": "1" if c.get("enabled", True) else "0"})
        if lane > 0 and m["assets"][key].get("has_video"):
            SubElement(clip, "adjust-conform", {"type": "fit"})
            a = m["assets"][key]
            # scale, scale_keyframes and cover_rect all drive the same channel, so they stay
            # mutually exclusive; position_px is independent and may combine with any of them.
            # Previously the whole chain was one elif, so a positioned AND scaled overlay -- the
            # ordinary repositioned B-roll case -- silently lost its scale with no warning.
            scale_sources = [k for k in ("cover_rect", "scale", "scale_keyframes") if c.get(k)]
            if len(scale_sources) > 1:
                print(f"WARNING clip {c['id']!r}: {', '.join(scale_sources)} all set a scale; "
                      f"using {scale_sources[0]!r} and ignoring the rest")
            attrs = {}
            if c.get("position_px"):
                x, y = (Decimal(str(v)) / pos_unit for v in c["position_px"])
                attrs["position"] = f"{x:.4f} {y:.4f}"
            chosen = scale_sources[0] if scale_sources else None
            if chosen == "cover_rect":
                # scale so the FITTED image covers the rect (center-crop full-bleed)
                fit = min(Fraction(canvas_w, a["width"]), Fraction(canvas_h, a["height"]))
                disp_w, disp_h = a["width"] * fit, a["height"] * fit
                rw, rh = (Decimal(str(v)) for v in c["cover_rect"])
                s = max(rw / Decimal(float(disp_w)), rh / Decimal(float(disp_h)))
                attrs["scale"] = f"{s:.5f} {s:.5f}"
            elif chosen == "scale":
                sv = f"{Decimal(str(c['scale'])):f}"
                attrs["scale"] = f"{sv} {sv}"
            if chosen == "scale_keyframes":
                tr = SubElement(clip, "adjust-transform", attrs)
                param = SubElement(tr, "param", {"name": "scale"})
                ka = SubElement(param, "keyframeAnimation")
                sf = Fraction(*[int(x) for x in start.rstrip("s").split("/")])
                for kf in c["scale_keyframes"]:
                    t = sf + Fraction(int(kf["at"]), 1) / fps  # SOURCE-time coordinates
                    v = f"{Decimal(str(kf['value'])):f}"
                    SubElement(ka, "keyframe", {"time": rational_s(t), "value": f"{v} {v}"})
            elif attrs:
                SubElement(clip, "adjust-transform", attrs)
        if c.get("volume_db") is not None and m["assets"][key].get("has_audio"):
            av = SubElement(clip, "adjust-volume", {"amount": f"{c['volume_db']}dB"})
            if c.get("fade_in_s") or c.get("fade_out_s"):
                pm = SubElement(av, "param", {"name": "amount"})  # DTD: fades nest in param
                if c.get("fade_in_s"):
                    SubElement(pm, "fadeIn", {"type": "easeIn", "duration": ssec(c["fade_in_s"], fps)})
                if c.get("fade_out_s"):
                    SubElement(pm, "fadeOut", {"type": "easeOut", "duration": ssec(c["fade_out_s"], fps)})

    role = prj.get("caption_role", "iTT?captionFormat=ITT.en")
    cstyle = prj.get("caption_style", {})
    caps = m.get("captions", [])
    cap_lane = str(max([c["lane"] for c in m["clips"] if c["lane"] > 0], default=1) + 1)
    dropped_caps = 0
    for i, page in enumerate(caps):
        end = page["to"]
        if i + 1 < len(caps):
            end = min(end, caps[i + 1]["from"])  # FCP rejects overlapping captions in a lane
        if end - page["from"] < 1:
            # Clamping against the next page can collapse a caption to zero (or negative) length,
            # which used to emit duration="0/1s". Drop it and say so instead of writing bad XML.
            dropped_caps += 1
            print(f"WARNING caption {i} ({page['text'][:12]!r}) collapsed to <1 frame after "
                  f"overlap clamping; dropped")
            continue
        cap = SubElement(gap, "caption", {"name": page["text"][:14], "lane": cap_lane,
                                          "offset": tsec(page["from"]), "duration": tsec(end - page["from"]),
                                          "start": tsec(page["from"]), "role": role})
        t = SubElement(cap, "text", {})
        ts = SubElement(t, "text-style", {"ref": f"cts{i}"})
        ts.text = page["text"]
        tsd = SubElement(cap, "text-style-def", {"id": f"cts{i}"})
        SubElement(tsd, "text-style", {"font": cstyle.get("font", "Helvetica"),
                                       "fontSize": cstyle.get("fontSize", "60"),
                                       "fontColor": cstyle.get("fontColor", "1 1 1 1"),
                                       "bold": cstyle.get("bold", "1"), "alignment": "center"})

    indent(root, space="  ")
    with out_path.open("wb") as h:
        h.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n')
        ElementTree(root).write(h, encoding="utf-8", xml_declaration=False)
    print(f"written {out_path}  (assets={len(asset_ids)} clips={len(m['clips'])} "
          f"captions={len(caps) - dropped_caps}" + (f" dropped={dropped_caps}" if dropped_caps else "") + ")")
    if missing:
        print("WARNING missing media:\n  " + "\n  ".join(missing))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
