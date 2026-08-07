# Installation

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Documentation home](index.md) · [Next: Quick start](quick-start.md)
<!-- DOC_NAV_END -->


## Normal Git installation

1. Stop ComfyUI.
2. Open a terminal in `ComfyUI/custom_nodes`.
3. Clone the repository:

```bash
git clone https://github.com/YOUR-ACCOUNT/ComfyUI-Pi-Agent.git
```

4. Start ComfyUI.
5. Search the node menu for `Pi Agent Status`.

Version 0.1.8 has no required Python package dependencies. The `requirements.txt` file is intentionally empty except for comments.

## ZIP installation

1. Extract the ZIP into `ComfyUI/custom_nodes`.
2. The final path should look like:

```text
ComfyUI/custom_nodes/ComfyUI-Pi-Agent/__init__.py
```

3. Restart ComfyUI.

A common mistake is extracting an extra folder level:

```text
ComfyUI/custom_nodes/ComfyUI-Pi-Agent/ComfyUI-Pi-Agent/__init__.py
```

Move the inner project up one level when that happens.

## Portable ComfyUI

Use the Python environment that belongs to the portable installation for any future optional dependency. The first release itself does not require a pip command.

## Docker

Mount or copy the repository into the container's `custom_nodes` directory. Make sure the container user can read the files and write to the selected ComfyUI user/output directories.

## WSL

Install the node inside the ComfyUI instance that actually runs under WSL. A Windows ComfyUI installation and a WSL ComfyUI installation have different `custom_nodes` directories.

## Verify the frontend extension

The plugin adds an optional sidebar setting and a `Pi Agent` menu command. The sidebar is off by default. When enabled, it provides the full Pi Agent chat interface described in [sidebar-chat.md](sidebar-chat.md). The nodes work even when the JavaScript extension is disabled.

## Update

```bash
cd ComfyUI/custom_nodes/ComfyUI-Pi-Agent
git pull
```

Restart ComfyUI after updating.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Documentation home](index.md) · [Next: Quick start](quick-start.md)
<!-- DOC_NAV_FOOTER_END -->
