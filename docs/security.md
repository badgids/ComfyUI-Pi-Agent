# Security and path policy

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Kdenlive and NLE handoff](kdenlive-nle.md) · [Next: Troubleshooting](troubleshooting.md)
<!-- DOC_NAV_END -->


## Import safety

Import performs no downloads, package installs, model scans outside ComfyUI's registry, or shell commands.

## Paths

No personal path is embedded. Empty output fields use the ComfyUI user directory. Explicit output directories are treated as user decisions. Generated child paths are checked against the selected root.

## Pi process

Pi is started through `subprocess.Popen` with a list of arguments. `shell=True` is not used.

## Secrets

The plugin does not place provider keys in workflow JSON. Configure credentials in Pi or the provider service.

## Third-party workflows

A tutorial can describe a workflow but cannot certify every custom node it references. Review third-party code before installing it.

## Sidebar chat history

The optional Pi Agent sidebar stores chat transcripts as local JSON files under ComfyUI user data. Clear or delete a chat from the sidebar when you no longer want that transcript saved. Do not paste passwords, API keys, access tokens, or other secrets into chat or project-context fields.

The chat routes are served by the same ComfyUI server as the rest of the plugin. If you expose ComfyUI to other computers, protect the ComfyUI server using the same network and authentication controls you use for the rest of your installation.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Kdenlive and NLE handoff](kdenlive-nle.md) · [Next: Troubleshooting](troubleshooting.md)
<!-- DOC_NAV_FOOTER_END -->
