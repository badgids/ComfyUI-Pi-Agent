# Contributing

<!-- DOC_NAV_START -->
**Navigation:** [Project README](README.md) · [Documentation home](docs/index.md) · [Next: Security policy](SECURITY.md)
<!-- DOC_NAV_END -->


Thank you for helping improve ComfyUI Pi Agent.

## Ground rules

1. Do not hardcode a personal machine path.
2. Do not download models or dependencies during plugin import.
3. Preserve original workflows and user files before edits.
4. Use live ComfyUI node schemas whenever possible.
5. Do not invent model filenames or claim unsupported compatibility.
6. Keep optional integrations isolated so a failure cannot stop ComfyUI.
7. Write documentation in plain, complete English.
8. Add tests for new behavior.

## Development

```bash
python -m unittest discover -s tests -v
```

Use focused modules instead of placing every feature in `nodes.py`. Nodes should call shared services so the same behavior can later be used by the API and optional sidebar.

## Pull requests

Describe:

- the problem;
- the change;
- how it was tested;
- compatibility risks;
- documentation changed;
- whether files, paths, models, or dependencies are affected.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](README.md) · [Documentation home](docs/index.md) · [Next: Security policy](SECURITY.md)
<!-- DOC_NAV_FOOTER_END -->
