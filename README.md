# GPT Image - APIMart Skill

CLI scripts and skill instructions for generating and editing images with APIMart's `gpt-image-2` image generation endpoint.

The APIMart interface is asynchronous: the scripts submit `POST /v1/images/generations`, poll `GET /v1/tasks/{task_id}`, then download image URLs from the completed task result.

## Requirements

| Requirement | Purpose |
| --- | --- |
| [uv](https://docs.astral.sh/uv/) | Runs the Python scripts directly with PEP 723 metadata. |
| APIMart API key | Used as `APIMART_API_KEY`. |
| Codex or Claude Code | Optional; the scripts also work standalone. |

## Setup

Clone or copy the `gpt-image/` directory into your skills directory, then provide credentials:

```bash
export APIMART_API_KEY="your-apimart-key"
export APIMART_BASE_URL="https://api.apimart.ai/v1"
```

Or use `gpt-image/.env`:

```bash
cp gpt-image/.env.example gpt-image/.env
# edit APIMART_API_KEY in gpt-image/.env
```

The scripts also accept `OPENAI_API_KEY` and `OPENAI_BASE_URL` as backward-compatible fallbacks, but new setups should use the APIMart names.

## Usage

Generate from scratch:

```bash
uv run gpt-image/scripts/generate.py \
  --prompt "A vintage 1960s travel poster for Kyoto in autumn" \
  --size 2:3 \
  --resolution 1k \
  --output kyoto.png
```

Edit an existing image:

```bash
uv run gpt-image/scripts/edit.py \
  --prompt "Replace the sky with a dramatic thunderstorm. Keep everything else identical." \
  --images photo.jpg \
  --size 3:2 \
  --resolution 1k \
  --output photo-stormy.png
```

Multi-image compositing:

```bash
uv run gpt-image/scripts/edit.py \
  --prompt "Place the dog from Image 2 next to the woman in Image 1. Match lighting and scale." \
  --images scene.png dog.png \
  --size 3:2 \
  --resolution 1k \
  --output composite.png
```

Dry-run the exact payload shape without using an API key:

```bash
uv run gpt-image/scripts/generate.py \
  --prompt "Original logo for Field & Flour" \
  --size 1:1 \
  --dry-run
```

## Flag Reference

Both scripts support:

| Flag | Required | Default | Notes |
| --- | --- | --- | --- |
| `--prompt` | yes | - | Generation or edit instruction. |
| `--output` | no | `output.png` | Output image path. |
| `--size` | no | `auto` | Ratio value accepted by APIMart. |
| `--resolution` | no | `1k` | `1k`, `2k`, or `4k`. Legacy pixel `--size` values infer this automatically. |
| `--official-fallback` | no | off | Sends `official_fallback: true`. |
| `--no-wait` | no | off | Submit and print `task_id` only. |
| `--initial-delay` | no | `12` | Seconds before first poll. |
| `--poll-interval` | no | `4` | Seconds between polls. |
| `--timeout` | no | `180` | Max seconds to wait. |
| `--language` | no | `zh` | Task error language. |
| `--dry-run` | no | off | Print JSON payload without network calls. |
| `--env-file` | no | `gpt-image/.env` | Alternate env file. |

`edit.py` also requires:

| Flag | Required | Default | Notes |
| --- | --- | --- | --- |
| `--images` | yes | - | 1-16 local image paths, HTTP(S) URLs, or `data:image/...` URIs. |

## Size and Resolution Values

APIMart `gpt-image-2` uses ratio notation:

`auto`, `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `5:4`, `4:5`, `2:1`, `1:2`, `21:9`, `9:21`.

`--resolution` accepts `1k`, `2k`, and `4k`. APIMart only supports `4k` with `16:9`, `9:16`, `2:1`, `1:2`, `21:9`, and `9:21`; the scripts reject unsupported 4K combinations before making a network call.

The scripts map common old pixel sizes when exact, for example `1024x1024 -> size=1:1, resolution=1k`, `2048x1152 -> size=16:9, resolution=2k`, and `3840x2160 -> size=16:9, resolution=4k`. Unsupported pixel dimensions fail with a clear error.

## APIMart Differences From OpenAI SDK Examples

- `n` is fixed at `1`.
- `quality`, `output_format`, and `output_compression` are not exposed by this APIMart endpoint.
- Local reference images are converted to base64 data URIs and sent as `image_urls`.
- The result is delivered through task polling, not a synchronous SDK response.
- Transparent background and `input_fidelity` flags are not part of this endpoint.

## Tests

Run offline unit and CLI tests:

```bash
python3 -m unittest discover -s tests
```

Optional live APIMart validation submits a real generation task and may incur API cost:

```bash
APIMART_LIVE_TESTS=1 APIMART_API_KEY="..." python3 -m unittest tests.test_live_apimart
```

## Prompting

See [`gpt-image/references/prompting-guide.md`](gpt-image/references/prompting-guide.md). The main patterns are:

1. Write scene, subject, details, constraints in that order.
2. For edits, explicitly state what changes and what must stay unchanged.
3. Quote literal text and specify typography, placement, and hierarchy.
4. For multi-image inputs, reference each image by index and role.

## Project Layout

```text
gpt-image/
├── SKILL.md
├── .env.example
├── scripts/
│   ├── apimart_client.py
│   ├── generate.py
│   └── edit.py
└── references/
    └── prompting-guide.md
```

## Packaging as a `.skill` File

From the repo root:

```bash
zip -r gpt-image.skill gpt-image/ -x "*.DS_Store" -x "gpt-image/.env"
```

Install the bundle by unzipping it into your skills directory, then provide `APIMART_API_KEY` on the target machine.

## License

MIT.
