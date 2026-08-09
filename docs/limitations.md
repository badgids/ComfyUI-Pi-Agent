# Known limitations

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Compatibility](compatibility.md) · [Next: Development and testing](development.md)
<!-- DOC_NAV_END -->


- ComfyUI-Pi does not generate media by itself; it plans, creates/repairs/validates workflows, and packages production/tutorial artifacts that use installed generation nodes. Actual media completion still requires the relevant ComfyUI workflows to execute successfully.
- Workflow repair is conservative and does not replace missing creative nodes or invent unavailable node classes.
- Model filename ranking is not architecture verification.
- The Fountain generator is a starter, not a complete literary adaptation engine without Pi reasoning.
- The shot list is starter coverage and needs directorial review.
- The Kdenlive writer is basic and does not reproduce every version-specific feature.
- Tutorial expected-output comparison is structural, not a subjective quality judge.
- The default **Terminal** is Pi's real streaming interactive TUI on POSIX/WSL systems with the controlling-PTY backend. The secondary **Chat** view presents completed structured Pi responses rather than token-by-token text streaming; its Stop control can abort an active structured RPC request.
- Native Windows without a POSIX PTY does not yet have a ConPTY Terminal backend and therefore falls back to structured Chat.
- Real workflow/node screenshot capture requires the optional Playwright dependency and either a compatible Chromium/Chrome executable or Playwright's installed Chromium browser.
- Importing/exporting sidebar Chat JSON does not bundle the private Terminal `pi-sessions/*.jsonl` history; moving an exported JSON file to another machine is not an exact portable Terminal-session migration.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Compatibility](compatibility.md) · [Next: Development and testing](development.md)
<!-- DOC_NAV_FOOTER_END -->
