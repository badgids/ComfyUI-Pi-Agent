# Troubleshooting

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Security and path policy](security.md) · [Next: Architecture](architecture.md)
<!-- DOC_NAV_END -->


## No Pi nodes appear

Check that `__init__.py` is directly inside the cloned directory and inspect the ComfyUI terminal for an import error.

## Pi status says not configured

Install Pi or set `PI_AGENT_EXECUTABLE`. All non-Pi nodes still work.

## Pi starts but gives a model error

Configure a provider and model in Pi. The ComfyUI node does not create provider credentials.

## Workflow report says missing node class

Install or enable the exact package that registers that class, then restart ComfyUI.

## Model inventory is empty

Confirm ComfyUI itself sees models in its model selectors. Review `extra_model_paths.yaml` and the actual ComfyUI instance being used.

## Tutorial compile cannot read a path

Use a path visible to the machine and environment running ComfyUI. A Windows path may not exist inside WSL or Docker.

## Pi Agent Settings are cut off on a small window

Current builds give the Settings panel its own vertical scrollbar. If you still cannot scroll through all settings, hard-refresh the ComfyUI browser after updating the plugin so the latest frontend CSS is loaded.

## Real workflow screenshots say Playwright is unavailable

Install the screenshot extra with the same Python environment that launches ComfyUI:

```bash
cd /path/to/ComfyUI/custom_nodes/ComfyUI-Pi-Agent
python -m pip install -e '.[screenshots]'
```

If no compatible Chromium/Chrome executable is available, also run:

```bash
python -m playwright install chromium
```

Restart ComfyUI after installing Python dependencies. The screenshot tool also requires the ComfyUI server/frontend to be running because it opens a separate capture page against that same instance.

## Existing ASCII diagram conversion says Ascidia is unavailable

Generated semantic flowcharts do not require Ascidia. Only the existing hand-authored ASCII conversion path needs it:

```bash
cd /path/to/ComfyUI/custom_nodes/ComfyUI-Pi-Agent
python -m pip install -e '.[diagrams]'
```

## Terminal is unavailable on native Windows

The real Terminal currently uses a POSIX controlling PTY. WSL is supported; native Windows without a POSIX PTY falls back to the structured Chat view until a ConPTY backend is implemented.

## A checkpoint is saved but context keeps climbing toward 100%

That is not the intended current behavior. At the configured threshold, Terminal should report that the checkpoint was saved and same-session compaction is happening immediately at `turn_end`. Fully restart ComfyUI/Pi after updating so the current terminal bridge is loaded. See [Preemptive same-session context compaction](context-handoff.md).

## DOCX will not open

Report the document and the text used to create it. The first-release writer supports common headings and paragraphs, not every Word feature.

## Kdenlive project needs repair

Use the assembly guide, timeline JSON, profile, and media map to relink or rebuild. Native Kdenlive formats can vary by version.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Security and path policy](security.md) · [Next: Architecture](architecture.md)
<!-- DOC_NAV_FOOTER_END -->
