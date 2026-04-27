from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATE = ROOT / "gpt-image" / "scripts" / "generate.py"
EDIT = ROOT / "gpt-image" / "scripts" / "edit.py"


class CliDryRunTests(unittest.TestCase):
    def run_script(self, script: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(script), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_generate_dry_run_outputs_apimart_payload(self):
        result = self.run_script(
            GENERATE,
            "--prompt",
            "A minimal poster",
            "--size",
            "16:9",
            "--resolution",
            "2k",
            "--official-fallback",
            "--dry-run",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "model": "gpt-image-2",
                "prompt": "A minimal poster",
                "n": 1,
                "size": "16:9",
                "resolution": "2k",
                "official_fallback": True,
            },
        )

    def test_generate_dry_run_infers_resolution_from_legacy_pixel_size(self):
        result = self.run_script(
            GENERATE,
            "--prompt",
            "A minimal poster",
            "--size",
            "2048x1152",
            "--dry-run",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["size"], "16:9")
        self.assertEqual(payload["resolution"], "2k")
        self.assertIn("Mapped pixel size 2048x1152", result.stderr)

    def test_edit_dry_run_redacts_local_image_data_uri(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "input.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\n")
            result = self.run_script(
                EDIT,
                "--prompt",
                "Keep composition, change background",
                "--images",
                str(image),
                "--size",
                "1:1",
                "--resolution",
                "1k",
                "--dry-run",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["size"], "1:1")
        self.assertEqual(payload["resolution"], "1k")
        self.assertEqual(
            payload["image_urls"],
            [f"data:image/png;base64,<redacted 8 bytes from {image}>"],
        )

    def test_legacy_openai_flag_fails_with_clear_message(self):
        result = self.run_script(
            GENERATE,
            "--prompt",
            "A minimal poster",
            "--quality",
            "high",
            "--dry-run",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not support --quality", result.stderr)

    def test_conflicting_pixel_resolution_fails(self):
        result = self.run_script(
            GENERATE,
            "--prompt",
            "A minimal poster",
            "--size",
            "2048x1152",
            "--resolution",
            "1k",
            "--dry-run",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("maps to size 16:9", result.stderr)

    def test_invalid_4k_ratio_fails(self):
        result = self.run_script(
            GENERATE,
            "--prompt",
            "A minimal poster",
            "--size",
            "1:1",
            "--resolution",
            "4k",
            "--dry-run",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("supports --resolution 4k only", result.stderr)


if __name__ == "__main__":
    unittest.main()
