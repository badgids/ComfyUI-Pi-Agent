# Model formats and GGUF

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Workflow intelligence](workflow-intelligence.md) · [Next: Image generation and editing profiles](image-generation-editing.md)
<!-- DOC_NAV_END -->


## Model identity is larger than a filename

A complete model configuration can include a diffusion model, text encoder, vision encoder, projector, VAE, codec, LoRA, loader node, and sampling profile.

## Resolver behavior

`Pi Model Resolver` searches installed filenames. It ranks names that contain family tokens and can add a preference for `safetensors` or `gguf`.

This ranking is discovery help. Before execution, confirm:

- architecture;
- family and revision;
- Base, SFT, Turbo, or Distilled variant;
- component role;
- latent format;
- conditioning nodes;
- companion files;
- LoRA support for the selected loader.

## GGUF substitution

A proper substitution may change loader nodes. It may also require a GGUF text encoder or multimodal projector. Never change only the extension and assume the workflow is repaired.

## Mixed formats

Mixed workflows are valid when the loader supports them, for example a GGUF diffusion model with a safetensors VAE. Each component is resolved independently.

## MiniMax H3 Director and GGUF

The dedicated MiniMax H3 Director integration does not assume a GGUF model is a drop-in replacement for the Director pack's documented safetensors checkpoints. ComfyUI-Pi may propose a GGUF substitution only when the running ComfyUI installation exposes a compatible MiniMax H3 GGUF loader and the complete conditioning/decode path can be validated. Otherwise it reports the candidate as unavailable or unvalidated instead of rewriting the Director workflow blindly.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Workflow intelligence](workflow-intelligence.md) · [Next: Image generation and editing profiles](image-generation-editing.md)
<!-- DOC_NAV_FOOTER_END -->
