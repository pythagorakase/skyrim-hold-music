"""Offline repertoire contracts: knowledge, provenance, reuse and job planning."""
from copy import deepcopy
import json
import unittest

from hold_music import Snapshot, plan


def request(**changes):
    value = dict(tradition="bosmer_leaping_tales", arrangement="lute_voice", mode="lyrical",
                 voice="bard-voice-v1", recipe_id="recipe-v1", model_id="model-v1")
    value.update(changes)
    return value


def scoped(**fields):
    return dict(save_id="save-a", world_id="world-a", **fields)


def composition(**changes):
    value = scoped(id="song-market", title="Market Day", tradition="bosmer_leaping_tales",
                   mode="lyrical", known_by=["bard-a"], composer_id="another-bard", created_at=20,
                   lyrics="A cart of apples crossed the square.", topic_id=None,
                   source_observation_ids=["private-author-memory"])
    value.update(changes)
    return value


def recording(**changes):
    value = scoped(id="audio-market", composition_id="song-market", performer_id="bard-a",
                   request=request(), playable=True, created_at=30)
    value.update(changes)
    return value


def observation(**changes):
    value = scoped(id="heard-scandal", performer_id="bard-a", event_id="scandal-event",
                   topic_id="scandal-claim", kind="scandal", summary="The reeve allegedly sold the same horse twice.",
                   happened_at=90, learned_at=95, source_id="tavern-rumor", evidence="rumor",
                   interest=.95, local_relevance=.95)
    value.update(changes)
    return value


def pending(**changes):
    value = scoped(id="job-one", performer_id="bard-a", action="compose_lyrics", request=request(),
                   topic_id="scandal-claim", composition_id=None, created_at=99, status="queued")
    value.update(changes)
    return value


def receipt(**changes):
    value = scoped(id="job-old", performer_id="bard-a", action="compose_lyrics", at=95)
    value.update(changes)
    return value


def performance(**changes):
    value = scoped(id="performance-one", performer_id="bard-a", composition_id="song-market", at=99)
    value.update(changes)
    return value


def snapshot(**changes):
    value = dict(save_id="save-a", world_id="world-a", performer_id="bard-a", now_hours=100,
                 request=request(), observations=[], compositions=[], recordings=[], recent_performances=[],
                 pending_jobs=[], generation_history=[], policy={})
    value.update(changes)
    return value


