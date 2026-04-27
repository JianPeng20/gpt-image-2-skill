#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
gpt-image edit - image editing through APIMart gpt-image-2 image_urls.

Run with: uv run edit.py --prompt "..." --images file1.png [file2.png ...] [options]
"""

import argparse
import sys

from apimart_client import (
    ApimartClient,
    ApimartError,
    build_payload,
    default_env_path,
    download_urls,
    extract_image_urls,
    load_env,
    print_dry_run,
    reject_unsupported_generation_args,
    resolve_image_inputs,
    wait_for_task,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Edit images with APIMart gpt-image-2")
    parser.add_argument("--prompt", required=True, help="Editing instruction prompt")
    parser.add_argument("--images", required=True, nargs="+", help="Input image paths, URLs, or data URIs")
    parser.add_argument("--output", default="output.png", help="Output file path (default: output.png)")
    parser.add_argument("--size", default="auto", help="Image ratio: auto, 1:1, 16:9, 2:3, etc.")
    parser.add_argument(
        "--resolution",
        default=None,
        help="Image resolution: 1k, 2k, or 4k. Defaults to 1k unless inferred from legacy pixel --size.",
    )
    parser.add_argument("--official-fallback", action="store_true", help="Enable APIMart official fallback")
    parser.add_argument("--no-wait", action="store_true", help="Submit task and print task_id only")
    parser.add_argument("--initial-delay", type=float, default=12, help="Seconds before first poll (default: 12)")
    parser.add_argument("--poll-interval", type=float, default=4, help="Seconds between polls (default: 4)")
    parser.add_argument("--timeout", type=float, default=180, help="Max seconds to wait for completion (default: 180)")
    parser.add_argument("--language", default="zh", help="Task error language for APIMart (default: zh)")
    parser.add_argument("--dry-run", action="store_true", help="Print APIMart JSON payload without network calls")
    parser.add_argument("--env-file", default=None, help="Path to .env file")

    # Legacy OpenAI SDK flags are parsed only so we can fail with a clear message.
    parser.add_argument("--quality", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--output-format", dest="output_format", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--output-compression", dest="output_compression", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--n", type=int, default=1, help=argparse.SUPPRESS)
    return parser.parse_args()


def main():
    args = parse_args()

    try:
        reject_unsupported_generation_args(args)
        image_urls = resolve_image_inputs(args.images, dry_run=args.dry_run)
        payload = build_payload(
            prompt=args.prompt,
            size=args.size,
            resolution=args.resolution,
            image_urls=image_urls,
            official_fallback=args.official_fallback,
        )

        if args.dry_run:
            print_dry_run(payload)
            return []

        load_env(args.env_file or default_env_path())
        client = ApimartClient()

        print(
            f"Submitting APIMart gpt-image-2 edit task with {len(image_urls)} "
            f"reference image(s), size={payload['size']}, resolution={payload['resolution']}...",
            flush=True,
        )
        task_id = client.submit_image_task(payload)
        print(f"Task ID: {task_id}", flush=True)

        if args.no_wait:
            return [task_id]

        task = wait_for_task(
            client,
            task_id,
            language=args.language,
            initial_delay=args.initial_delay,
            poll_interval=args.poll_interval,
            timeout=args.timeout,
        )
        urls = extract_image_urls(task)
        return download_urls(urls, args.output)
    except ApimartError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
