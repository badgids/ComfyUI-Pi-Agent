# Development and testing

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Known limitations](limitations.md) · [Next: Roadmap](roadmap.md)
<!-- DOC_NAV_END -->


## Run tests

```bash
python -m compileall -q comfy_pi_agent
python -m unittest discover -s tests -v
node --check web/pi_agent.js
node --check web/mcp_bridge.js
```

CI runs the Python suite on Linux, Windows, and macOS across Python 3.10–3.13. A separate frontend job syntax-checks both ComfyUI browser extensions with Node.js.

## Add a node

1. Put reusable logic in a focused module.
2. Add a small node wrapper in `nodes.py`.
3. Add display mappings.
4. Add tests without requiring ComfyUI.
5. Update the node reference and changelog.

## Release metadata

`MANIFEST.json` is a generated integrity snapshot. Do not hand-edit only its version or a few hashes. After the release tree is final and contains no unrelated untracked files, regenerate it from the exact checkout:

```bash
python tools/regenerate_manifest.py
python tools/regenerate_manifest.py --check
```

The generator excludes `MANIFEST.json` itself, records the current package version from `comfy_pi_agent/version.py`, and hashes every tracked/non-ignored release file. Review the resulting manifest diff before committing.

## Rules

Do not use hardcoded personal paths, import-time downloads, shell strings, or silent destructive edits.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Known limitations](limitations.md) · [Next: Roadmap](roadmap.md)
<!-- DOC_NAV_FOOTER_END -->
