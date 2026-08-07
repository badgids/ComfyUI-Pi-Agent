# Image generation and editing

<!-- DOC_NAV_START -->
**Navigation:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Model discovery, safetensors, and GGUF](model-formats-gguf.md) · [Next: Music, speech, and audio profiles](audio-music-voice.md)
<!-- DOC_NAV_END -->


The bundled model profiles cover Qwen Image, Qwen Image Edit, Krea 2, Krea 2 Edit, FLUX.2 Klein, and Z-Image.

## Qwen Image Edit

Treat edit models separately from text-to-image models. Editing normally needs semantic image understanding and VAE appearance conditioning. Revision-specific reference methods and acceleration profiles must be validated.

## Krea 2 Edit

Krea editing may require a functional edit LoRA and adapter nodes that inject both grounded semantic conditioning and source-image latent information. A style LoRA is not a substitute for the edit LoRA.

## Reference roles

Use explicit roles such as identity, wardrobe, pose, style, lighting, environment, or composition. Do not send every reference to every available input.

## Attention and accelerators

SageAttention, KJNodes patches, Lightning LoRAs, Turbo checkpoints, and Distilled checkpoints are different concepts. Select them only when the exact model and loader combination is validated.

---

<!-- DOC_NAV_FOOTER_START -->
**Navigate:** [Project README](../README.md) · [Documentation home](index.md) · [Previous: Model discovery, safetensors, and GGUF](model-formats-gguf.md) · [Next: Music, speech, and audio profiles](audio-music-voice.md)
<!-- DOC_NAV_FOOTER_END -->
