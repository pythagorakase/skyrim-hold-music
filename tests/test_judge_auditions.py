import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import judge_auditions as judge


class JudgeAuditionsTests(unittest.TestCase):
    def setUp(self):
        rates = patch.object(judge, "RATES_VALID_THROUGH", "9999-12-31")
        rates.start()
        self.addCleanup(rates.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        audio = b"synthetic audio fixture; never sent to a provider"
        (self.root / "anonymous.mp3").write_bytes(audio)
        self.corpus = {"a01": {
            "audio_path": "anonymous.mp3", "sha256": judge.digest(audio),
            "duration_seconds": 60, "historical_target": "PRIVATE TARGET",
            "take_id": "PRIVATE TAKE ID", "profile_id": "PRIVATE HOLD",
        }}
        self.trial = {"id": "test", "mode": "candidates", "audio_ids": ["a01", "a01"]}
        self.manifest = self.root / "manifest.json"
        judge.dump(self.manifest, {"corpus": self.corpus, "trials": [self.trial],
                                  "max_requests": 1, "budget_usd": 1})

    def test_payload_omits_provenance_and_preserves_duplicate_audio(self):
        payload = judge.build_request(judge.MODELS[0], self.trial, self.corpus, self.root)
        wire = json.dumps(payload)
        self.assertNotIn("PRIVATE", wire)
        self.assertNotIn("anonymous.mp3", wire)
        self.assertFalse(payload["store"])
        self.assertNotIn("previous_interaction_id", payload)
        clips = [p["data"] for p in payload["input"] if p["type"] == "audio"]
        self.assertEqual(len(clips), 2)
        self.assertEqual(clips[0], clips[1])

    def test_changed_audio_is_rejected_before_transmission(self):
        (self.root / "anonymous.mp3").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "Audio changed"):
            judge.build_request(judge.MODELS[0], self.trial, self.corpus, self.root)

    def test_custom_protocol_preserves_anonymous_audio_and_exact_schema(self):
        prompt = "Judge these fictional adaptations against the supplied musical requirements."
        schema = judge.object_schema({"closest_profile": {"type": "string", "enum": ["one", "two"]}})
        payload = judge.build_request(judge.MODELS[0], self.trial, self.corpus,
                                      self.root, prompt=prompt, schema=schema)
        self.assertEqual(payload["input"][0]["text"], prompt)
        self.assertEqual(payload["response_format"]["schema"], schema)
        self.assertNotIn("PRIVATE", json.dumps(payload))
        self.assertEqual(len([p for p in payload["input"] if p["type"] == "audio"]), 2)

    def test_oversized_custom_protocol_is_rejected_before_network_or_credentials(self):
        data = json.loads(self.manifest.read_text())
        data["judge_prompt"] = "é" * 13000
        judge.dump(self.manifest, data)
        with patch.object(judge, "read_key") as key, \
                patch.object(judge, "build_opener") as transport:
            with self.assertRaisesRegex(ValueError, "input allowance"):
                judge.run(self.manifest, execute=True, models=[judge.MODELS[0]])
        key.assert_not_called()
        transport.assert_not_called()

    def test_cost_includes_thinking_and_missing_usage_is_unknown(self):
        self.assertAlmostEqual(judge.usage_cost(judge.MODELS[0], {
            "total_input_tokens": 1000, "total_output_tokens": 200,
            "total_thought_tokens": 300}), .008)
        self.assertIsNone(judge.usage_cost(judge.MODELS[0], {}))

    def test_attempted_request_is_never_retried(self):
        prior = self.root / "requests" / ("test__" + judge.MODELS[0])
        prior.mkdir(parents=True)
        with patch.object(judge, "read_key", return_value="test key"), \
                patch.object(judge, "build_opener") as transport:
            judge.run(self.manifest, execute=True, models=[judge.MODELS[0]])
        transport.assert_not_called()

    def test_spending_ceiling_blocks_network(self):
        data = json.loads(self.manifest.read_text())
        data["budget_usd"] = .00001
        judge.dump(self.manifest, data)
        with patch.object(judge, "read_key", return_value="test key"), \
                patch.object(judge, "build_opener") as transport:
            with self.assertRaisesRegex(ValueError, "spending ceiling"):
                judge.run(self.manifest, execute=True, models=[judge.MODELS[0]])
        transport.assert_not_called()

    def test_dry_run_never_reads_credentials_or_calls_network(self):
        with patch.object(judge, "read_key") as key, \
                patch.object(judge, "build_opener") as transport:
            judge.run(self.manifest)
        key.assert_not_called()
        transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
