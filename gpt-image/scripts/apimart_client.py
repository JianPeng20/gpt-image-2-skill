"""Shared APIMart helpers for gpt-image-2 CLI scripts."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_BASE_URL = "https://api.apimart.ai/v1"
MODEL = "gpt-image-2"
VALID_SIZES = {
    "auto",
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "5:4",
    "4:5",
    "2:1",
    "1:2",
    "21:9",
    "9:21",
}

VALID_RESOLUTIONS = {"1k", "2k", "4k"}

FOUR_K_SIZES = ("16:9", "9:16", "2:1", "1:2", "21:9", "9:21")

PIXEL_SIZE_TO_SPEC = {
    "1024x1024": ("1:1", "1k"),
    "1536x1024": ("3:2", "1k"),
    "1024x1536": ("2:3", "1k"),
    "1024x768": ("4:3", "1k"),
    "768x1024": ("3:4", "1k"),
    "1280x1024": ("5:4", "1k"),
    "1024x1280": ("4:5", "1k"),
    "1536x864": ("16:9", "1k"),
    "864x1536": ("9:16", "1k"),
    "2048x1024": ("2:1", "1k"),
    "1024x2048": ("1:2", "1k"),
    "2016x864": ("21:9", "1k"),
    "864x2016": ("9:21", "1k"),
    "2048x2048": ("1:1", "2k"),
    "2048x1360": ("3:2", "2k"),
    "1360x2048": ("2:3", "2k"),
    "2048x1536": ("4:3", "2k"),
    "1536x2048": ("3:4", "2k"),
    "2560x2048": ("5:4", "2k"),
    "2048x2560": ("4:5", "2k"),
    "2048x1152": ("16:9", "2k"),
    "1152x2048": ("9:16", "2k"),
    "2688x1344": ("2:1", "2k"),
    "1344x2688": ("1:2", "2k"),
    "2688x1152": ("21:9", "2k"),
    "1152x2688": ("9:21", "2k"),
    "3840x2160": ("16:9", "4k"),
    "2160x3840": ("9:16", "4k"),
    "3840x1920": ("2:1", "4k"),
    "1920x3840": ("1:2", "4k"),
    "3840x1648": ("21:9", "4k"),
    "1648x3840": ("9:21", "4k"),
}

PIXEL_SIZE_TO_RATIO = {
    pixel_size: spec[0] for pixel_size, spec in PIXEL_SIZE_TO_SPEC.items()
}

PENDING_STATUSES = {"submitted", "pending", "processing", "in_progress"}
FAILED_STATUSES = {"failed", "cancelled"}


class ApimartError(RuntimeError):
    """Raised for user-facing APIMart CLI errors."""


def load_env(env_path: str | None) -> None:
    """Load key=value pairs from a .env file without overriding exported vars."""
    if not env_path or not os.path.exists(env_path):
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def default_env_path() -> str:
    return str(Path(__file__).resolve().parent.parent / ".env")


def get_api_key() -> str:
    key = os.environ.get("APIMART_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ApimartError(
            "APIMART_API_KEY not found. Add it to .env or export it. "
            "OPENAI_API_KEY is accepted as a backward-compatible fallback."
        )
    return key


def get_base_url() -> str:
    return (
        os.environ.get("APIMART_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")


def normalize_resolution(resolution: str | None) -> str:
    value = (resolution or "1k").strip().lower()
    if value in VALID_RESOLUTIONS:
        return value
    raise ApimartError(
        f"Unsupported resolution '{resolution}'. Valid values: "
        + ", ".join(sorted(VALID_RESOLUTIONS))
    )


def normalize_size(size: str) -> str:
    return normalize_dimensions(size=size, resolution=None)[0]


def normalize_dimensions(size: str | None, resolution: str | None = None) -> tuple[str, str]:
    value = (size or "auto").strip().lower()
    explicit_resolution = resolution is not None and resolution.strip() != ""
    resolution_value = normalize_resolution(resolution)

    if value in VALID_SIZES:
        size_value = value
    elif "x" in value:
        spec = PIXEL_SIZE_TO_SPEC.get(value)
        if spec:
            size_value, inferred_resolution = spec
            if explicit_resolution and resolution_value != inferred_resolution:
                raise ApimartError(
                    f"Pixel size '{size}' maps to size {size_value} with "
                    f"resolution {inferred_resolution}, but --resolution "
                    f"{resolution_value} was provided."
                )
            resolution_value = inferred_resolution
            print(
                f"Mapped pixel size {value} to APIMart size {size_value} "
                f"with resolution {resolution_value}.",
                file=sys.stderr,
            )
        else:
            raise ApimartError(
                f"Unsupported pixel size '{size}'. APIMart gpt-image-2 accepts "
                "ratio-style --size plus --resolution. Use values such as "
                "--size 1:1 --resolution 1k, --size 16:9 --resolution 2k, "
                "or a documented legacy pixel size."
            )
    else:
        raise ApimartError(
            f"Unsupported size '{size}'. Valid values: "
            + ", ".join(sorted(VALID_SIZES))
        )

    if resolution_value == "4k" and size_value not in FOUR_K_SIZES and size_value != "auto":
        raise ApimartError(
            "APIMart gpt-image-2 supports --resolution 4k only with sizes: "
            + ", ".join(FOUR_K_SIZES)
        )

    return size_value, resolution_value


def reject_unsupported_generation_args(args) -> None:
    unsupported = []
    if getattr(args, "quality", None) is not None:
        unsupported.append("--quality")
    if getattr(args, "output_format", None) is not None:
        unsupported.append("--output-format")
    if getattr(args, "output_compression", None) is not None:
        unsupported.append("--output-compression")
    if unsupported:
        raise ApimartError(
            "APIMart gpt-image-2 generation does not support "
            + ", ".join(unsupported)
            + ". Remove these flags."
        )
    if getattr(args, "n", 1) != 1:
        raise ApimartError("APIMart gpt-image-2 generation supports only --n 1.")


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def is_data_uri(value: str) -> bool:
    return value.startswith("data:image/")


def image_path_to_data_uri(path: str, dry_run: bool = False) -> str:
    mime, _ = mimetypes.guess_type(path)
    if not mime or not mime.startswith("image/"):
        raise ApimartError(f"Cannot infer image MIME type from path: {path}")

    if dry_run:
        size = os.path.getsize(path)
        return f"data:{mime};base64,<redacted {size} bytes from {path}>"

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def resolve_image_inputs(images: list[str], dry_run: bool = False) -> list[str]:
    if len(images) > 16:
        raise ApimartError("APIMart gpt-image-2 supports at most 16 reference images.")

    image_urls = []
    for image in images:
        if is_url(image) or is_data_uri(image):
            image_urls.append(image)
            continue
        if not os.path.exists(image):
            raise ApimartError(f"Image not found: {image}")
        image_urls.append(image_path_to_data_uri(image, dry_run=dry_run))
    return image_urls


def build_payload(
    *,
    prompt: str,
    size: str,
    resolution: str | None = None,
    image_urls: list[str] | None = None,
    official_fallback: bool = False,
) -> dict:
    size_value, resolution_value = normalize_dimensions(size=size, resolution=resolution)
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "n": 1,
        "size": size_value,
        "resolution": resolution_value,
    }
    if image_urls:
        payload["image_urls"] = image_urls
    if official_fallback:
        payload["official_fallback"] = True
    return payload


class ApimartClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or get_api_key()
        self.base_url = (base_url or get_base_url()).rstrip("/")

    def submit_image_task(self, payload: dict) -> str:
        response = self._request_json("POST", "/images/generations", payload)
        data = response.get("data")
        if not isinstance(data, list) or not data:
            raise ApimartError(f"Unexpected generation response: {response}")
        task_id = data[0].get("task_id")
        if not task_id:
            raise ApimartError(f"Generation response did not include task_id: {response}")
        return task_id

    def get_task(self, task_id: str, language: str = "zh") -> dict:
        path = (
            f"/tasks/{urllib.parse.quote(task_id, safe='')}"
            f"?language={urllib.parse.quote(language, safe='')}"
        )
        response = self._request_json("GET", path)
        data = response.get("data")
        if not isinstance(data, dict):
            raise ApimartError(f"Unexpected task response: {response}")
        return data

    def _request_json(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        body = None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "User-Agent": "curl/8.7.1",
        }
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            raise ApimartError(f"HTTP {e.code} from APIMart: {format_error_body(raw)}") from None
        except urllib.error.URLError as e:
            raise ApimartError(f"Network error calling APIMart: {e.reason}") from None

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            raise ApimartError(f"APIMart returned non-JSON response: {raw[:500]}") from None

        code = result.get("code")
        if code not in (None, 200):
            raise ApimartError(f"APIMart error response: {json.dumps(result, ensure_ascii=False)}")
        return result


def format_error_body(raw: str) -> str:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return raw[:1000]
    return json.dumps(parsed, ensure_ascii=False)


def wait_for_task(
    client: ApimartClient,
    task_id: str,
    *,
    language: str,
    initial_delay: float,
    poll_interval: float,
    timeout: float,
) -> dict:
    if initial_delay > 0:
        print(f"Waiting {initial_delay:g}s before first task poll...", flush=True)
        time.sleep(initial_delay)

    started = time.monotonic()
    while True:
        task = client.get_task(task_id, language=language)
        status = str(task.get("status", "")).lower()
        progress = task.get("progress")
        progress_text = f", progress={progress}%" if progress is not None else ""
        print(f"Task {task_id}: status={status or 'unknown'}{progress_text}", flush=True)

        if status == "completed":
            return task
        if status in FAILED_STATUSES:
            error = task.get("error") or {}
            if isinstance(error, dict):
                message = error.get("message") or json.dumps(error, ensure_ascii=False)
            else:
                message = str(error)
            message = message or "unknown error"
            raise ApimartError(f"Task {task_id} {status}: {message}")
        if status and status not in PENDING_STATUSES:
            raise ApimartError(f"Task {task_id} returned unknown status '{status}': {task}")
        if time.monotonic() - started >= timeout:
            raise ApimartError(f"Timed out after {timeout:g}s waiting for task {task_id}.")
        time.sleep(poll_interval)


def extract_image_urls(task: dict) -> list[str]:
    images = (((task.get("result") or {}).get("images")) or [])
    urls = []
    for image in images:
        values = image.get("url") if isinstance(image, dict) else None
        if isinstance(values, list) and values:
            urls.append(values[0])
        elif isinstance(values, str):
            urls.append(values)
    if not urls:
        raise ApimartError(f"Completed task did not include result.images URLs: {task}")
    return urls


def output_paths(output: str, count: int) -> list[str]:
    base, ext = os.path.splitext(output)
    if not ext:
        ext = ".png"
    if count == 1:
        return [f"{base}{ext}"]
    return [f"{base}_{index}{ext}" for index in range(1, count + 1)]


def download_urls(urls: list[str], output: str) -> list[str]:
    paths = output_paths(output, len(urls))
    for url, path in zip(urls, paths):
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "curl/8.7.1"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response, open(path, "wb") as f:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        except urllib.error.URLError as e:
            raise ApimartError(f"Failed to download result image {url}: {e.reason}") from None
        print(f"  Saved: {path}", flush=True)
    return paths


def print_dry_run(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
