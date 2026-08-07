# Security policy

<!-- DOC_NAV_START -->
**Navigation:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Contributing](CONTRIBUTING.md) · [Next: Code of conduct](CODE_OF_CONDUCT.md)
<!-- DOC_NAV_END -->


## Report a vulnerability

Please report security problems privately to the repository owner before publishing details.

## Important boundaries

- The plugin does not download anything during import.
- Pi is executed without `shell=True`.
- User output paths are explicit or placed under ComfyUI's user directory.
- Child paths are checked so they cannot escape the selected output root.
- Original workflows are preserved before repair or annotation.
- Provider secrets remain in Pi/provider configuration and are not inserted into workflows.

## Untrusted workflows and tutorials

A workflow can reference third-party nodes, scripts, models, or media. Review unknown projects before running them. The tutorial compiler documents detected requirements but cannot guarantee that an unrelated third-party package is safe.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Contributing](CONTRIBUTING.md) · [Next: Code of conduct](CODE_OF_CONDUCT.md)
<!-- DOC_NAV_FOOTER_END -->
