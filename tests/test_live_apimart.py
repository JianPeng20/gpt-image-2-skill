from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "gpt-image" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from apimart_client import ApimartClient, build_payload  # noqa: E402


@unittest.skipUnless(
    os.environ.get("APIMART_LIVE_TESTS") == "1",
    "set APIMART_LIVE_TESTS=1 to run paid APIMart integration tests",
)
class ApimartLiveTests(unittest.TestCase):
    def test_submit_generation_task_returns_task_id(self):
        if not os.environ.get("APIMART_API_KEY"):
            self.skipTest("APIMART_API_KEY is required for live APIMart tests")

        payload = build_payload(
            prompt="A simple flat blue square centered on a white background.",
            size="1:1",
            resolution="1k",
        )

        task_id = ApimartClient().submit_image_task(payload)

        self.assertIsInstance(task_id, str)
        self.assertTrue(task_id)


if __name__ == "__main__":
    unittest.main()
