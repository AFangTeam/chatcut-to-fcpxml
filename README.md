# chatcut-to-fcpxml

**ChatCut → Final Cut Pro.** Hand a [ChatCut](https://chatcut.com) timeline off to Final Cut Pro as a real, editable FCPXML project — not a flattened render.

**[👉 简体中文文档](README.zh-CN.md)** · English below

An [Agent Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview): drop the folder into Claude Code or Codex and ask. The Python underneath also runs on its own, with no agent involved.

## Watch it work

<a href="https://www.bilibili.com/video/BV17M8P6EEgD/"><img src="https://i0.hdslb.com/bfs/archive/cc477eb429164de56ab0dedf5ecca89e3a3bac65.jpg" width="480" alt="终于 FinalCut+自动剪辑 — chatcut-to-fcpxml walkthrough"></a>

**[终于😲 FinalCut+自动剪辑](https://www.bilibili.com/video/BV17M8P6EEgD/)** · 3:48 · Bilibili · in Chinese

A full run: ChatCut edit in, Final Cut Pro project out.
<!-- YouTube version: add a line here once it's up. -->

Cuts land on the exact frame. Overlay tracks stay separate lanes. Zoom moves come across as live, editable keyframes. Music keeps its dB and its fades. Captions arrive in FCP's own caption lane.

Everything in this skill was measured against a real Final Cut Pro import (FCP 12.x) and read back from the Inspector — including the failure modes, which are the reason the skill exists. FCP imports FCPXML *silently*: a clean exit code and a green import dialog routinely hide assets that were dropped, transforms that compounded, and captions that restyled themselves.

## What survives the trip

| ChatCut | In Final Cut Pro |
|---|---|
| Cuts, order, gaps, source trims | Frame-exact, rational timebase |
| Multiple video tracks | Positive lanes off a gap-anchored spine |
| Multiple audio tracks | Negative lanes, never mixed down |
| Instant punch-in (e.g. 150%) | Static `adjust-transform` scale |
| Slow push (e.g. 1.0 → 1.12) | Real keyframes you can drag afterwards |
| Volume + fades | `adjust-volume` with DTD-legal nested fades |
| Captions | iTT captions — text, timing and line breaks exact |
| Motion Graphics | Pre-rendered ProRes 4444 with alpha |
| Shaders / LUTs / plugin transitions | **Not portable** — rebuild, pre-render, or omit and report |

## Requirements

- **Final Cut Pro** 12.x (the DTD check reads FCP's own bundled `FCPXMLv1_10.dtd`; the pipeline runs fine without FCP installed, it just skips that check)
- **Python 3.9+** — standard library only, nothing to `pip install`
- **ffmpeg / ffprobe** — every asset gets probed, because declaring media untruthfully is what makes FCP drop it
- **ChatCut** — the skill reads the source timeline through ChatCut's MCP tools, which any MCP-capable host exposes. Without ChatCut you can still drive `author_fcpxml.py` by writing a manifest yourself.

## Install

This repo *is* the skill, so cloning it into your skills directory is the whole install:

```bash
git clone https://github.com/AFangTeam/chatcut-to-fcpxml.git ~/.claude/skills/chatcut-to-fcpxml    # Claude Code
git clone https://github.com/AFangTeam/chatcut-to-fcpxml.git ~/.codex/skills/chatcut-to-fcpxml     # Codex
```

Want a pinned version instead? Grab the release zip:

```bash
curl -L -o skill.zip https://github.com/AFangTeam/chatcut-to-fcpxml/releases/latest/download/chatcut-to-fcpxml.zip
unzip skill.zip -d ~/.claude/skills/     # or ~/.codex/skills/
```

Then just ask your agent for it:

> Export this ChatCut project to Final Cut Pro

The skill drives ChatCut through its MCP tools, which are the same in every host, so it behaves identically wherever it runs.

## Check it works

```bash
bash examples/make_demo.sh
```

Synthesizes three throwaway clips with ffmpeg, writes a manifest, authors an FCPXML and validates it. Expected output:

```
written .../demo.fcpxml  (assets=3 clips=4 captions=2)
resources=6 refs=5 dtd=passed errors=0 warnings=0
```

`open examples/demo.fcpxml` to import it into FCP. It exercises the awkward paths on purpose: a vertical 1080×1920 canvas fed by 16:9 sources, a 25fps clip on a 29.97 timeline, a video-only asset, a keyframed push, a static punch-in, and Chinese captions.

## Using it directly

With no agent involved at all, the two scripts stand alone:

```bash
python3 scripts/author_fcpxml.py manifest.json output.fcpxml
python3 scripts/validate_fcpxml.py output.fcpxml
```

Start from [`examples/manifest.example.json`](examples/manifest.example.json); every field is documented in [`references/manifest-schema.md`](references/manifest-schema.md).

Exit codes: `author_fcpxml.py` returns `2` when a referenced media file is missing — it still writes valid XML, so you can author before the media has landed. `validate_fcpxml.py` returns `1` only on structural errors; missing media is a warning there.

## Known limits — say these out loud before you promise anything

- **iTT captions keep text, timing and line breaks, but FCP renders them in its own caption style.** Fonts, sizes and background panels do not carry over. Burned-in caption *looks* never survive the trip; restyle in FCP or deliver a burn-in.
- **Shaders, LUTs and plugin transitions have no FCPXML equivalent.** Rebuild them in FCP, pre-render them to a movie, or omit them — and report which.
- **Cross-frame-rate sources import fine** (FCP conforms them), but frame-exact *source* trims quantize to the source's own frame grid.
- **A successful import proves nothing.** [`references/compatibility.md`](references/compatibility.md) has the verification checklist; run it.

## What's in the box

```
SKILL.md                        the procedure the agent follows
agents/openai.yaml              interface card for OpenAI-side hosts (Codex)
references/compatibility.md     every verified FCP behavior — silent-drop table, position
                                units, conform/transform compounding, letterbox math,
                                caption fidelity, DTD traps, verification techniques
references/manifest-schema.md   the manifest.json format, field by field
scripts/author_fcpxml.py        manifest.json -> FCPXML
scripts/validate_fcpxml.py      structure, resource refs, media existence, FCP's own DTD
examples/                       a filled-in manifest and a self-contained demo
```

## License

[MIT](LICENSE) — use it, fork it, ship it in your own work.

More of my skills and tools: [github.com/AFangTeam](https://github.com/AFangTeam)