class RepertoireTests(unittest.TestCase):
    def test_cache_first_avoids_new_lyrics_despite_salient_news(self):
        result = plan(snapshot(compositions=[composition()], recordings=[recording()], observations=[observation()]))
        self.assertEqual(result["action"], "play_recording")
        self.assertEqual(result["recording_id"], "audio-market")
        self.assertIsNone(result["lyric_brief"])
        self.assertIsNone(result["work_key"])

    def test_topical_policy_can_compose_with_playable_fallback(self):
        result = plan(snapshot(compositions=[composition()], recordings=[recording()], observations=[observation()],
                               policy={"selection": "topical_when_salient"}))
        self.assertEqual(result["action"], "compose_lyrics")
        self.assertEqual(result["fallback"]["recording_id"], "audio-market")
        self.assertEqual(result["subject"]["evidence"], "rumor")
        self.assertEqual(result["lyric_brief"]["source_observation_ids"], ["heard-scandal"])
        self.assertIn("Wit", result["lyric_brief"]["creative_license"])

    def test_topical_composition_recording_playback_pipeline_and_cooldown(self):
        source = snapshot(compositions=[composition()], recordings=[recording()], observations=[observation()],
                          policy={"selection": "topical_when_salient"})
        self.assertEqual(plan(source)["action"], "compose_lyrics")
        source["compositions"].append(composition(id="song-scandal", topic_id="scandal-claim", created_at=100,
            title="One Horse, Two Purses", composer_id="bard-a", lyrics="They say the reeve filled two purses.",
            source_observation_ids=["heard-scandal"]))
        source["generation_history"].append(receipt(at=100))
        next_step = plan(source)
        self.assertEqual(next_step["action"], "generate_recording")
        self.assertEqual(next_step["composition_id"], "song-scandal")
        self.assertEqual(next_step["fallback"]["recording_id"], "audio-market")
        self.assertTrue(next_step["recording_brief"]["reuse_existing_lyrics"])
        source["recordings"].append(recording(id="audio-scandal", composition_id="song-scandal", created_at=100))
        self.assertEqual(plan(source)["recording_id"], "audio-scandal")
        source["recent_performances"].append(performance(composition_id="song-scandal", at=100,
                                                        topic_id="scandal-claim"))
        final = plan(source)
        self.assertEqual(final["action"], "play_recording")
        self.assertEqual(final["recording_id"], "audio-market")

    def test_known_lyrics_reused_without_author_private_knowledge(self):
        result = plan(snapshot(compositions=[composition()], request=request(arrangement="drum_voice")))
        self.assertEqual(result["action"], "generate_recording")
        self.assertEqual(result["composition_id"], "song-market")
        self.assertTrue(result["recording_brief"]["reuse_existing_lyrics"])
        self.assertIsNone(result["lyric_brief"])
        self.assertNotIn("private-author-memory", json.dumps(result))

    def test_instrumental_and_wordless_never_compose_lyrics(self):
        for mode, voice in [("instrumental", "none"), ("wordless", "bard-voice-v1")]:
            with self.subTest(mode=mode):
                result = plan(snapshot(request=request(mode=mode, voice=voice), observations=[observation()]))
                self.assertEqual(result["action"], "generate_recording")
                self.assertIsNone(result["lyric_brief"])
                self.assertTrue(result["recording_brief"]["omit_lyrics"])
                self.assertTrue(result["recording_brief"]["create_composition_on_success"])

    def test_instrumental_rendition_preserves_composition_identity(self):
        result = plan(snapshot(request=request(mode="instrumental", voice="none", arrangement="lute"),
                               compositions=[composition()]))
        self.assertEqual(result["composition_id"], "song-market")
        self.assertFalse(result["recording_brief"]["reuse_existing_lyrics"])
        self.assertTrue(result["recording_brief"]["omit_lyrics"])
        self.assertNotIn("A cart", json.dumps(result))

    def test_existing_instrumental_rendition_of_lyrical_song_can_play(self):
        req = request(mode="instrumental", voice="none", arrangement="lute")
        result = plan(snapshot(request=req, compositions=[composition()], recordings=[recording(request=req)]))
        self.assertEqual(result["action"], "play_recording")

    def test_world_cache_does_not_teach_actor_a_song(self):
        result = plan(snapshot(compositions=[composition(known_by=["another-bard"])], recordings=[recording()]))
        self.assertEqual(result["action"], "no_selection")

    def test_hearing_gossip_does_not_teach_somebody_elses_lyrics(self):
        result = plan(snapshot(compositions=[composition(known_by=["another-bard"], topic_id="scandal-claim")],
                               recordings=[recording()], observations=[observation()]))
        self.assertEqual(result["action"], "compose_lyrics")
        self.assertIsNone(result["composition_id"])
        self.assertIsNone(result["recording_id"])

    def test_actor_and_save_scope_apply_before_evidence_selection(self):
        foreign = observation(id="secret-witness", performer_id="another-bard", evidence="direct", summary="SECRET")
        foreign_save = observation(id="secret-save", save_id="other-save", evidence="direct", summary="SAVE SECRET")
        foreign_world = observation(id="secret-world", world_id="other-world", evidence="direct", summary="WORLD SECRET")
        result = plan(snapshot(observations=[observation(), foreign, foreign_save, foreign_world]))
        self.assertEqual(result["subject"]["evidence"], "rumor")
        self.assertNotIn("SECRET", json.dumps(result))

    def test_cross_save_composition_and_recording_never_play(self):
        result = plan(snapshot(compositions=[composition(save_id="other-save")],
                               recordings=[recording(save_id="other-save")]))
        self.assertEqual(result["action"], "no_selection")

    def test_another_performers_recording_is_not_this_performers_cache(self):
        result = plan(snapshot(compositions=[composition()], recordings=[recording(performer_id="other-bard")]))
        self.assertEqual(result["action"], "generate_recording")

    def test_all_recording_identity_fields_must_match(self):
        for field, value in [("arrangement", "flute_voice"), ("voice", "voice-two"), ("recipe_id", "recipe-two"),
                             ("model_id", "model-two"), ("tradition", "different-tradition"), ("mode", "wordless")]:
            with self.subTest(field=field):
                incompatible = request(**{field: value})
                result = plan(snapshot(compositions=[composition()], recordings=[recording(request=incompatible)]))
                self.assertEqual(result["action"], "generate_recording")

    def test_unplayable_or_future_recordings_are_not_cache_hits(self):
        for changes in [{"playable": False}, {"created_at": 101}, {"created_at": 19}]:
            with self.subTest(changes=changes):
                self.assertEqual(plan(snapshot(compositions=[composition()], recordings=[recording(**changes)]))["action"],
                                 "generate_recording")

    def test_future_knowledge_and_compositions_do_not_leak_after_reload(self):
        result = plan(snapshot(observations=[observation(happened_at=101, learned_at=102)],
                               compositions=[composition(created_at=101)], recordings=[recording(created_at=102)]))
        self.assertEqual(result["action"], "no_selection")
        self.assertIn("Future-dated", " ".join(result["reasons"]))

    def test_unknown_dates_never_become_fresh(self):
        for key in ("happened_at", "learned_at"):
            with self.subTest(key=key):
                result = plan(snapshot(observations=[observation(**{key: None})]))
                self.assertEqual(result["action"], "no_selection")
                self.assertIn("Unknown", " ".join(result["reasons"]))

    def test_retelling_same_claim_with_new_event_id_does_not_refresh_it(self):
        old = observation(id="old", happened_at=1, learned_at=2)
        recent_copy = observation(id="copy", event_id="another-report-id", happened_at=98, learned_at=99)
        result = plan(snapshot(observations=[old, recent_copy]))
        self.assertEqual(result["action"], "no_selection")

    def test_repeated_rumor_neither_confirms_nor_increases_salience(self):
        source = observation(interest=.5, local_relevance=.5)
        copies = [observation(id=f"copy-{n}", learned_at=96+n/10, interest=1, local_relevance=1) for n in range(10)]
        self.assertEqual(plan(snapshot(observations=[source, *copies]))["action"], "no_selection")
        result = plan(snapshot(observations=[observation(), *copies]))
        self.assertEqual(result["subject"]["evidence"], "rumor")
        self.assertAlmostEqual(result["subject"]["salience"], .95)

    def test_direct_evidence_can_change_framing_without_refreshing_age(self):
        result = plan(snapshot(observations=[observation(), observation(id="saw-it", evidence="direct",
                    happened_at=90, learned_at=99, summary="The bard witnessed the two payments.")]))
        self.assertEqual(result["subject"]["evidence"], "direct")
        self.assertEqual(result["subject"]["learned_at"], 95)
        self.assertEqual(result["subject"]["source_observation_ids"], ["saw-it"])

    def test_no_heroism_is_inferred_from_summary_or_kind(self):
        for kind in ("quest_success", "scandal", "gossip", "everyday_news", "other"):
            with self.subTest(kind=kind):
                result = plan(snapshot(observations=[observation(kind=kind, summary="The bridge reopened.")]))
                self.assertEqual(result["action"], "compose_lyrics")
                self.assertEqual(result["subject"]["kind"], kind)
                self.assertEqual(result["lyric_brief"]["summary"], "The bridge reopened.")

    def test_song_and_topic_repetition_are_separate(self):
        source = snapshot(compositions=[composition()], recordings=[recording()], recent_performances=[performance()])
        self.assertEqual(plan(source)["action"], "no_selection")
        source["compositions"] = [composition(topic_id="shared-topic"), composition(id="song-two", topic_id="shared-topic")]
        source["recordings"] = [recording(composition_id="song-two")]
        self.assertEqual(plan(source)["action"], "no_selection")

    def test_recent_performance_optional_ids_and_other_scope_do_not_block(self):
        source = snapshot(compositions=[composition()], recordings=[recording()],
                          recent_performances=[performance(performer_id="another-bard")])
        self.assertEqual(plan(source)["action"], "play_recording")
        source["recent_performances"] = [performance(save_id="another-save")]
        self.assertEqual(plan(source)["action"], "play_recording")
        source["recent_performances"] = [performance(at=101)]
        self.assertEqual(plan(source)["action"], "play_recording")

    def test_cache_choice_rotates_by_composition_last_performance(self):
        source = snapshot(compositions=[composition(), composition(id="song-two")],
            recordings=[recording(), recording(id="audio-two", composition_id="song-two")],
            recent_performances=[performance(at=80)])
        self.assertEqual(plan(source)["recording_id"], "audio-two")

    def test_duplicate_pending_lyrics_is_not_submitted(self):
        result = plan(snapshot(observations=[observation()], pending_jobs=[pending()]))
        self.assertEqual(result["action"], "wait")
        self.assertEqual(result["pending_job_id"], "job-one")
        self.assertIsNone(result["work_key"])

    def test_duplicate_pending_recording_is_not_submitted(self):
        result = plan(snapshot(compositions=[composition()], pending_jobs=[pending(action="generate_recording",
                    composition_id="song-market", topic_id=None)]))
        self.assertEqual(result["action"], "wait")
        self.assertEqual(result["pending_job_id"], "job-one")

    def test_inactive_foreign_and_future_jobs_do_not_block(self):
        for changes in ({"status": "failed"}, {"status": "cancelled"}, {"status": "completed"},
                        {"save_id": "other-save"}, {"world_id": "other-world"},
                        {"performer_id": "another-bard"}, {"created_at": 101}):
            with self.subTest(changes=changes):
                result = plan(snapshot(observations=[observation()], pending_jobs=[pending(**changes)]))
                self.assertEqual(result["action"], "compose_lyrics")

    def test_pending_job_and_its_start_receipt_count_once(self):
        source = snapshot(observations=[observation()], pending_jobs=[pending(topic_id="different-claim")],
            generation_history=[receipt(id="job-one", at=99)],
            policy={"composition_cooldown_hours": 0, "max_pending_jobs": 2, "max_lyric_jobs": 2})
        self.assertEqual(plan(source)["action"], "compose_lyrics")

    def test_cooldown_and_budget_are_independent_generation_guards(self):
        source = snapshot(observations=[observation()], generation_history=[receipt()])
        result = plan(source)
        self.assertEqual(result["action"], "wait")
        self.assertEqual(result["retry_at"], 119)
        source["policy"] = {"composition_cooldown_hours": 0, "max_lyric_jobs": 1}
        self.assertIn("budget", " ".join(plan(source)["reasons"]))

    def test_cooldown_is_actor_and_save_scoped(self):
        source = snapshot(observations=[observation()], generation_history=[receipt(performer_id="other-bard"),
            receipt(id="other-save-receipt", save_id="other-save"), receipt(id="future", at=101)])
        self.assertEqual(plan(source)["action"], "compose_lyrics")

    def test_topical_budget_block_plays_available_cache(self):
        result = plan(snapshot(observations=[observation()], compositions=[composition()], recordings=[recording()],
            policy={"selection": "topical_when_salient", "max_lyric_jobs": 0}))
        self.assertEqual(result["action"], "play_recording")
        self.assertIn("budget", " ".join(result["reasons"]))

    def test_pending_topical_work_keeps_playable_fallback(self):
        result = plan(snapshot(observations=[observation()], compositions=[composition()], recordings=[recording()],
            pending_jobs=[pending()], policy={"selection": "topical_when_salient"}))
        self.assertEqual(result["action"], "wait")
        self.assertEqual(result["fallback"]["recording_id"], "audio-market")

    def test_work_key_stays_stable_across_time_and_receipt_copies(self):
        source = snapshot(observations=[observation()])
        first = plan(source)
        source["now_hours"] = 101
        source["observations"].append(observation(id="aaa-retrieval-copy", event_id="copy-event"))
        second = plan(source)
        self.assertEqual(first["work_key"], second["work_key"])
        source["request"]["recipe_id"] = "revised-recipe"
        self.assertNotEqual(first["work_key"], plan(source)["work_key"])

    def test_plan_is_pure_serializable_and_accepts_dataclass_snapshot(self):
        source = snapshot(observations=[observation()])
        before = deepcopy(source)
        first = plan(source)
        self.assertEqual(source, before)
        self.assertEqual(first, plan(Snapshot.from_dict(source)))
        self.assertEqual(first, json.loads(json.dumps(first)))
        self.assertEqual(first, plan(source))
        self.assertEqual(source["pending_jobs"], [])

    def test_validation_rejects_bad_clock_and_implicit_classification(self):
        for changes in ({"now_hours": float("nan")}, {"now_hours": True}, {"now_hours": -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Snapshot.from_dict(snapshot(**changes))
        with self.assertRaises(ValueError):
            plan(snapshot(observations=[observation(kind="sounds like a heroic success")]))
        with self.assertRaises(ValueError):
            plan(snapshot(observations=[observation(happened_at=99, learned_at=95)]))


if __name__ == "__main__":
    unittest.main()
