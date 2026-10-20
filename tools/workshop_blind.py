"""Private, durable blind recognition sessions. Reads never generate music."""

from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import threading

try:
    from .workshop_library import digest, recipe_fingerprint, read_json
except ImportError:
    from workshop_library import digest, recipe_fingerprint, read_json


MODEL = "lyria-3-clip-preview"
FORMATS = {"clip": MODEL, "full": "lyria-3.5"}
CONTRACT = "blind-recognition-v1"
PRESENTATION = "three-choice-v1"
LEGACY_PRESENTATION = "full-palette-v1"
SESSION_LIMIT = 64 * 1024 * 1024
ID = re.compile(r"[a-f0-9]{32}")
MODES = {"canonical": "Style instruments", "plucked": "Shared plucked strings", "flute": "Shared reedless woodwinds"}
NEUTRAL_LYRICS = "The light falls low, the day is done.\nA quiet step, another one.\nThe open door, the warming glow.\nWe rest a while, then onward go."
DESCRIPTIONS = {
    "haafingar": "Triple-time Renaissance galliard, balanced phrases, spacious chords and shaped cadences.",
    "eastmarch": "Restrained rímur declamation: narrow range, articulated verse and clear pauses.",
    "whiterun": "Modal narrative ballad, substantial verses and a short returning refrain.",
    "reach": "Duple reel mouth music, compact strains and tightly articulated syllables.",
    "falkreath": "Repeated five-beat runo-song cells, narrow melody and sparse plucked support.",
    "rift": "Bouncing compound-time jig, bright chord strokes and repeated dance strains.",
    "winterhold": "Wordless joik adaptation, recurring vocal shapes and restrained plucked accompaniment.",
    "pale": "Broad rowing-song phrases over a measured pulse, with spacious endings.",
    "hjaalmarch": "Repeated sutartinės figures, neighboring-note tension and unresolved interlocking phrases.",
    "dunmer": "Persian-inspired modal lament, ornamented melody and flexible expressive phrasing.",
    "imperial": "Italian monody, one expressive solo voice over measured chordal support.",
    "reach_sean_nos": "Ornamented free air, flexible pacing and intimate melodic detail.",
}


def description(identifier, fallback):
    return DESCRIPTIONS.get(identifier, " ".join(fallback.split()[:12]))


def now():
    return datetime.now(timezone.utc).isoformat()


class StorageBusy(RuntimeError):
    pass


@contextmanager
def storage_lock(root):
    """The server CLI and seeder CLI must never write the same store concurrently."""
    directory = Path(root) / "auditions" / ".blind"
    for path in (directory.parent, directory):
        if path.is_symlink():
            raise StorageBusy("Workshop storage is not a regular local directory.")
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = directory / "process.lock"
    if path.is_symlink():
        raise StorageBusy("Workshop lock is not a regular local file.")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            try:
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            except OSError:
                raise StorageBusy("The workshop or clip seeder is already using this folder. Stop it before starting another writer.") from None
        else:
            import fcntl
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise StorageBusy("The workshop or clip seeder is already using this folder. Stop it before starting another writer.") from None
        yield
    finally:
        os.close(descriptor)


def clean(value):
    return str(value or "").strip().rstrip(".")


def arrangement_for(profile, mode):
    return profile.get("audition", {}).get("arrangement", "lute_voice") if mode == "canonical" else "lute" if mode == "plucked" else "flute"


def prompt_for(profile, mode, format="clip"):
    """Use frozen canonical recipe fragments, never browser drafts or target lyrics."""
    arrangement = arrangement_for(profile, mode)
    sings = arrangement.endswith("_voice") or arrangement == "voice"
    wordless = sings and profile.get("audition", {}).get("vocal_mode") == "wordless"
    family = "flute" if arrangement.startswith("flute") else "plucked"
    instrument = profile.get("workshop", {}).get(family, "flute" if family == "flute" else "lute")
    core = profile.get("core", "")
    if not sings:
        core = profile.get("core_instrumental", core)
    if family == "flute":
        core = profile.get("core_monophonic", core) if sings else profile.get("core_instrumental_monophonic", profile.get("core_monophonic", core))
    clause = profile.get("flute" if family == "flute" else "lute", "")
    if not sings:
        clause = profile.get("flute_instrumental" if family == "flute" else "lute_instrumental", clause)
    rule = profile.get("workshop", {}).get("family_rules", {}).get(family)
    rule = rule or ("No reed-driven sound." if family == "flute" else "No bowed strings.")
    parts = ["Create a thirty-second acoustic music clip." if format == "clip" else "Create a complete acoustic song with a clear beginning, developed musical phrases and a natural ending.",
             "Style: " + clean(profile.get("reference", profile["name"])) + ".",
             ("One adult singer playing " + instrument + " while singing." if sings else "One performer playing " + instrument + "."),
             "Intimate live acoustic room; only these sound sources. No additional instruments.", rule,
             clean(core) + ".", instrument[0].upper() + instrument[1:] + ": " + clean(clause) + "."]
    if sings:
        parts.append("Voice: " + clean(profile.get("voice", "one natural adult voice")) + ".")
    lyrics = ""
    if wordless:
        parts.append("Wordless vocables only; no lyrics, sentences or spoken words.")
    elif sings:
        lyrics = NEUTRAL_LYRICS
        parts.extend(["Sing only these supplied English words in order; do not add words, names of places, regions, cultures, traditions or instruments.", "Lyrics:\n" + lyrics])
    else:
        parts.append("Instrumental only. No singing, spoken words or vocalizations.")
    cue = core if mode != "canonical" else profile.get("dialect") or core or profile.get("reference_focus") or profile.get("reference")
    if family == "flute" and profile.get("reference_focus_monophonic"):
        cue = clean(cue) + ". " + clean(profile["reference_focus_monophonic"])
    return {"prompt": "\n".join(parts), "arrangement": arrangement, "instrument_name": instrument, "supplied_lyrics": lyrics,
            "cue": clean(cue) + "."}


