"""Independent regression checks for knowledge boundaries and retold stories."""
import copy
import json
from pathlib import Path
import unittest

from hold_music.repertoire import plan


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "repertoire" / "scandal.json"


def snapshot():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class RepertoireKnowledgeReviewTests(unittest.TestCase):
    def test_duplicate_receipt_does_not_change_equivalent_work_key(self):
        data = snapshot()
        original = plan(data)
        duplicate = copy.deepcopy(data["observations"][0])
        duplicate["id"] = "aaa-retrieved-copy"
        data["observations"].append(duplicate)
        repeated = plan(data)
        self.assertEqual(repeated["action"], "compose_lyrics")
        self.assertEqual(original["work_key"], repeated["work_key"])
        self.assertEqual(repeated["subject"]["evidence"], "rumor")

    def test_changed_event_key_cannot_refresh_the_same_topic(self):
        data = snapshot()
        original = data["observations"][0]
        original.update(happened_at=1, learned_at=2)
        repeated = copy.deepcopy(original)
        repeated.update(id="new-delivery", event_id="different-event-key", happened_at=118, learned_at=119)
        data["observations"].append(repeated)
        decision = plan(data)
        self.assertEqual(decision["action"], "play_recording")
        self.assertIsNone(decision["lyric_brief"])

    def test_another_bards_direct_evidence_cannot_confirm_this_rumor(self):
        data = snapshot()
        direct = copy.deepcopy(data["observations"][0])
        direct.update(id="aaa-witness", performer_id="another-bard", evidence="direct",
                      summary="I personally witnessed a meeting.", interest=1, local_relevance=1)
        data["observations"].append(direct)
        decision = plan(data)
        self.assertEqual(decision["subject"]["evidence"], "rumor")
        self.assertNotIn("aaa-witness", decision["subject"]["source_observation_ids"])

    def test_later_direct_evidence_does_not_refresh_an_old_claim(self):
        data = snapshot()
        original = data["observations"][0]
        original.update(happened_at=1, learned_at=2)
        direct = copy.deepcopy(original)
        direct.update(id="later-direct", evidence="direct", happened_at=118, learned_at=119)
        data["observations"].append(direct)
        decision = plan(data)
        self.assertEqual(decision["action"], "play_recording")
        self.assertIsNone(decision["lyric_brief"])

    def test_unknown_knowledge_age_is_not_replaced_with_now(self):
        data = snapshot()
        data["observations"][0].update(happened_at=None, learned_at=None)
        self.assertEqual(plan(data)["action"], "play_recording")

    def test_foreign_save_song_does_not_grant_same_named_local_song(self):
        data = snapshot()
        data["observations"] = []
        foreign = copy.deepcopy(data["compositions"][0])
        foreign["save_id"] = "another-save"
        data["compositions"][0]["known_by"] = []
        data["compositions"].append(foreign)
        decision = plan(data)
        self.assertEqual(decision["action"], "no_selection")
        self.assertIsNone(decision["recording_id"])

    def test_rearrangement_reuses_known_words_without_private_observations(self):
        data = snapshot()
        data["observations"] = []
        data["request"]["voice"] = "new-rendition-voice"
        data["compositions"][0]["source_observation_ids"] = ["composer-private-memory"]
        before = copy.deepcopy(data)
        decision = plan(data)
        self.assertEqual(decision["action"], "generate_recording")
        self.assertIsNone(decision["lyric_brief"])
        self.assertTrue(decision["recording_brief"]["reuse_existing_lyrics"])
        self.assertEqual(data, before)


if __name__ == "__main__":
    unittest.main()
