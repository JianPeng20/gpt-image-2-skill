from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "gpt-image" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from apimart_client import (  # noqa: E402
    ApimartClient,
    ApimartError,
    build_payload,
    extract_image_urls,
    normalize_dimensions,
    normalize_resolution,
    normalize_size,
    output_paths,
    resolve_image_inputs,
    wait_for_task,
)


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class FakeTaskClient:
    def __init__(self, tasks: list[dict]):
        self.tasks = tasks
        self.calls = 0

    def get_task(self, task_id: str, language: str = "zh") -> dict:
        del task_id, language
        task = self.tasks[min(self.calls, len(self.tasks) - 1)]
        self.calls += 1
        return task


class ApimartPayloadTests(unittest.TestCase):
    def test_build_payload_includes_apimart_shape(self):
        payload = build_payload(
            prompt="Draw a clean product poster",
            size="16:9",
            resolution="2k",
            official_fallback=True,
        )

        self.assertEqual(
            payload,
            {
                "model": "gpt-image-2",
                "prompt": "Draw a clean product poster",
                "n": 1,
                "size": "16:9",
                "resolution": "2k",
                "official_fallback": True,
            },
        )

    def test_pixel_size_infers_ratio_and_resolution(self):
        self.assertEqual(normalize_dimensions("2048x1152"), ("16:9", "2k"))
        self.assertEqual(normalize_dimensions("3840x2160"), ("16:9", "4k"))
        self.assertEqual(normalize_size("1024x1536"), "2:3")

    def test_pixel_size_rejects_conflicting_resolution(self):
        with self.assertRaisesRegex(ApimartError, "maps to size 16:9"):
            normalize_dimensions("2048x1152", "1k")

    def test_rejects_unsupported_4k_ratio(self):
        with self.assertRaisesRegex(ApimartError, "supports --resolution 4k only"):
            normalize_dimensions("1:1", "4k")

    def test_rejects_invalid_resolution_and_size(self):
        with self.assertRaisesRegex(ApimartError, "Unsupported resolution"):
            normalize_resolution("3k")
        with self.assertRaisesRegex(ApimartError, "Unsupported size"):
            normalize_dimensions("7:5", "1k")

    def test_edit_payload_includes_image_urls(self):
        payload = build_payload(
            prompt="Use the second image as style",
            size="1:1",
            resolution="1k",
            image_urls=["https://example.test/image.png"],
        )

        self.assertEqual(payload["image_urls"], ["https://example.test/image.png"])


class ImageInputTests(unittest.TestCase):
    def test_resolve_image_inputs_accepts_urls_and_data_uris(self):
        inputs = ["https://example.test/a.png", "data:image/png;base64,abc"]
        self.assertEqual(resolve_image_inputs(inputs), inputs)

    def test_resolve_image_inputs_redacts_local_file_in_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "input.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")

            result = resolve_image_inputs([str(image)], dry_run=True)

        self.assertEqual(
            result,
            [f"data:image/png;base64,<redacted 8 bytes from {image}>"],
        )

    def test_resolve_image_inputs_rejects_missing_files_and_too_many_images(self):
        with self.assertRaisesRegex(ApimartError, "Image not found"):
            resolve_image_inputs(["missing.png"])
        with self.assertRaisesRegex(ApimartError, "at most 16"):
            resolve_image_inputs([f"https://example.test/{i}.png" for i in range(17)])


class TaskParsingTests(unittest.TestCase):
    def test_extract_image_urls_supports_documented_nested_url_list(self):
        task = {
            "status": "completed",
            "result": {
                "images": [
                    {"url": ["https://example.test/one.png"]},
                    {"url": "https://example.test/two.png"},
                ]
            },
        }

        self.assertEqual(
            extract_image_urls(task),
            ["https://example.test/one.png", "https://example.test/two.png"],
        )

    def test_extract_image_urls_rejects_empty_result(self):
        with self.assertRaisesRegex(ApimartError, "result.images"):
            extract_image_urls({"status": "completed", "result": {"images": []}})

    def test_wait_for_task_returns_completed_task(self):
        client = FakeTaskClient(
            [
                {"status": "processing", "progress": 50},
                {"status": "completed", "result": {"images": [{"url": ["x"]}]}},
            ]
        )

        task = wait_for_task(
            client,
            "task_123",
            language="zh",
            initial_delay=0,
            poll_interval=0,
            timeout=1,
        )

        self.assertEqual(task["status"], "completed")
        self.assertEqual(client.calls, 2)

    def test_wait_for_task_rejects_failed_task(self):
        client = FakeTaskClient([{"status": "failed", "error": {"message": "bad prompt"}}])

        with self.assertRaisesRegex(ApimartError, "bad prompt"):
            wait_for_task(
                client,
                "task_123",
                language="zh",
                initial_delay=0,
                poll_interval=0,
                timeout=1,
            )


class ApimartClientRequestTests(unittest.TestCase):
    def test_submit_image_task_posts_json_with_required_headers(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["timeout"] = timeout
            captured["method"] = request.get_method()
            captured["url"] = request.full_url
            captured["headers"] = {
                key.lower(): value for key, value in request.header_items()
            }
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse({"code": 200, "data": [{"task_id": "task_abc"}]})

        with mock.patch("apimart_client.urllib.request.urlopen", fake_urlopen):
            task_id = ApimartClient(
                api_key="test-key", base_url="https://api.apimart.ai/v1"
            ).submit_image_task({"model": "gpt-image-2"})

        self.assertEqual(task_id, "task_abc")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "https://api.apimart.ai/v1/images/generations")
        self.assertEqual(captured["headers"]["authorization"], "Bearer test-key")
        self.assertEqual(captured["headers"]["user-agent"], "curl/8.7.1")
        self.assertEqual(captured["body"], {"model": "gpt-image-2"})
        self.assertEqual(captured["timeout"], 60)

    def test_get_task_encodes_task_id_and_language(self):
        captured = {}

        def fake_urlopen(request, timeout):
            del timeout
            captured["url"] = request.full_url
            return FakeResponse({"code": 200, "data": {"status": "completed"}})

        with mock.patch("apimart_client.urllib.request.urlopen", fake_urlopen):
            task = ApimartClient(api_key="test-key", base_url="https://base.test/v1").get_task(
                "task/a b", language="zh cn"
            )

        self.assertEqual(task, {"status": "completed"})
        self.assertEqual(captured["url"], "https://base.test/v1/tasks/task%2Fa%20b?language=zh%20cn")

    def test_output_paths_preserve_extension_and_suffix_multiple_results(self):
        self.assertEqual(output_paths("out", 1), ["out.png"])
        self.assertEqual(output_paths("out.jpg", 3), ["out_1.jpg", "out_2.jpg", "out_3.jpg"])


class EnvironmentTests(unittest.TestCase):
    def test_no_apimart_key_is_written_by_tests(self):
        env_example = (ROOT / "gpt-image" / ".env.example").read_text()

        self.assertIn("APIMART_API_KEY=", env_example)
        self.assertNotIn("sk-", env_example)
        self.assertIsNone(os.environ.get("APIMART_API_KEY_FOR_TEST_ASSERTION_ONLY"))


if __name__ == "__main__":
    unittest.main()
