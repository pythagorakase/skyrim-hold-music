"""Recipe evidence must stop being current when the audible request changes."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from tools import workshop_library as library


class RecipeProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "id": "falkreath", "name": "Falkreath", "reference": "Karelian runo-song",
            "core": "Short descending cells in five beats",
            "workshop": {"plucked": "lute", "flute": "flute", "drum": "hand drum",
                         "family_rules": {"plucked": "No bowed strings.",
                                          "flute": "No reed-driven sound."}},
            "audition": {"stage": "baseline", "revision": "baseline-11-v2",
                         "arrangement": "lute_voice", "vocal_mode": "lyrics"},
        }
        self.palette = {"auditionRaces": {"nord": "Nord"},
                        "auditionRegions": {"falkreath": "Falkreath Hold, Skyrim"},
                        "auditionVoices": {}}
        self.take = {"id": "a" * 32, "profile_id": self.profile["id"],
                     "recipe_revision": self.profile["audition"]["revision"],
                     "recipe_fingerprint": library.recipe_fingerprint(self.profile, self.palette)}

    def status(self, profile=None):
        profile = self.profile if profile is None else profile
        return library.prompt_status(self.take, {profile["id"]: profile}, self.palette, {})["state"]

    def test_named_instrument_and_family_exclusions_invalidate_same_revision_take(self):
        self.assertEqual(self.status(), "current")
        changes = (
            lambda p: p["workshop"].update(plucked="plucked kantele"),
            lambda p: p["workshop"]["family_rules"].update(plucked="No bowed strings or keyboard."),
            lambda p: p["workshop"]["family_rules"].update(flute="No reed-driven sound or brass."),
            lambda p: p["workshop"].pop("family_rules"),
        )
        for change in changes:
            with self.subTest(change=change):
                changed = deepcopy(self.profile)
                change(changed)
                self.assertEqual(changed["audition"]["revision"], self.take["recipe_revision"])
                self.assertEqual(self.status(changed), "obsolete")

    def test_revision_and_monophonic_reference_changes_invalidate_saved_take(self):
        for field, value in (("revision", "baseline-11-v3"),
                             ("reference_focus_monophonic", "A single-line contour reduction")):
            with self.subTest(field=field):
                changed = deepcopy(self.profile)
                if field == "revision":
                    changed["audition"][field] = value
                else:
                    changed[field] = value
                self.assertEqual(self.status(changed), "obsolete")

    def test_saved_fingerprint_does_not_inherit_new_assembly_contract(self):
        with patch.object(library, "PROMPT_CONTRACT", "workshop-prompt-v1"):
            self.take["recipe_fingerprint"] = library.recipe_fingerprint(self.profile, self.palette)
            self.assertEqual(self.status(), "current")
        self.assertEqual(self.status(), "obsolete")

    def test_reordering_rules_does_not_discard_matching_evidence(self):
        changed = deepcopy(self.profile)
        changed["workshop"]["family_rules"] = dict(reversed(list(changed["workshop"]["family_rules"].items())))
        self.assertEqual(self.status(changed), "current")
