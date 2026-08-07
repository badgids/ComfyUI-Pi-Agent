# Agent development rules

<!-- DOC_NAV_START -->
**Navigation:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Code of conduct](CODE_OF_CONDUCT.md) · [Next: Third-party notices](THIRD_PARTY_NOTICES.md)
<!-- DOC_NAV_END -->


1. Never hardcode a personal machine path.
2. Never download models, nodes, packages, or tools during plugin import.
3. Preserve original workflows and user files before edits.
4. Use live ComfyUI node schemas and installed model registries.
5. Do not invent filenames, node classes, or compatibility claims.
6. Keep optional integrations isolated from ComfyUI startup.
7. Use argument arrays for subprocesses; never build shell command strings from user input.
8. Keep nodes independently usable and place shared logic in service modules.
9. Update tests and documentation with every user-visible change.
10. Use plain, complete language that is understandable without removing technical detail.
11. Design agent-facing instructions for weak local models: one current objective, deterministic procedure routing, explicit completion rules, and validation evidence.
12. Keep hidden model context bounded and dynamic. Do not preload the skill library, node-pack manuals, whole workflows, or long project files when a compact digest or on-demand path is enough.
13. Agent output must not claim files, workflow changes, tests, or successful execution without observable evidence.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](README.md) · [Documentation home](docs/index.md) · [Previous: Code of conduct](CODE_OF_CONDUCT.md) · [Next: Third-party notices](THIRD_PARTY_NOTICES.md)
<!-- DOC_NAV_FOOTER_END -->