class BlindSessions:
    def __init__(self, workshop, *, error, writer, parse_audio, audio_formats):
        self.workshop, self.Error, self.write = workshop, error, writer
        self.parse_audio, self.audio_formats = parse_audio, audio_formats
        self.base = workshop.data_dir / ".blind"
        self.sessions = {}
        self.pool = {}
        self.pool_error = False
        exposure_path = self.base / "exposures.json"
        self.exposures = read_json(exposure_path)
        self.exposure_error = ((exposure_path.exists() or exposure_path.is_symlink()) and
                               (not isinstance(self.exposures, dict) or any(
                                   not isinstance(k, str) or not re.fullmatch(r"[a-f0-9]{64}", k) or
                                   not isinstance(v, dict) or not isinstance(v.get("trial_id"), str) or not ID.fullmatch(v["trial_id"])
                                   for k, v in (self.exposures or {}).items())))
        if not isinstance(self.exposures, dict):
            self.exposures = {}
        for path in sorted((self.base / "sessions").glob("*.json")):
            value = read_json(path, limit=SESSION_LIMIT)
            if not self._valid_session(value, path.stem):
                continue
            self.sessions[value["id"]] = value
            changed = False
            for trial in value["trials"]:
                if trial["status"] in ("queued", "generating"):
                    trial.update(status="failed", error="Generation was interrupted. Its charge or result is unknown. No automatic retry was made.")
                    changed = True
            if changed:
                self._save(value)
        for path in sorted((self.base / "pool").glob("*.json")):
            value = read_json(path)
            if not self._valid_pool(value, path.stem):
                self.pool_error = True
                continue
            if value["status"] in ("queued", "generating"):
                value.update(status="interrupted", error="The saved generation was interrupted. Its charge or result is unknown. No automatic retry was made.")
                self._save_pool(value)
            self.pool[value["id"]] = value
        # The session receipt is committed first. Recover its claim even if the
        # process stopped before the separate pool receipt could be updated.
        for session in self.sessions.values():
            for trial in session["trials"]:
                if trial.get("practice"):
                    continue
                source = self.pool.get(trial.get("source_id"))
                if source and source.get("claimed_by") != trial["id"]:
                    if source.get("claimed_by"):
                        self.pool_error = True
                        continue
                    source["claimed_by"] = trial["id"]
                    self._save_pool(source)

    @staticmethod
    def _valid_pool(value, identifier):
        if not isinstance(value, dict) or not ID.fullmatch(identifier) or value.get("id") != identifier or value.get("version") != 1:
            return False
        if value.get("status") not in ("queued", "generating", "ready", "failed", "interrupted", "duplicate"):
            return False
        if not all(isinstance(value.get(key), str) for key in ("target", "group_id", "mode", "model", "revision", "created_at")) or not isinstance(value.get("recipe"), dict):
            return False
        if value.get("claimed_by") is not None and (not isinstance(value["claimed_by"], str) or not ID.fullmatch(value["claimed_by"])):
            return False
        if value["status"] == "ready" and (value.get("mime_type") not in ("audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav") or not isinstance(value.get("audio_sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", value["audio_sha256"]) or not isinstance(value.get("lyrics"), str) or not isinstance(value.get("ready_at"), str)):
            return False
        return True

    @staticmethod
    def _valid_session(value, identifier):
        if not isinstance(value, dict) or not ID.fullmatch(identifier) or value.get("id") != identifier or value.get("version") != 1:
            return False
        if not isinstance(value.get("mode"), str) or value["mode"] not in MODES or (value.get("size") is not None and (type(value["size"]) is not int or not 1 <= value["size"] <= 30)):
            return False
        if not all(isinstance(value.get(key), str) for key in ("model", "revision", "group_id", "created_at")):
            return False
        if not all(isinstance(value.get(key), list) for key in ("choices", "plan", "trials")) or not isinstance(value.get("recipes"), dict) or not isinstance(value.get("requests"), dict):
            return False
        if not value["recipes"] or not all(isinstance(k, str) and isinstance(r, dict) and all(
                isinstance(r.get(field), str) for field in ("prompt", "arrangement", "supplied_lyrics", "name", "cue", "recipe_revision"))
                for k, r in value["recipes"].items()):
            return False
        if (value["size"] is not None and len(value["plan"]) != value["size"]) or not all(isinstance(p, str) and p in value["recipes"] for p in value["plan"]):
            return False
        if not all(isinstance(c, dict) and isinstance(c.get("id"), str) and isinstance(c.get("name"), str) and c["id"] in value["recipes"] for c in value["choices"]):
            return False
        if len({c["id"] for c in value["choices"]}) != len(value["choices"]):
            return False
        seen = set()
        session_choices = {c["id"] for c in value["choices"]}
        for trial in value["trials"]:
            if not isinstance(trial, dict) or not isinstance(trial.get("id"), str) or not ID.fullmatch(trial["id"]) or trial["id"] in seen:
                return False
            seen.add(trial["id"])
            if trial.get("status") not in ("queued", "generating", "ready", "answered", "failed") or not isinstance(trial.get("target"), str) or trial["target"] not in value["recipes"]:
                return False
            if "choice_ids" in trial or "presentation_contract" in trial:
                offered = trial.get("choice_ids")
                contract = trial.get("presentation_contract")
                if (not isinstance(offered, list) or not offered or not all(isinstance(c, str) and c in session_choices for c in offered)
                        or len(set(offered)) != len(offered) or trial["target"] not in offered
                        or contract not in (PRESENTATION, LEGACY_PRESENTATION)
                        or (contract == PRESENTATION and len(offered) != 3)
                        or (contract == LEGACY_PRESENTATION and set(offered) != session_choices)):
                    return False
                if trial["status"] == "answered" and trial.get("guess") not in {*offered, "unsure"}:
                    return False
            if trial["status"] == "failed" and not isinstance(trial.get("error"), str):
                return False
            if trial["status"] in ("ready", "answered") and (trial.get("mime_type") not in ("audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav") or not isinstance(trial.get("audio_sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", trial["audio_sha256"]) or not isinstance(trial.get("lyrics"), str)):
                return False
            if trial["status"] == "answered" and (not isinstance(trial.get("guess"), str) or trial["guess"] not in {*value["recipes"], "unsure"} or type(trial.get("correct")) is not bool or type(trial.get("scored")) is not bool or trial.get("reaction") not in ("keep", "rework", None)):
                return False
        return all(isinstance(k, str) and ID.fullmatch(k) and isinstance(v, str) and v in seen for k, v in value["requests"].items())

    def _ensure_storage(self):
        for path in (self.workshop.data_dir, self.base, self.base / "sessions", self.base / "audio", self.base / "pool", self.base / "seed-reports"):
            if path.is_symlink():
                raise self.Error("Blind session storage is not a regular local directory.", 409)
            path.mkdir(mode=0o700, parents=True, exist_ok=True)

    def _save(self, session):
        self._ensure_storage()
        content = json.dumps(session, ensure_ascii=False, indent=2).encode()
        if len(content) > SESSION_LIMIT:
            raise self.Error("This session reached its local history storage limit. Its saved history was preserved; start a new session before continuing.", 409)
        self.write(self.base / "sessions" / (session["id"] + ".json"), content)

    def _save_exposures(self, exposures):
        self._ensure_storage()
        self.write(self.base / "exposures.json", json.dumps(exposures, ensure_ascii=False, indent=2).encode())
        self.exposures = exposures

    def _save_pool(self, record):
        self._ensure_storage()
        self.write(self.base / "pool" / (record["id"] + ".json"), json.dumps(record, ensure_ascii=False, indent=2).encode())

    def _cohort(self, mode, challenger=False, format="clip"):
        profiles = self._eligible(mode, challenger)
        if len(profiles) < 3:
            raise self.Error("This mode needs at least three supported active styles to offer two distractors.", 409)
        choices = [{"id": p["id"], "name": p["name"]} for p in profiles]
        recipes = {p["id"]: {**prompt_for(p, mode, format), "name": p["name"], "recipe_fingerprint": recipe_fingerprint(p, self.workshop.palette), "recipe_revision": p.get("audition", {}).get("revision", "unversioned")} for p in profiles}
        model = FORMATS[format]
        # Deliberately retain the original clip digest contract: existing saved
        # clips remain usable when open-ended judging or tooltips are added.
        group = digest({"contract": CONTRACT, "mode": mode, "model": model, "choices": choices, "recipes": recipes})
        return {"mode": mode, "model": model, "format": format, "revision": self.workshop.palette.get("baseline", {}).get("revision", "unversioned"),
                "choices": choices, "recipes": recipes, "group_id": group, "include_challenger": challenger}

    def _available_pool(self, cohort):
        if self.exposure_error or self.pool_error:
            return []
        reserved_hashes = {t.get("audio_sha256") for s in self.sessions.values() for t in s["trials"] if t.get("audio_sha256")}
        seen = set(self.exposures) | reserved_hashes
        result = []
        for record in sorted(self.pool.values(), key=lambda r: r["created_at"]):
            if record["status"] != "ready" or record.get("claimed_by") or record["group_id"] != cohort["group_id"]:
                continue
            target = record["target"]
            if record["model"] != cohort["model"] or record["mode"] != cohort["mode"] or record["recipe"] != cohort["recipes"].get(target):
                continue
            audio_hash = record["audio_sha256"]
            if audio_hash in seen:
                continue
            path = self.base / "audio" / (record["id"] + self.audio_formats[record["mime_type"]])
            if not path.is_file() or path.is_symlink():
                continue
            seen.add(audio_hash)
            result.append(record)
        return result

    def pool_summary(self):
        formats = {}
        for format in FORMATS:
            summaries = {}
            for mode in MODES:
                try:
                    cohort = self._cohort(mode, format=format)
                except self.Error:
                    continue
                summaries[mode] = {"ready": len(self._available_pool(cohort)),
                                   "total": sum(r["group_id"] == cohort["group_id"] and r["status"] == "ready" for r in self.pool.values())}
            formats[format] = {"ready": sum(s["ready"] for s in summaries.values()), "total": sum(s["total"] for s in summaries.values()), "by_mode": summaries}
        return {"ready": sum(f["ready"] for f in formats.values()), "total": sum(r["status"] == "ready" for r in self.pool.values()),
                "by_mode": formats["clip"]["by_mode"], "by_format": formats}

    def _eligible(self, mode, challenger=False):
        self.workshop.refresh_palette()
        palette = self.workshop.palette
        ids = list(palette.get("baseline", {}).get("profiles", []))
        if challenger:
            ids += list(palette.get("baseline", {}).get("comparisons", []))
        result = []
        for identifier in dict.fromkeys(ids):
            profile = self.workshop.profiles.get(identifier)
            if not profile or profile.get("audition", {}).get("stage") not in ("baseline", "comparison"):
                continue
            arrangement = arrangement_for(profile, mode)
            if arrangement not in profile.get("workshop", {}).get("allowed", []):
                continue
            if mode == "flute" and not (profile.get("flute_instrumental") or profile.get("flute")):
                continue
            if mode == "plucked" and not (profile.get("lute_instrumental") or profile.get("lute")):
                continue
            result.append(profile)
        return result

    def catalog(self):
        with self.workshop.lock:
            profiles = self._eligible("canonical", True)
            sessions = sorted(self.sessions.values(), key=lambda s: s["created_at"], reverse=True)
            return {"choices": [{"id": p["id"], "name": p["name"], "description": description(p["id"], prompt_for(p, "canonical")["cue"])} for p in profiles],
                    "modes": [{"id": mode, "label": label, "choice_ids": [p["id"] for p in self._eligible(mode, True)]} for mode, label in MODES.items()],
                    "formats": [{"id": f, "label": "30-second clip" if f == "clip" else "Full song", "model": model} for f, model in FORMATS.items()],
                    "active_session": self.public(sessions[0]) if sessions else None,
                    "sessions": [{key: self.public(s)[key] for key in ("id", "mode", "format", "include_challenger", "size", "completed", "finished", "created_at", "revision")} for s in sessions],
                    "pool": self.pool_summary()}

    def create(self, payload):
        if not isinstance(payload, dict):
            raise self.Error("Send the session settings as an object.")
        mode, size, challenger = payload.get("mode", "canonical"), payload.get("size"), payload.get("include_challenger", False)
        format = payload.get("format", "clip")
        if not isinstance(mode, str) or mode not in MODES or (size is not None and (type(size) is not int or not 1 <= size <= 30)) or type(challenger) is not bool or not isinstance(format, str) or format not in FORMATS:
            raise self.Error("Choose a supported mode and format; use an open-ended session or 1–30 recordings.")
        with self.workshop.lock:
            cohort = self._cohort(mode, challenger, format)
            choices, group = cohort["choices"], cohort["group_id"]
            counts = Counter(p for s in self.sessions.values() if s["group_id"] == group for p in s["plan"])
            plan = []
            for _ in range(size or 0):
                least = min(counts[c["id"]] for c in choices)
                target = secrets.choice([c["id"] for c in choices if counts[c["id"]] == least])
                plan.append(target)
                counts[target] += 1
            session = {**cohort, "version": 1, "id": secrets.token_hex(16), "size": size,
                       "created_at": now(), "plan": plan, "trials": [], "requests": {}}
            self._save(session)
            self.sessions[session["id"]] = session
            return self.public(session)

    def _session(self, identifier):
        session = self.sessions.get(identifier)
        if not session:
            raise self.Error("Blind session not found.", 404)
        return session

    def _trial(self, identifier):
        for session in self.sessions.values():
            for trial in session["trials"]:
                if trial["id"] == identifier:
                    return session, trial
        raise self.Error("Blind clip not found.", 404)

    def _offer_choices(self, session, trial):
        """Presentation is separate from the frozen generation/pool cohort."""
        others = [c["id"] for c in session["choices"] if c["id"] != trial["target"]]
        if len(others) < 2:
            raise self.Error("This session needs at least three supported styles to offer two distractors. Start another supported session.", 409)
        random = secrets.SystemRandom()
        offered = [trial["target"], *random.sample(others, 2)]
        random.shuffle(offered)
        trial.update(choice_ids=offered, presentation_contract=PRESENTATION)

    def _prepare_choices(self, session):
        # Old answered trials retain the full palette they actually saw. Only
        # unanswered legacy trials are migrated, with a durable write before
        # their first reduced-choice response (including after a restart).
        session = self.sessions.get(session["id"], session)
        missing = [t for t in session["trials"] if t["status"] != "answered" and "choice_ids" not in t]
        if not missing:
            return session
        updated = deepcopy(session)
        for trial in updated["trials"]:
            if trial["status"] != "answered" and "choice_ids" not in trial:
                self._offer_choices(updated, trial)
        self._save(updated)
        self.sessions[session["id"]] = updated
        return updated

    def public(self, session):
        session = self._prepare_choices(session)
        choices = {c["id"]: {**c, "description": description(c["id"], session["recipes"][c["id"]]["cue"])} for c in session["choices"]}
        trials = []
        for trial in session["trials"]:
            item = {"id": trial["id"], "status": trial["status"],
                    "presentation_contract": trial.get("presentation_contract", LEGACY_PRESENTATION),
                    "choices": [deepcopy(choices[identifier]) for identifier in trial.get("choice_ids", choices)]}
            if trial["status"] in ("ready", "answered"):
                item["audio_url"] = "/api/blind/trials/" + trial["id"] + "/audio"
                item["listened"] = bool(trial.get("listened"))
                if trial.get("practice"):
                    item["practice"] = True
            if trial["status"] == "failed":
                item["error"] = trial["error"]
            if trial["status"] == "answered":
                recipe = session["recipes"][trial["target"]]
                item.update(reveal={"profile_id": trial["target"], "name": recipe["name"], "cue": recipe["cue"],
                                    "prompt": recipe["prompt"], "arrangement": recipe["arrangement"], "instrument_name": recipe.get("instrument_name", ""), "model": session["model"],
                                    "recipe_revision": recipe["recipe_revision"], "supplied_lyrics": recipe["supplied_lyrics"], "lyrics": trial.get("lyrics", "")},
                            guess=trial["guess"], correct=trial["correct"], reaction=trial.get("reaction"),
                            scored=trial.get("scored", True), practice=not trial.get("scored", True))
            trials.append(item)
        completed = sum(t["status"] == "answered" for t in trials)
        return {**{key: deepcopy(session[key]) for key in ("id", "mode", "size", "model", "revision", "choices", "created_at")},
                "choices": list(choices.values()),
                "format": session.get("format", "full" if session["model"] == FORMATS["full"] else "clip"),
                "include_challenger": session.get("include_challenger", False),
                "pool_group_id": session["group_id"],
                "trials": trials, "current_trial": trials[-1] if trials else None, "completed": completed, "finished": session["size"] is not None and completed >= session["size"],
                "ready_count": len(self._available_pool(session))}

    def get(self, identifier):
        with self.workshop.lock:
            return self.public(self._session(identifier))

    def next(self, identifier, payload):
        request_id = payload.get("request_id") if isinstance(payload, dict) else None
        if not isinstance(request_id, str) or not ID.fullmatch(request_id):
            raise self.Error("A valid clip request ID is required.")
        generate = payload.get("generate", False)
        fallback = payload.get("generate_if_needed", False)
        replay, hours = payload.get("replay", "none"), payload.get("replay_after_hours", 24)
        if type(generate) is not bool or type(fallback) is not bool:
            raise self.Error("Generation must be an explicit boolean choice.")
        if not isinstance(replay, str) or replay not in ("none", "all", "incorrect") or type(hours) not in (int, float) or not math.isfinite(hours) or not 0 <= hours <= 87600:
            raise self.Error("Choose a replay mode and a finite interval between 0 and 87,600 hours.")
        options = {"generate": generate, "generate_if_needed": fallback, "replay": replay, "replay_after_hours": hours}
        with self.workshop.lock:
            session = self._session(identifier)
            if request_id in session["requests"]:
                previous = next(t for t in session["trials"] if t["id"] == session["requests"][request_id])
                previous_options = previous.get("request_options", {"generate": previous.get("generate", True), "generate_if_needed": False, "replay": "none", "replay_after_hours": 24})
                if previous_options != options:
                    raise self.Error("This request ID was already used for a different clip action.", 409)
                return self.public(session)
            if self.exposure_error:
                raise self.Error("Saved listening history could not be read. Its file was preserved; restore it before generating more blind clips.", 409)
            if self.pool_error:
                raise self.Error("Saved clip pool records could not be read. They were preserved; restore them before continuing. No paid fallback was started.", 409)
            completed = sum(t["status"] == "answered" for t in session["trials"])
            if session["size"] is not None and completed >= session["size"]:
                raise self.Error("This session is complete. Start another session for fresh clips.", 409)
            if session["trials"] and session["trials"][-1]["status"] not in ("answered", "failed"):
                raise self.Error("Finish the current clip before generating another.", 409)
            if not generate:
                if replay != "none":
                    candidate = self._due_replay(session, replay, hours)
                    if candidate:
                        return self._replay(session, candidate, request_id, completed, options)
                if self._available_pool(session):
                    return self._consume(session, request_id, completed, options)
                if not fallback:
                    raise self.Error("No fresh saved clips or due replays are available for this session. Explicitly generate or replenish the matching pool before continuing.", 409)
            if self.workshop.active_id:
                raise self.Error("Music is already generating. Wait for it to finish.", 409)
            if not self.workshop.key_reader():
                raise self.Error("Add your Google key with python3 tools/configure_key.py, then try again.", 503)
            updated = deepcopy(session)
            if completed >= len(updated["plan"]):
                counts = self._target_counts(session)
                least = min(counts[c["id"]] for c in session["choices"])
                updated["plan"].append(secrets.choice([c["id"] for c in session["choices"] if counts[c["id"]] == least]))
            trial = {"id": secrets.token_hex(16), "target": updated["plan"][completed], "status": "queued", "created_at": now(), "request_id": request_id, "generate": True, "request_options": options}
            self._offer_choices(updated, trial)
            updated["trials"].append(trial)
            updated["requests"][request_id] = trial["id"]
            self._save(updated)  # Durable receipt before any paid call.
            self.sessions[identifier] = updated
            self.workshop.active_id = trial["id"]
            self.workshop.jobs[trial["id"]] = {"id": trial["id"], "status": "queued", "kind": "blind"}
            threading.Thread(target=self._generate, args=(identifier, trial["id"]), daemon=True).start()
            return self.public(updated)

    def _target_counts(self, session):
        return Counter(t["target"] for s in self.sessions.values() if s["group_id"] == session["group_id"] for t in s["trials"]
                       if t["status"] in ("queued", "generating", "ready", "answered") and not t.get("practice") and t.get("scored", True))

    @staticmethod
    def _set_target(session, index, target):
        if index < len(session["plan"]):
            session["plan"][index] = target
        else:
            session["plan"].append(target)

    def _consume(self, session, request_id, completed, options):
        available = self._available_pool(session)
        if not available:
            raise self.Error("No fresh saved clips are available for this session. Explicitly generate or replenish the matching clip pool before continuing.", 409)
        counts = self._target_counts(session)
        minimum = min(counts[r["target"]] for r in available)
        source = secrets.choice([r for r in available if counts[r["target"]] == minimum])
        trial = {"id": secrets.token_hex(16), "target": source["target"], "status": "ready", "created_at": now(),
                 "request_id": request_id, "generate": False, "source_id": source["id"], "request_options": options,
                 **{key: source[key] for key in ("audio_sha256", "mime_type", "lyrics", "ready_at")}}
        updated = deepcopy(session)
        self._set_target(updated, completed, source["target"])
        self._offer_choices(updated, trial)
        updated["trials"].append(trial)
        updated["requests"][request_id] = trial["id"]
        self._save(updated)  # Commit ownership before returning audio or updating the pool.
        self.sessions[session["id"]] = updated
        source["claimed_by"] = trial["id"]
        self._save_pool(source)
        return self.public(updated)

    def _due_replay(self, session, replay, hours):
        pending = {t.get("audio_sha256") for s in self.sessions.values() for t in s["trials"] if t["status"] == "ready"}
        latest = {}
        for stored in self.sessions.values():
            if stored["group_id"] != session["group_id"]:
                continue
            for trial in stored["trials"]:
                if trial["status"] == "answered" and trial["audio_sha256"] not in pending:
                    previous = latest.get(trial["audio_sha256"])
                    order = lambda item: (item.get("judgment_order", 0) if type(item.get("judgment_order", 0)) is int else 0, item.get("answered_at", ""))
                    if not previous or order(trial) >= order(previous):
                        latest[trial["audio_sha256"]] = trial
        current = datetime.fromisoformat(now())
        candidates = []
        for audio_hash, trial in latest.items():
            exposure = self.exposures.get(audio_hash, {})
            # The durable answered trial is authoritative if a previous crash
            # separated its write from the exposure-ledger update.
            if replay == "incorrect" and trial["correct"]:
                continue
            timestamp = exposure.get("last_played_at") or exposure.get("first_seen_at")
            try:
                heard = datetime.fromisoformat(timestamp)
                if heard.tzinfo is None or (current - heard).total_seconds() < hours * 3600:
                    continue
            except (TypeError, ValueError):
                continue
            try:
                self.audio_file(trial["id"], expose=False)
            except self.Error:
                continue
            candidates.append((heard, trial))
        if not candidates:
            return None
        oldest = min(heard for heard, _ in candidates)
        return secrets.choice([trial for heard, trial in candidates if heard == oldest])

    def _replay(self, session, source, request_id, completed, options):
        trial = {"id": secrets.token_hex(16), "target": source["target"], "status": "ready", "created_at": now(),
                 "request_id": request_id, "request_options": options, "generate": False, "practice": True,
                 "source_id": source.get("source_id", source["id"]), "source_trial_id": source["id"],
                 **{key: source[key] for key in ("audio_sha256", "mime_type", "lyrics", "ready_at")}}
        updated = deepcopy(session)
        self._set_target(updated, completed, trial["target"])
        self._offer_choices(updated, trial)
        updated["trials"].append(trial)
        updated["requests"][request_id] = trial["id"]
        self._save(updated)
        self.sessions[session["id"]] = updated
        return self.public(updated)

    def _generate(self, session_id, trial_id):
        try:
            with self.workshop.lock:
                session, trial = self._trial(trial_id)
                trial["status"] = "generating"
                self._save(session)
                self.workshop.jobs[trial_id]["status"] = "generating"
                recipe = deepcopy(session["recipes"][trial["target"]])
                model = session["model"]
            key = self.workshop.key_reader()
            if not key:
                raise self.Error("The Google key is no longer configured.")
            audio, mime, lyrics = self.parse_audio(self.workshop.generator(recipe["prompt"], key, model=model))
            with self.workshop.lock:
                session, trial = self._trial(trial_id)
                self._ensure_storage()
                self.write(self.base / "audio" / (trial_id + self.audio_formats[mime]), audio)
                audio_hash = hashlib.sha256(audio).hexdigest()
                known = audio_hash in self.exposures or any(r.get("audio_sha256") == audio_hash for r in self.pool.values()) or any(
                    other.get("audio_sha256") == audio_hash for stored in self.sessions.values() for other in stored["trials"] if other["id"] != trial_id)
                trial.update(status="ready", mime_type=mime, lyrics=lyrics, audio_sha256=audio_hash, ready_at=now())
                if known:
                    trial["practice"] = True
                self._save(session)
                self.workshop.jobs[trial_id]["status"] = "completed"
        except Exception as error:
            with self.workshop.lock:
                session, trial = self._trial(trial_id)
                # Provider diagnostics can contain the answer or whole prompt.
                code = getattr(error, "details", None)
                http_status = code.get("http_status") if isinstance(code, dict) else None
                prefix = "Google HTTP " + str(http_status) + ". " if type(http_status) is int else ""
                message = prefix + "This clip could not be completed or saved. The request may have incurred a charge. No automatic retry was made."
                trial.update(status="failed", error=message, failed_at=now())
                self.workshop.jobs[trial_id] = {"id": trial_id, "kind": "blind", "status": "failed", "error": message, "failed_at": now()}
                try:
                    self._save(session)
                except (OSError, self.Error):
                    pass
        finally:
            with self.workshop.lock:
                if self.workshop.active_id == trial_id:
                    self.workshop.active_id = None

    def _expose(self, trial, *, reveal=False, heard=False, guess=None):
        if self.exposure_error:
            raise self.Error("Saved listening history could not be read. Its file was preserved; restore it before playing or scoring more blind clips.", 409)
        audio_hash = trial["audio_sha256"]
        first = self.exposures.get(audio_hash)
        exposures = deepcopy(self.exposures)
        changed = False
        if not isinstance(first, dict) or not isinstance(first.get("trial_id"), str):
            first = {"trial_id": trial["id"], "first_seen_at": now()}
            exposures[audio_hash] = first
            changed = True
        else:
            first = exposures[audio_hash]
        scored = not trial.get("practice") and first["trial_id"] == trial["id"] and first.get("revealed_by") in (None, trial["id"])
        if reveal and not first.get("revealed_by"):
            first.update(revealed_by=trial["id"], revealed_at=now())
            changed = True
        if heard:
            first["last_played_at"] = now()
            changed = True
        if guess is not None:
            first.update(latest_guess=guess, latest_correct=guess == trial["target"], latest_trial_id=trial["id"], last_judged_at=now())
            changed = True
        if changed:
            self._save_exposures(exposures)
        return scored

    def guess(self, identifier, payload):
        answer = payload.get("guess") if isinstance(payload, dict) else None
        with self.workshop.lock:
            session, trial = self._trial(identifier)
            session = self._prepare_choices(session)
            trial = next(t for t in session["trials"] if t["id"] == identifier)
            choices = set(trial.get("choice_ids", [c["id"] for c in session["choices"]])) | {"unsure"}
            if not isinstance(answer, str) or answer not in choices:
                raise self.Error("Choose one of this clip's offered styles or unsure.")
            if trial["status"] == "answered":
                if trial["guess"] != answer:
                    raise self.Error("The first answer is already saved and cannot be changed.", 409)
                return self.public(session)
            if trial["status"] != "ready":
                raise self.Error("Wait for the clip before answering.", 409)
            scored = self._expose(trial, reveal=True, guess=answer)
            updated = deepcopy(session)
            saved = next(t for t in updated["trials"] if t["id"] == identifier)
            judgment_order = 1 + max((t.get("judgment_order", 0) for s in self.sessions.values() for t in s["trials"] if type(t.get("judgment_order", 0)) is int), default=0)
            saved.update(status="answered", guess=answer, correct=answer == trial["target"], answered_at=now(), judgment_order=judgment_order, reaction=None, scored=scored)
            self._save(updated)
            self.sessions[session["id"]] = updated
            return self.public(updated)

    def played(self, identifier, payload):
        if not isinstance(payload, dict) or type(payload.get("completed", False)) is not bool:
            raise self.Error("Send a valid playback event.")
        with self.workshop.lock:
            session, trial = self._trial(identifier)
            if trial["status"] not in ("ready", "answered"):
                raise self.Error("This recording is not ready to play.", 409)
            self._expose(trial, heard=True)
            if payload.get("completed") and not trial.get("listened"):
                updated = deepcopy(session)
                next(t for t in updated["trials"] if t["id"] == identifier)["listened"] = True
                self._save(updated)
                self.sessions[session["id"]] = updated
                session = updated
            return self.public(session)

    def reaction(self, identifier, payload):
        if not isinstance(payload, dict) or "reaction" not in payload or payload["reaction"] not in ("keep", "rework", None):
            raise self.Error("Choose keep, rework, or clear the reaction.")
        with self.workshop.lock:
            session, trial = self._trial(identifier)
            if trial["status"] != "answered":
                raise self.Error("Answer before recording a reaction.", 409)
            updated = deepcopy(session)
            next(t for t in updated["trials"] if t["id"] == identifier)["reaction"] = payload["reaction"]
            self._save(updated)
            self.sessions[session["id"]] = updated
            return self.public(updated)

    def audio_file(self, identifier, *, expose=True):
        with self.workshop.lock:
            session, trial = self._trial(identifier)
            if trial["status"] not in ("ready", "answered"):
                raise self.Error("Blind audio is not ready.", 404)
            source_id = trial.get("source_id", identifier)
            if not isinstance(source_id, str) or not ID.fullmatch(source_id):
                raise self.Error("Blind audio not found.", 404)
            path = self.base / "audio" / (source_id + self.audio_formats[trial["mime_type"]])
            if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.is_file():
                raise self.Error("Blind audio not found.", 404)
            if expose:
                self._expose(trial, heard=True)
            return path, trial["mime_type"]

    def seed_plan(self, *, mode="canonical", clips_per_style=3, max_clips=33, include_challenger=False, format="clip"):
        """Describe exact-cohort deficits without keys, writes, sessions or charges."""
        if not isinstance(mode, str) or mode not in MODES or type(clips_per_style) is not int or not 1 <= clips_per_style <= 100 or type(max_clips) is not int or not 1 <= max_clips <= 1000 or type(include_challenger) is not bool or not isinstance(format, str) or format not in FORMATS:
            raise self.Error("Choose a supported mode, 1–100 clips per style and a 1–1000 new-call limit.")
        with self.workshop.lock:
            cohort = self._cohort(mode, include_challenger, format)
            counts = Counter(r["target"] for r in self._available_pool(cohort))
            blocked = [{"id": r["id"], "status": r["status"]} for r in self.pool.values()
                       if r["group_id"] == cohort["group_id"] and r["status"] in ("queued", "generating", "failed", "interrupted", "duplicate")]
            styles = [{**c, "ready": counts[c["id"]], "needed": max(0, clips_per_style - counts[c["id"]])} for c in cohort["choices"]]
            needed = sum(s["needed"] for s in styles)
            return {"mode": mode, "format": format, "model": cohort["model"], "revision": cohort["revision"], "group_id": cohort["group_id"],
                    "choice_count": len(styles), "clips_per_style": clips_per_style, "max_clips": max_clips,
                    "include_challenger": include_challenger, "by_style": styles, "ready": sum(counts.values()),
                    "needed": needed, "planned": min(needed, max_clips), "blocked": blocked,
                    "storage_error": self.exposure_error or self.pool_error}

    def seed(self, *, mode="canonical", clips_per_style=3, max_clips=33, include_challenger=False, format="clip", execute=False, on_event=None):
        """Seed a bounded fresh pool; every call needs explicit execute=True.

        Failed or unknown receipts block automatic resumption of that cohort.
        Successful prior receipts are reused; judged/claimed clips are replenished
        only through a later explicit seed invocation.
        """
        plan = self.seed_plan(mode=mode, clips_per_style=clips_per_style, max_clips=max_clips, include_challenger=include_challenger, format=format)
        report = {**plan, "executed": execute is True, "attempted": 0, "completed": 0, "failed": 0, "duplicates": 0,
                  "skipped": plan["ready"], "stopped": False, "remaining": plan["needed"]}
        if execute is not True:
            return report
        with self.workshop.lock:
            if self.workshop.active_id:
                raise self.Error("Music is already generating. Wait before seeding clips.", 409)
            if plan["storage_error"]:
                raise self.Error("Saved pool or listening history could not be read. Restore it before seeding clips.", 409)
            if plan["blocked"]:
                report.update(stopped=True, error="A failed or interrupted attempt exists for this cohort. Its receipt was preserved; no automatic retry was made.")
                return report
            if not plan["planned"]:
                return report
            if not self.workshop.key_reader():
                raise self.Error("Add your Google key with python3 tools/configure_key.py before seeding clips.", 503)
            cohort = self._cohort(mode, include_challenger, format)
            if cohort["group_id"] != plan["group_id"]:
                raise self.Error("The palette changed. Review a fresh seed plan before executing.", 409)
            run_id = secrets.token_hex(16)
            report.update(run_id=run_id, started_at=now())
            self._ensure_storage()
            report_path = self.base / "seed-reports" / (run_id + ".json")
            report["report_path"] = str(report_path)
            self.write(report_path, json.dumps(report, ensure_ascii=False, indent=2).encode())
            self.workshop.active_id = run_id
            self.workshop.jobs[run_id] = {"id": run_id, "kind": "blind_seed", "status": "generating"}
        counts = Counter({s["id"]: s["ready"] for s in plan["by_style"]})
        try:
            for _ in range(plan["planned"]):
                least = min(counts[c["id"]] for c in cohort["choices"] if counts[c["id"]] < clips_per_style)
                target = secrets.choice([c["id"] for c in cohort["choices"] if counts[c["id"]] == least])
                source_id = secrets.token_hex(16)
                record = {"version": 1, "id": source_id, "status": "queued", "target": target, "group_id": cohort["group_id"],
                          "mode": mode, "format": format, "model": cohort["model"], "revision": cohort["revision"], "recipe": deepcopy(cohort["recipes"][target]),
                          "created_at": now(), "seed_run_id": run_id, "claimed_by": None}
                try:
                    with self.workshop.lock:
                        self._save_pool(record)  # Receipt commits before provider access.
                        self.pool[source_id] = record
                        record["status"] = "generating"
                        self._save_pool(record)
                    key = self.workshop.key_reader()
                    if not key:
                        raise self.Error("The Google key is no longer configured.")
                    report["attempted"] += 1
                    audio, mime, lyrics = self.parse_audio(self.workshop.generator(record["recipe"]["prompt"], key, model=record["model"]))
                    with self.workshop.lock:
                        audio_hash = hashlib.sha256(audio).hexdigest()
                        duplicate = audio_hash in self.exposures or any(r.get("audio_sha256") == audio_hash for r in self.pool.values() if r["id"] != source_id)
                        self.write(self.base / "audio" / (source_id + self.audio_formats[mime]), audio)
                        record.update(status="duplicate" if duplicate else "ready", audio_sha256=audio_hash, mime_type=mime,
                                      lyrics=lyrics, ready_at=now())
                        if duplicate:
                            record["error"] = "The provider returned an already saved recording. No automatic replacement was generated."
                        self._save_pool(record)
                    if duplicate:
                        report.update(stopped=True, duplicates=report["duplicates"] + 1, error=record["error"])
                        if on_event:
                            on_event({"event": "stopped", "attempted": report["attempted"], "completed": report["completed"], "duplicates": report["duplicates"], "error": record["error"]})
                        break
                    report["completed"] += 1
                    counts[target] += 1
                    report["remaining"] -= 1
                    self.write(report_path, json.dumps(report, ensure_ascii=False, indent=2).encode())
                    if on_event:
                        on_event({"event": "saved", "id": source_id, "completed": report["completed"], "planned": plan["planned"]})
                except Exception as error:
                    details = getattr(error, "details", None)
                    code = details.get("http_status") if isinstance(details, dict) else None
                    prefix = "Google HTTP " + str(code) + ". " if type(code) is int else ""
                    message = prefix + "Seeding stopped after this attempt could not be completed or saved. Check its receipt and provider usage. No automatic retry was made."
                    # Never discard a committed successful clip because later
                    # report-writing failed. All other unknown outcomes block resume.
                    if record.get("status") != "ready" or source_id not in self.pool:
                        record.update(status="failed", error=message, failed_at=now())
                    else:
                        saved = read_json(self.base / "pool" / (source_id + ".json"))
                        if not isinstance(saved, dict) or saved.get("status") != "ready":
                            record.update(status="failed", error=message, failed_at=now())
                    self.pool[source_id] = record
                    try:
                        self._save_pool(record)
                    except (OSError, self.Error):
                        self.pool_error = True
                    failed_clip = record.get("status") not in ("ready", "duplicate")
                    report.update(stopped=True, error=message, failed=report["failed"] + int(failed_clip))
                    if not failed_clip:
                        report["report_error"] = True
                    if on_event:
                        on_event({"event": "stopped", "attempted": report["attempted"], "completed": report["completed"], "failed": report["failed"], "error": message})
                    break
        except (KeyboardInterrupt, SystemExit):
            message = "Seeding was interrupted. Any in-flight request may have incurred a charge; its result is unknown. No automatic retry was made."
            report.update(stopped=True, interrupted=True, error=message)
            with self.workshop.lock:
                for pending in self.pool.values():
                    if pending.get("seed_run_id") == run_id and pending["status"] in ("queued", "generating"):
                        pending.update(status="interrupted", error=message)
                        try:
                            self._save_pool(pending)
                        except (OSError, self.Error):
                            self.pool_error = True
        finally:
            report["finished_at"] = now()
            actual = Counter(r["target"] for r in self._available_pool(cohort))
            report["ready_after"] = sum(actual.values())
            report["remaining"] = sum(max(0, clips_per_style - actual[c["id"]]) for c in cohort["choices"])
            try:
                report["report_saved"] = True
                self.write(report_path, json.dumps(report, ensure_ascii=False, indent=2).encode())
            except OSError:
                report.update(stopped=True, report_saved=False, error="The seed report could not be saved. Clip receipts were retained; inspect them before continuing.")
            with self.workshop.lock:
                if self.workshop.active_id == run_id:
                    self.workshop.active_id = None
                self.workshop.jobs[run_id]["status"] = "failed" if report["stopped"] else "completed"
        return report

    def stats(self):
        with self.workshop.lock:
            groups = {}
            for session in self.sessions.values():
                answered = [t for t in session["trials"] if t["status"] == "answered" and t.get("scored", True)]
                if not answered:
                    continue
                for trial in answered:
                    contract = trial.get("presentation_contract", LEGACY_PRESENTATION)
                    choice_count = len(trial.get("choice_ids", session["choices"]))
                    # Preserve legacy group IDs, but never blend different
                    # guessing tasks merely because their audio recipes match.
                    group_id = session["group_id"] if contract == LEGACY_PRESENTATION else digest({"pool_group_id": session["group_id"], "presentation_contract": contract, "choice_count": choice_count})
                    group = groups.setdefault(group_id, {"id": group_id, "pool_group_id": session["group_id"], "presentation_contract": contract,
                                                        "mode": session["mode"], "format": session.get("format", "clip"), "model": session["model"], "revision": session["revision"], "choice_count": choice_count, "attempts": 0, "correct": 0,
                                                        "styles": {c["id"]: {**c, "attempts": 0, "correct": 0} for c in session["choices"]}, "confusion": Counter()})
                    group["attempts"] += 1
                    group["correct"] += int(trial["correct"])
                    style = group["styles"][trial["target"]]
                    style["attempts"] += 1
                    style["correct"] += int(trial["correct"])
                    if not trial["correct"]:
                        group["confusion"][(trial["target"], trial["guess"])] += 1
            output = []
            for group in groups.values():
                styles = group.pop("styles")
                confusion = group.pop("confusion")
                group.update(accuracy=group["correct"] / group["attempts"], chance=1 / group["choice_count"],
                             per_style=[{**s, "accuracy": s["correct"] / s["attempts"] if s["attempts"] else None} for s in styles.values()],
                             confusions=[{"target": t, "guess": g, "count": count} for (t, g), count in sorted(confusion.items(), key=lambda item: (-item[1], item[0]))])
                output.append(group)
            return {"groups": output}
