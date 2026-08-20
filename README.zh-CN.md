# chatcut-to-fcpxml

**ChatCut → Final Cut Pro。** 把 [ChatCut](https://chatcut.com) 的时间线原样交接给 Final Cut Pro —— 交过去的是一个还能继续剪的 FCPXML 工程，不是一条压平的成片。

这是一个 [Agent Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview)：把文件夹丢进 Claude Code 或 Codex，然后开口就行。底下那两个 Python 脚本也能脱离 agent 单独跑。

简体中文 · **[English](README.md)**

> **从视频过来的？** 一句话装好，直接跳到 [安装](#安装)；想先确认能跑，看 [验证能跑通](#验证能跑通)。

## 看它怎么跑

<a href="https://www.bilibili.com/video/BV17M8P6EEgD/"><img src="https://i0.hdslb.com/bfs/archive/cc477eb429164de56ab0dedf5ecca89e3a3bac65.jpg" width="480" alt="终于 FinalCut+自动剪辑"></a>

**[终于😲 FinalCut+自动剪辑](https://www.bilibili.com/video/BV17M8P6EEgD/)** · 3:48 · 哔哩哔哩

从 ChatCut 的成片到 Final Cut Pro 工程，完整走一遍。
<!-- YouTube 版：传好之后在这里加一行。 -->

剪辑点落在准确的那一帧。叠加轨还是分开的轨。推镜过去是活的关键帧，落地还能接着拖。音乐的 dB 和淡入淡出都在。字幕进的是 FCP 自己的字幕轨。

这个 skill 里的每一条都是对着真实的 Final Cut Pro（FCP 12.x）导入结果量出来的，数字全部从检查器里读回来 —— 包括那些失败模式，而它们恰恰是这个 skill 存在的理由。FCP 导入 FCPXML 是**静默失败**的：退出码干干净净、导入对话框一路绿灯，素材照样能凭空消失、变换照样能叠错、字幕照样能自己换个样式。

## 哪些东西能原样过去

| ChatCut | 到了 Final Cut Pro |
|---|---|
| 剪辑点、顺序、空隙、源素材裁切 | 帧级精确，有理数时基 |
| 多条视频轨 | 挂在 gap 主干上的正 lane |
| 多条音频轨 | 负 lane，绝不混音下来 |
| 瞬间推近（比如 150%） | 静态 `adjust-transform` 缩放 |
| 缓慢推镜（比如 1.0 → 1.12） | 真关键帧，进去还能改 |
| 音量 + 淡入淡出 | `adjust-volume`，淡变嵌在 DTD 允许的位置 |
| 字幕 | iTT 字幕 —— 文字、时间、断行完全一致 |
| Motion Graphics | 预渲染成带 alpha 的 ProRes 4444 |
| 滤镜 / LUT / 插件转场 | **过不去** —— 在 FCP 里重建、预渲染，或者省掉并如实报告 |

## 依赖

- **Final Cut Pro** 12.x（DTD 校验读的是 FCP 自带的 `FCPXMLv1_10.dtd`；没装 FCP 也能跑，只是跳过这步校验）
- **Python 3.9+** —— 只用标准库，不用 `pip install` 任何东西
- **ffmpeg / ffprobe** —— 每个素材都要 probe 一遍，因为把媒体信息填得不老实正是 FCP 丢素材的原因
- **ChatCut** —— skill 通过 ChatCut 的 MCP 工具读取源时间线，这套工具任何支持 MCP 的 host 都能拿到。没有 ChatCut 你也能自己写 manifest 来驱动 `author_fcpxml.py`

## 安装

这个仓库本身就是那个 skill，所以直接 clone 到 skills 目录就装完了：

```bash
git clone https://github.com/AFangTeam/chatcut-to-fcpxml.git ~/.claude/skills/chatcut-to-fcpxml    # Claude Code
git clone https://github.com/AFangTeam/chatcut-to-fcpxml.git ~/.codex/skills/chatcut-to-fcpxml     # Codex
```

想锁定版本就下 Release 里的 zip：

```bash
curl -L -o skill.zip https://github.com/AFangTeam/chatcut-to-fcpxml/releases/latest/download/chatcut-to-fcpxml.zip
unzip skill.zip -d ~/.claude/skills/     # 或 ~/.codex/skills/
```

然后直接跟你的 agent 说：

> 把这个 ChatCut 工程导到 Final Cut Pro

skill 是通过 ChatCut 的 MCP 工具驱动的，这套工具在各个 host 里是同一套，所以在哪跑行为都一样。

## 验证能跑通

```bash
bash examples/make_demo.sh
```

用 ffmpeg 合成三条临时素材、写好 manifest、生成 FCPXML 并校验。预期输出：

```
written .../demo.fcpxml  (assets=3 clips=4 captions=2)
resources=6 refs=5 dtd=passed errors=0 warnings=0
```

`open examples/demo.fcpxml` 就能导进 FCP。这个 demo 是故意挑难走的路走的：竖屏 1080×1920 画布配 16:9 源、29.97 时间线上放一条 25fps 的素材、一条纯视频无音轨的素材、一个带关键帧的推镜、一个静态推近，以及中文字幕。

## 完全不经过 agent 直接跑

两个脚本本身是独立的：

```bash
python3 scripts/author_fcpxml.py manifest.json output.fcpxml
python3 scripts/validate_fcpxml.py output.fcpxml
```

从 [`examples/manifest.example.json`](examples/manifest.example.json) 改起，每个字段在 [`references/manifest-schema.md`](references/manifest-schema.md) 里都有说明。

退出码：`author_fcpxml.py` 在引用的媒体文件不存在时返回 `2` —— 但 XML 照样是合法的，所以素材还没到位时就可以先把工程写出来。`validate_fcpxml.py` 只在结构性错误时返回 `1`，缺素材在它这里只是 warning。

## 已知边界 —— 答应别人之前先把这几条说清楚

- **iTT 字幕的文字、时间、断行都保留，但 FCP 用它自己的字幕样式渲染。** 字体、字号、背景条都带不过去。烧录字幕的**外观**永远过不了这一趟；要么在 FCP 里重新做样式，要么直接交烧录版。
- **滤镜、LUT、插件转场在 FCPXML 里没有对应物。** 在 FCP 里重建、预渲染成片段，或者省掉 —— 但要说清楚省了哪些。
- **不同帧率的素材导入没问题**（FCP 会做 conform），但对**源素材**的帧级裁切会被量化到源自己的帧网格上。
- **导入成功什么都证明不了。** 验证清单在 [`references/compatibility.md`](references/compatibility.md) 里，照着走一遍。

## 目录里都有什么

```
SKILL.md                        agent 实际执行的流程
agents/openai.yaml              给 OpenAI 侧 host（Codex）的接口卡片
references/compatibility.md     所有实测过的 FCP 行为 —— 静默丢弃对照表、position 单位、
                                conform 与 transform 的叠加关系、letterbox 数学、字幕保真度、
                                DTD 陷阱、验证手法
references/manifest-schema.md   manifest.json 格式，逐字段说明
scripts/author_fcpxml.py        manifest.json -> FCPXML
scripts/validate_fcpxml.py      结构、资源引用、媒体存在性、FCP 自带 DTD
examples/                       一份填好的 manifest 和一个自包含的 demo
```

## 许可

[MIT](LICENSE) —— 随便用、随便改、随便放进你自己的活里。

我的其他 skill 和工具：[github.com/AFangTeam](https://github.com/AFangTeam)
