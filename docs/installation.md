# Installation

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Documentation home](index.md) · [Next: Quick start](quick-start.md)
<!-- DOC_NAV_END -->


## Normal Git installation

1. Stop ComfyUI.
2. Open a terminal in the `ComfyUI/custom_nodes` directory used by the ComfyUI instance you actually run.
3. Clone the repository:

```bash
git clone https://github.com/Badgids/ComfyUI-Pi-Agent.git
cd ComfyUI-Pi-Agent
```

4. Start ComfyUI.
5. Search the node menu for `Pi Agent Status`.

The **core** ComfyUI-Pi plugin intentionally has no mandatory third-party Python dependency. `requirements.txt` therefore remains minimal. Optional documentation features have explicit extras described below.

## Optional Python feature dependencies

Always run these commands with the **same Python interpreter/environment that launches ComfyUI**. Installing into an unrelated system Python will not make the library available to the custom node.

### Documentation diagrams: Ascidia

Generated semantic flowcharts and current ComfyUI Nodes 2.0 schematic node illustrations work without Ascidia. Ascidia is needed when ComfyUI-Pi must convert an **existing hand-authored ASCII diagram** into SVG/PNG using Ascidia's pattern parser instead of tracing text glyphs.

```bash
cd /path/to/ComfyUI/custom_nodes/ComfyUI-Pi-Agent
python -m pip install -e '.[diagrams]'
```

This installs the packaged `ascidia>=2.0.1,<3` optional dependency and its Python dependencies.

### Real workflow/node screenshots: Playwright

Tutorial/documentation screenshot tools use Playwright to open a separate headless browser page against the **same running ComfyUI instance**, load a serialized copy of the active workflow, and capture the real rendered page. Install the screenshot extra with:

```bash
cd /path/to/ComfyUI/custom_nodes/ComfyUI-Pi-Agent
python -m pip install -e '.[screenshots]'
```

ComfyUI-Pi first tries a compatible Chromium/Chrome executable available on the machine. If none is available, install Playwright's Chromium build once:

```bash
python -m playwright install chromium
```

On a Linux/CI host that is also missing Chromium system libraries, Playwright can install the browser plus supported OS dependencies with:

```bash
python -m playwright install --with-deps chromium
```

That command may require the privileges normally needed by the operating-system package manager.

### Install every optional documentation feature

```bash
cd /path/to/ComfyUI/custom_nodes/ComfyUI-Pi-Agent
python -m pip install -e '.[diagrams,screenshots]'
python -m playwright install chromium   # only when no suitable system Chromium/Chrome is available
```

These are optional runtime features. Missing Ascidia or Playwright must not prevent ComfyUI-Pi's core nodes, Terminal, structured Chat, workflow inspection, or project/document compilers from loading.

## Portable ComfyUI

Use ComfyUI's bundled Python, not a random system Python. From the ComfyUI directory, substitute the actual portable interpreter path for `python` in the commands above. For example, a portable package commonly uses a bundled `python_embeded`/`python_embedded` interpreter; use the name present in **your** installation rather than hardcoding a machine-specific path.

## ZIP installation

1. Extract the ZIP into `ComfyUI/custom_nodes`.
2. The final path should look like:

```text
ComfyUI/custom_nodes/ComfyUI-Pi-Agent/__init__.py
```

3. Install optional extras from that extracted directory only if you need those features.
4. Restart ComfyUI.

A common mistake is extracting an extra folder level:

```text
ComfyUI/custom_nodes/ComfyUI-Pi-Agent/ComfyUI-Pi-Agent/__init__.py
```

Move the inner project up one level when that happens.

## Docker

Mount or copy the repository into the container's `custom_nodes` directory. Run optional `pip` installs **inside the same container/environment as ComfyUI**. For Playwright screenshots the container also needs a usable Chromium/Chrome installation or the Playwright Chromium binary and its required OS libraries.

## WSL

Install the node and any optional dependencies inside the ComfyUI instance that actually runs under WSL. A Windows ComfyUI installation and a WSL ComfyUI installation have different Python environments and `custom_nodes` directories.

The real Terminal mode uses the POSIX controlling-PTY backend under WSL. Native Windows without a POSIX PTY falls back to structured Chat until a ConPTY backend is provided.

## Verify the frontend extension

The plugin adds the optional **Pi Agent** interface. When enabled, it provides Terminal and Chat views described in [sidebar-chat.md](sidebar-chat.md). The node-based tools continue to work when the interface is disabled.

For Playwright screenshot capture, ComfyUI itself must already be running because the capture page connects back to the same live frontend/API instance.

## Update

```bash
cd ComfyUI/custom_nodes/ComfyUI-Pi-Agent
git pull
```

If an update changes optional dependency versions, refresh the extras you use:

```bash
python -m pip install -e '.[diagrams,screenshots]'
python -m playwright install chromium
```

Restart ComfyUI after Python/backend updates. A hard browser refresh is also recommended after frontend changes.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Documentation home](index.md) · [Next: Quick start](quick-start.md)
<!-- DOC_NAV_FOOTER_END -->
