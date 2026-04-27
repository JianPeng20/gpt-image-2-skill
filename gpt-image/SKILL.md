---
name: gpt-image
description: Generate and edit images through APIMart's gpt-image-2 image API using bundled CLI scripts. Use this skill whenever the user asks to generate, create, edit, modify, composite, restyle, or transform images, including logos, ads, UI mockups, infographics, product mockups, virtual try-on, style transfer, object removal, translation, sketch-to-render, lighting changes, and multi-image compositing. Always use these scripts for GPT image work instead of calling the image API from memory.
---

# GPT Image Skill

Generate and edit images with APIMart's `gpt-image-2` generation endpoint.

The APIMart interface is asynchronous:

1. `POST /v1/images/generations` submits a task.
2. `GET /v1/tasks/{task_id}` is polled until completion.
3. Result URLs from `data.result.images[*].url[0]` are downloaded to `--output`.

## Setup

No install step is needed. Scripts use PEP 723 inline metadata, and `uv run` executes them directly.

The scripts read credentials in this order:

1. `APIMART_API_KEY` from the shell environment.
2. `APIMART_API_KEY` from `<SKILL_DIR>/.env`.
3. `OPENAI_API_KEY` as a backward-compatible fallback.

Optional base URL:

```bash
APIMART_BASE_URL=https://api.apimart.ai/v1
```

## Script Choice

| Script | Purpose | Use when |
| --- | --- | --- |
| `scripts/generate.py` | Text to image | No input image is provided. |
| `scripts/edit.py` | Text + reference images to image | The user provides 1-16 local paths, URLs, or image data URIs. |

## generate.py

```bash
uv run <SKILL_DIR>/scripts/generate.py \
  --prompt "Your prompt here" \
  --size 2:3 \
  --resolution 1k \
  --output /path/to/output.png
```

| Flag | Required | Default | Notes |
| --- | --- | --- | --- |
| `--prompt` | Yes | - | Generation prompt. |
| `--output` | No | `output.png` | Saves one image. If the API returns multiple URLs, suffixes `_1`, `_2`, etc. |
| `--size` | No | `auto` | APIMart ratio value: `auto`, `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `5:4`, `4:5`, `2:1`, `1:2`, `21:9`, `9:21`. |
| `--resolution` | No | `1k` | APIMart resolution value: `1k`, `2k`, or `4k`. Old pixel `--size` values infer this automatically. |
| `--official-fallback` | No | off | Sends `official_fallback: true`. |
| `--no-wait` | No | off | Submit and print `task_id` without polling/downloading. |
| `--initial-delay` | No | `12` | Seconds before the first task poll. |
| `--poll-interval` | No | `4` | Seconds between task polls. |
| `--timeout` | No | `180` | Max seconds to wait. |
| `--language` | No | `zh` | Task error language. |
| `--dry-run` | No | off | Print JSON payload without network calls or API key requirement. |
| `--env-file` | No | `<SKILL_DIR>/.env` | Alternate env file. |

## edit.py

```bash
uv run <SKILL_DIR>/scripts/edit.py \
  --prompt "Your edit instruction" \
  --images input1.png input2.png \
  --size 2:3 \
  --resolution 1k \
  --output /path/to/output.png
```

`edit.py` uses the same flags as `generate.py`, plus:

| Flag | Required | Default | Notes |
| --- | --- | --- | --- |
| `--images` | Yes | - | 1-16 local image paths, `http(s)` URLs, or `data:image/...` URIs. Local files are base64 encoded into APIMart `image_urls`. |

Reference images by index in prompts: "Image 1 is the scene, Image 2 is the style reference."

## APIMart Compatibility

- `gpt-image-2` only supports `n: 1`; the scripts reject `--n` values other than `1`.
- The referenced APIMart generation endpoint uses ratio-style `size` plus `resolution` (`1k`, `2k`, `4k`), not OpenAI pixel dimensions. Common old pixel sizes are mapped to both fields when exact; unsupported pixel sizes fail with a clear error.
- APIMart `4k` output is accepted only with `16:9`, `9:16`, `2:1`, `1:2`, `21:9`, and `9:21`; the scripts reject invalid 4K ratio combinations before calling the API.
- The APIMart `gpt-image-2` generation endpoint does not expose `quality`, `output_format`, `output_compression`, transparency, or `input_fidelity`; the scripts reject old flags instead of silently ignoring them.
- Result files are downloaded from APIMart result URLs. The URL content determines the actual image bytes; use the `--output` extension you want for local naming.

## Prompting

Before writing a prompt, read `references/prompting-guide.md`.

Prompt principles:

1. Structure: scene/background, subject, key details, constraints.
2. Be specific: materials, textures, visual medium, lighting, framing.
3. For edits, state both what changes and what must remain unchanged.
4. Quote literal text and specify typography/placement.
5. For multi-image edits, identify each image by index and role.

## Workflow Examples

### Generate: Infographic

```bash
uv run <SKILL_DIR>/scripts/generate.py \
  --prompt "Create a detailed infographic about [topic]. Include [data points]. Clean layout, clear labels, readable text. White background." \
  --size 2:3 \
  --resolution 2k \
  --output infographic.png
```

### Generate: Photorealistic Image

```bash
uv run <SKILL_DIR>/scripts/generate.py \
  --prompt "Create a photorealistic photograph of [subject]. [Camera/lens details]. [Lighting]. Natural texture, no retouching." \
  --size 2:3 \
  --resolution 1k \
  --output photo.png
```

### Generate: Logo

```bash
uv run <SKILL_DIR>/scripts/generate.py \
  --prompt "Create an original logo for [brand]. [Brand personality]. Clean vector-like shapes, strong silhouette, flat design, plain background. No watermark." \
  --size 1:1 \
  --resolution 1k \
  --output logo.png
```

### Edit: Product Mockup

```bash
uv run <SKILL_DIR>/scripts/edit.py \
  --prompt "Extract the product, place it on a plain white opaque background. Preserve product geometry and label legibility. Add subtle contact shadow. Do not restyle." \
  --images product_photo.png \
  --size 2:3 \
  --resolution 1k \
  --output mockup.png
```

### Edit: Virtual Try-On

```bash
uv run <SKILL_DIR>/scripts/edit.py \
  --prompt "Dress the person using the provided clothing images. Do not change face, body shape, pose, or identity. Replace only clothing with realistic fit. Match lighting and shadows." \
  --images person.png top.png jacket.png shoes.png \
  --size 2:3 \
  --resolution 1k \
  --output tryon.png
```

### Edit: Scene Compositing

```bash
uv run <SKILL_DIR>/scripts/edit.py \
  --prompt "Place the element from Image 2 into Image 1 next to [anchor]. Match lighting, perspective, scale, and shadows. Do not change anything else." \
  --images scene.png element.png \
  --size 2:3 \
  --resolution 1k \
  --output composite.png
```

## Error Handling

The scripts validate:

- API key presence for real calls.
- APIMart-compatible `size`.
- APIMart-compatible `resolution`.
- Unsupported legacy OpenAI flags.
- `--n 1`.
- Input image existence and image count for edit mode.
- Task status and APIMart error payloads.

After saving, surface the output path(s) to the user. If the user supplied input images, use the exact paths they provided; do not move or copy them.
