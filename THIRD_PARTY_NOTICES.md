# Third-party notices

<!-- DOC_NAV_START -->
**Navigation:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Agent/development rules](AGENTS.md) · [Next: Changelog](CHANGELOG.md)
<!-- DOC_NAV_END -->


ComfyUI Pi Agent Production Suite is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

ComfyUI-Pi can discover, inspect, plan, create from installed examples, and operate workflows that use separately distributed projects. Those projects keep their own copyrights, licenses, trademarks, model licenses, and asset licenses.

## ComfyUI-MiniMaxH3-Director

Project:

```text
https://github.com/seesee75-commits/ComfyUI-MiniMaxH3-Director
```

Upstream license: **GPL-3.0**.

ComfyUI-Pi includes original integration metadata, planning/inspection logic, and lazily loaded operating guidance for the pack. It recognizes public node IDs and uses the user's installed upstream example workflows and live ComfyUI schemas as the preferred workflow-creation source.

The upstream project's own source files, copyrights, and notices remain its own. ComfyUI-Pi does not need to vendor a frozen copy of its large frontend implementation in order to interoperate with it.

## WhatDreamsCost-ComfyUI

Project:

```text
https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI
```

Upstream license: **GPL-3.0**.

ComfyUI-Pi includes original integration metadata, inspection/planning logic, and lazily loaded operating guidance for the public WhatDreamsCost node set. Workflow creation prefers the installed upstream `example_workflows` files and live node schemas.

The upstream project remains separately distributed and retains its own copyright notices and third-party dependency obligations.

## ComfyUI-scene-camera-action

Project:

```text
https://github.com/arturitu/ComfyUI-scene-camera-action
```

Upstream node-pack license: **MIT**.

The upstream repository also contains a `scene-staging-builder` AI skill whose metadata declares **Apache-2.0**. ComfyUI-Pi does not copy that skill verbatim. It ships its own GPL-3.0 integration procedure and adapter metadata, and it can discover the user's installed upstream skill path when deeper reference is useful.

ComfyUI-Pi interoperates through the public `SceneNode`, `ActingNode`, and `DirectingNode` contracts, live ComfyUI schemas, and SceneState/preset data. The upstream frontend, models, presets, source code, and notices remain separately licensed.

## ComfyUI-MiniMax-H3-Turbo

Project:

```text
https://github.com/Larryvrh/ComfyUI-MiniMax-H3-Turbo
```

Upstream node-pack license: **Apache-2.0**.

ComfyUI-Pi includes original GPL-3.0 adapter logic, metadata, tests, and lazily loaded operating guidance for the public `MiniMaxH3TurboLoRA` and `MiniMaxH3TurboSampler` nodes. Workflow creation uses the user's installed upstream example workflow as the preferred baseline.

The separately distributed MiniMax H3 base models, Turbo LoRA weights, VAEs, text encoders, and other model assets keep their own license and usage terms; ComfyUI-Pi does not relicense or automatically redistribute them.

## xterm.js

ComfyUI-Pi vendors browser-side xterm.js JavaScript/CSS assets for rendering the real Pi PTY inside the ComfyUI sidebar. xterm.js is distributed under the **MIT License**. Its license text is included at [`web/vendor/XTERM_LICENSE.txt`](web/vendor/XTERM_LICENSE.txt).

The vendored terminal renderer is a frontend dependency only. It does not change the GPL-3.0-only license of ComfyUI-Pi's own source code.

## ComfyUI and other custom nodes

ComfyUI, KJNodes, ComfyUI-GGUF, ComfyUI-LTXVideo, VideoHelperSuite, and other custom-node packs are not relicensed by ComfyUI-Pi. Their original license terms continue to apply.

## Models, media, fonts, and external assets

Model weights, LoRAs, user media, generated media, fonts, music, reference files, and other external assets are not automatically covered by ComfyUI-Pi's GPL-3.0 license merely because ComfyUI-Pi can discover or operate them. Their original licenses and usage terms continue to apply.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Agent/development rules](AGENTS.md) · [Next: Changelog](CHANGELOG.md)
<!-- DOC_NAV_FOOTER_END -->
