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

## DOCX will not open

Report the document and the text used to create it. The first-release writer supports common headings and paragraphs, not every Word feature.

## Kdenlive project needs repair

Use the assembly guide, timeline JSON, profile, and media map to relink or rebuild. Native Kdenlive formats can vary by version.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Security and path policy](security.md) · [Next: Architecture](architecture.md)
<!-- DOC_NAV_FOOTER_END -->
