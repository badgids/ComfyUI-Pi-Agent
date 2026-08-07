# Development and testing

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Known limitations](limitations.md) · [Next: Roadmap](roadmap.md)
<!-- DOC_NAV_END -->


## Run tests

```bash
python -m unittest discover -s tests -v
```

## Add a node

1. Put reusable logic in a focused module.
2. Add a small node wrapper in `nodes.py`.
3. Add display mappings.
4. Add tests without requiring ComfyUI.
5. Update the node reference and changelog.

## Rules

Do not use hardcoded personal paths, import-time downloads, shell strings, or silent destructive edits.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Known limitations](limitations.md) · [Next: Roadmap](roadmap.md)
<!-- DOC_NAV_FOOTER_END -->
