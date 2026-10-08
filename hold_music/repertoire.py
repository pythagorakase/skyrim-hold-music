"""Deterministic, read-only repertoire decisions from an actor-scoped snapshot.

Times are explicit in-game hours in one save/world clock domain. The adapter must
not replace unknown event/learning times with retrieval time. A plan is not a
completed job, acquired song, performed song, or budget receipt.
topic_id identifies the same claim/subject across retellings, not a broad news
category. Distinct factual developments need distinct normalized topic IDs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math
from typing import Any

MODES = {"lyrical", "wordless", "instrumental"}
ACTIONS = {"compose_lyrics", "generate_recording"}
KINDS = {"quest_success", "scandal", "gossip", "everyday_news", "other"}


@dataclass(frozen=True)
class Request:
    tradition: str
    arrangement: str
    mode: str
    voice: str
    recipe_id: str
    model_id: str


@dataclass(frozen=True)
class Scoped:
    save_id: str
    world_id: str
    id: str


@dataclass(frozen=True)
class Observation(Scoped):
    performer_id: str
    event_id: str
    topic_id: str
    kind: str
    summary: str
    happened_at: float | None
    learned_at: float | None
    source_id: str
    evidence: str
    interest: float
    local_relevance: float


@dataclass(frozen=True)
class Composition(Scoped):
    title: str
    tradition: str
    mode: str
    known_by: tuple[str, ...]
    composer_id: str
    created_at: float
    lyrics: str | None = None
    topic_id: str | None = None
    source_observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Recording(Scoped):
    composition_id: str
    performer_id: str
    request: Request
    playable: bool
    created_at: float


@dataclass(frozen=True)
class Performance(Scoped):
    performer_id: str
    composition_id: str
    at: float
    recording_id: str | None = None
    topic_id: str | None = None


@dataclass(frozen=True)
class PendingJob(Scoped):
    performer_id: str
    action: str
    request: Request
    created_at: float
    status: str = "queued"
    topic_id: str | None = None
    composition_id: str | None = None
    work_key: str | None = None


@dataclass(frozen=True)
class GenerationReceipt(Scoped):
    """Confirmed starts, including failed attempts; id is the executor's job id."""
    performer_id: str
    action: str
    at: float


@dataclass(frozen=True)
class Policy:
    selection: str = "cache_first"
    topic_max_age_hours: float = 72.0
    knowledge_max_age_hours: float = 48.0
    salience_threshold: float = 0.75
    composition_cooldown_hours: float = 24.0
    recording_cooldown_hours: float = 1.0
    song_repeat_hours: float = 4.0
    topic_repeat_hours: float = 24.0
    budget_window_hours: float = 24.0
    max_lyric_jobs: int = 2
    max_recording_jobs: int = 2
    max_pending_jobs: int = 1


def _text(value: Any, name: str, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")


def _number(value: Any, name: str, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")


def _read(cls: type, source: dict) -> Any:
    if not isinstance(source, dict):
        raise ValueError(f"{cls.__name__} must be an object")
    data = dict(source)
    unknown = set(data) - {f.name for f in fields(cls)}
    if unknown:
        raise ValueError(f"Unknown {cls.__name__} fields: {', '.join(sorted(unknown))}")
    if cls in (Recording, PendingJob) and "request" in data:
        data["request"] = _read(Request, data["request"])
    for name in ("known_by", "source_observation_ids"):
        if name in data:
            if not isinstance(data[name], (list, tuple)):
                raise ValueError(f"{name} must be a list")
            for item in data[name]:
                _text(item, name)
            data[name] = tuple(data[name])
    try:
        obj = cls(**data)
    except TypeError as exc:
        raise ValueError(f"Invalid {cls.__name__}: {exc}") from exc
    for name in ("save_id", "world_id", "id", "performer_id", "event_id", "source_id", "summary", "title", "tradition", "composer_id", "arrangement", "voice", "recipe_id", "model_id"):
        if hasattr(obj, name):
            _text(getattr(obj, name), name)
    for name in ("topic_id", "composition_id", "recording_id", "work_key"):
        if hasattr(obj, name):
            required = (name == "topic_id" and cls is Observation) or (name == "composition_id" and cls in (Recording, Performance))
            _text(getattr(obj, name), name, not required)
    for name in ("created_at", "at", "happened_at", "learned_at", "interest", "local_relevance"):
        if hasattr(obj, name):
            _number(getattr(obj, name), name, name in ("happened_at", "learned_at"))
    if hasattr(obj, "mode") and obj.mode not in MODES:
        raise ValueError("mode must be lyrical, wordless, or instrumental")
    if cls is Request and obj.mode == "instrumental" and obj.voice != "none":
        raise ValueError("Instrumental requests must set voice to 'none'")
    if cls is Observation:
        if obj.kind not in KINDS or obj.evidence not in {"direct", "rumor"}:
            raise ValueError("Observation kind/evidence must use the explicit enums")
        if obj.interest > 1 or obj.local_relevance > 1:
            raise ValueError("Observation interest and local_relevance must be in [0, 1]")
        if obj.happened_at is not None and obj.learned_at is not None and obj.learned_at < obj.happened_at:
            raise ValueError("An observation cannot be learned before its event happened")
    if cls is Composition:
        if obj.mode == "lyrical":
            _text(obj.lyrics, "lyrical composition lyrics")
        elif obj.lyrics not in (None, ""):
            raise ValueError("Wordless/instrumental compositions cannot contain lyrics")
    if cls is Recording and not isinstance(obj.playable, bool):
        raise ValueError("playable must be a boolean supplied by the cache adapter")
    if cls in (PendingJob, GenerationReceipt) and obj.action not in ACTIONS:
        raise ValueError("Unknown generation action")
    if cls is PendingJob and obj.status not in {"queued", "running", "failed", "cancelled", "completed"}:
        raise ValueError("Unknown pending-job status")
    if cls is Policy:
        if obj.selection not in {"cache_first", "topical_when_salient"}:
            raise ValueError("Unknown selection policy")
        for f in fields(cls):
            if f.name != "selection":
                _number(getattr(obj, f.name), f.name)
                if f.name.startswith("max_") and type(getattr(obj, f.name)) is not int:
                    raise ValueError(f"{f.name} must be an integer")
        if obj.salience_threshold > 1 or obj.budget_window_hours <= 0:
            raise ValueError("Invalid salience threshold or budget window")
    return obj


@dataclass(frozen=True)
class Snapshot:
    save_id: str
    world_id: str
    performer_id: str
    now_hours: float
    request: Request
    observations: tuple[Observation, ...] = ()
    compositions: tuple[Composition, ...] = ()
    recordings: tuple[Recording, ...] = ()
    recent_performances: tuple[Performance, ...] = ()
    pending_jobs: tuple[PendingJob, ...] = ()
    generation_history: tuple[GenerationReceipt, ...] = ()
    policy: Policy = Policy()

    @classmethod
    def from_dict(cls, source: dict) -> Snapshot:
        if not isinstance(source, dict):
            raise ValueError("Snapshot must be an object")
        data = dict(source)
        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown Snapshot fields: {', '.join(sorted(unknown))}")
        data["request"] = _read(Request, data.get("request", {}))
        data["policy"] = _read(Policy, data.get("policy", {}))
        types = {"observations": Observation, "compositions": Composition, "recordings": Recording,
                 "recent_performances": Performance, "pending_jobs": PendingJob, "generation_history": GenerationReceipt}
        for key, item_type in types.items():
            rows = data.get(key, [])
            if not isinstance(rows, (list, tuple)):
                raise ValueError(f"{key} must be a list")
            data[key] = tuple(_read(item_type, row) for row in rows)
            ids = [(row.save_id, row.world_id, row.id) for row in data[key]]
            if len(set(ids)) != len(ids):
                raise ValueError(f"Duplicate scoped identifiers in {key}")
        try:
            obj = cls(**data)
        except TypeError as exc:
            raise ValueError(f"Invalid Snapshot: {exc}") from exc
        for name in ("save_id", "world_id", "performer_id"):
            _text(getattr(obj, name), name)
        _number(obj.now_hours, "now_hours")
        return obj


class _Planner:
    def __init__(self, snapshot: Snapshot):
        self.s, self.p, self.r, self.now = snapshot, snapshot.policy, snapshot.request, snapshot.now_hours
        self.history = [x for x in snapshot.recent_performances if self.actor(x) and x.at <= self.now]
        self.receipts = [x for x in snapshot.generation_history if self.actor(x) and x.at <= self.now]
        self.jobs = sorted((x for x in snapshot.pending_jobs if self.actor(x) and x.created_at <= self.now
                            and x.status in {"queued", "running"}), key=lambda x: (x.created_at, x.id))
        self.known = {x.id: x for x in snapshot.compositions if self.scope(x) and x.created_at <= self.now
                      and snapshot.performer_id in x.known_by}
        self.suitable = {key: c for key, c in self.known.items() if c.tradition == self.r.tradition
                         and (self.r.mode != "lyrical" or c.mode == "lyrical") and not self.repeated(c)}
        self.recordings = [x for x in snapshot.recordings if self.actor(x) and x.playable and x.request == self.r
                          and x.composition_id in self.suitable
                          and self.suitable[x.composition_id].created_at <= x.created_at <= self.now]
        self.recording = self.best_recording(self.recordings)
        self.topic_diagnostics: list[str] = []
        self.subject = self.choose_subject() if self.r.mode == "lyrical" else None

    def scope(self, item: Scoped) -> bool:
        return item.save_id == self.s.save_id and item.world_id == self.s.world_id

    def actor(self, item: Any) -> bool:
        return self.scope(item) and item.performer_id == self.s.performer_id

    def last_play(self, composition_id: str) -> float:
        return max((x.at for x in self.history if x.composition_id == composition_id), default=-1)

    def best_recording(self, recordings: list[Recording]) -> Recording | None:
        return min(recordings, key=lambda x: (self.last_play(x.composition_id), -x.created_at, x.id), default=None)

    def topic_recent(self, topic_id: str | None) -> bool:
        return bool(topic_id) and any(
            self.now - x.at < self.p.topic_repeat_hours
            and (x.topic_id == topic_id or (x.composition_id in self.known and self.known[x.composition_id].topic_id == topic_id))
            for x in self.history)

    def repeated(self, composition: Composition) -> bool:
        last = self.last_play(composition.id)
        return (last >= 0 and self.now - last < self.p.song_repeat_hours) or self.topic_recent(composition.topic_id)

    def choose_subject(self) -> dict | None:
        groups: dict[str, list[Observation]] = {}
        for item in self.s.observations:
            if not self.actor(item):
                continue
            if any(value is not None and value > self.now for value in (item.happened_at, item.learned_at)):
                self.topic_diagnostics.append("Future-dated knowledge was excluded.")
                continue
            groups.setdefault(item.topic_id, []).append(item)
        covered = {c.topic_id for c in self.known.values() if c.mode == "lyrical" and c.topic_id}
        choices = []
        for topic_id, reports in groups.items():
            if any(x.happened_at is None or x.learned_at is None for x in reports):
                self.topic_diagnostics.append("Unknown event/learning age was excluded from fresh-topic ranking.")
                continue
            happened, learned = min(x.happened_at for x in reports), min(x.learned_at for x in reports)
            if self.now - happened > self.p.topic_max_age_hours or self.now - learned > self.p.knowledge_max_age_hours:
                continue
            # Direct evidence can replace a rumor, but copies cannot confer truth or freshness.
            item = min(reports, key=lambda x: (x.evidence != "direct", x.learned_at, x.id))
            score = (item.interest + item.local_relevance) / 2
            reusable = any(c.topic_id == item.topic_id for c in self.suitable.values())
            if score < self.p.salience_threshold or self.topic_recent(item.topic_id) or (item.topic_id in covered and not reusable):
                continue
            subject = {"event_id": item.event_id, "topic_id": topic_id, "kind": item.kind,
                       "summary": item.summary, "evidence": item.evidence, "salience": score,
                       "happened_at": happened, "learned_at": learned,
                       "source_observation_ids": [item.id], "source_ids": [item.source_id]}
            choices.append(subject)
        return min(choices, key=lambda x: (-x["salience"], -x["happened_at"], -x["learned_at"], x["topic_id"], x["event_id"]), default=None)

    def result(self, action: str, reasons: list[str], **extra: Any) -> dict:
        output = {"version": 1, "action": action, "save_id": self.s.save_id,
                  "world_id": self.s.world_id, "performer_id": self.s.performer_id,
                  "request": asdict(self.r), "reasons": reasons, "subject": None,
                  "composition_id": None, "recording_id": None, "lyric_brief": None,
                  "recording_brief": None, "fallback": None, "pending_job_id": None,
                  "work_key": None, "retry_at": None}
        output.update(extra)
        return output

    def play(self, reasons: list[str] | None = None, recording: Recording | None = None) -> dict:
        recording = recording or self.recording
        return self.result("play_recording", reasons or ["An eligible actor-known recording matches every requested identity field."],
                           recording_id=recording.id, composition_id=recording.composition_id)

    def fallback(self) -> dict | None:
        return ({"action": "play_recording", "recording_id": self.recording.id,
                 "composition_id": self.recording.composition_id} if self.recording else None)

    def work(self, action: str, composition: Composition | None = None, subject: dict | None = None) -> dict:
        cid, topic = (composition.id if composition else None), (subject["topic_id"] if subject else None)
        matching = next((job for job in self.jobs if job.action == action and (
            (action == "compose_lyrics" and job.topic_id == topic)
            or (action == "generate_recording" and job.composition_id == cid and job.request == self.r))), None)
        common = {"composition_id": cid, "subject": subject, "fallback": self.fallback()}
        if matching:
            return self.result("wait", ["Equivalent work is already pending; do not submit it again."],
                               pending_job_id=matching.id, **common)
        if len(self.jobs) >= self.p.max_pending_jobs:
            return self.result("wait", ["The actor's pending-job capacity is exhausted."],
                               pending_job_id=self.jobs[0].id if self.jobs else None, **common)
        cooldown = self.p.composition_cooldown_hours if action == "compose_lyrics" else self.p.recording_cooldown_hours
        cap = self.p.max_lyric_jobs if action == "compose_lyrics" else self.p.max_recording_jobs
        attempts = {x.id: x.at for x in self.receipts if x.action == action}
        for job in self.jobs:
            if job.action == action:
                attempts.setdefault(job.id, job.created_at)
        last = max(attempts.values(), default=None)
        if last is not None and self.now - last < cooldown:
            return self.result("wait", ["The generation cooldown has not elapsed."], retry_at=last + cooldown, **common)
        recent = [at for at in attempts.values() if self.now - at < self.p.budget_window_hours]
        if len(recent) >= cap:
            retry = min(recent) + self.p.budget_window_hours if recent and cap else None
            return self.result("wait", ["The actor's generation budget is exhausted."], retry_at=retry, **common)
        identity = {"action": action, "save_id": self.s.save_id, "world_id": self.s.world_id,
                    "performer_id": self.s.performer_id, "composition_id": cid}
        if action == "compose_lyrics":
            identity.update(tradition=self.r.tradition, recipe_id=self.r.recipe_id,
                            topic_id=topic)
        else:
            identity["request"] = asdict(self.r)
        key = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if action == "compose_lyrics":
            brief = {**subject, "performer_id": self.s.performer_id, "tradition": self.r.tradition,
                     "factual_framing": ("A story this bard heard, not a verified fact or a witnessed event."
                                         if subject["evidence"] == "rumor" else "This bard's supplied direct observation; do not add unseen outcomes."),
                     "creative_license": "Wit, metaphor, satire and exaggerated attitude are welcome; do not invent corroboration, witnesses or factual outcomes.",
                     "knowledge_boundary": "Use only this selected actor-known subject. Repeated gossip is not independent confirmation."}
            return self.result(action, ["A salient, recent, uncovered actor-known subject needs a new composition."],
                               lyric_brief=brief, work_key=key, **common)
        brief = {"request": asdict(self.r), "composition_id": cid,
                 "reuse_existing_lyrics": bool(composition and self.r.mode == "lyrical"),
                 "omit_lyrics": self.r.mode != "lyrical",
                 "create_composition_on_success": composition is None}
        return self.result(action, ["No compatible playable recording exists; reuse the known composition." if composition
                                   else "Create a wordless/instrumental recording without requesting lyrics."],
                           recording_brief=brief, work_key=key, **common)

    def run(self) -> dict:
        if self.recording and self.p.selection == "cache_first":
            return self.play()
        deferred = None
        if self.subject and self.p.selection == "topical_when_salient":
            topical = [c for c in self.suitable.values() if c.topic_id == self.subject["topic_id"]]
            recorded = self.best_recording([r for r in self.recordings if r.composition_id in {c.id for c in topical}])
            if recorded:
                return self.play(["A matching recording already covers the salient actor-known topic; reuse it."], recorded)
            if topical:
                composition = min(topical, key=lambda c: (self.last_play(c.id), c.created_at, c.id))
                proposed = self.work("generate_recording", composition, self.subject)
            else:
                proposed = self.work("compose_lyrics", subject=self.subject)
            if proposed["action"] != "wait" or proposed["pending_job_id"]:
                return proposed
            deferred = proposed
        if self.recording:
            return self.play(["Use the eligible cached recording."] + (deferred["reasons"] if deferred else []))
        composition = min(self.suitable.values(), key=lambda c: (self.last_play(c.id), c.created_at, c.id), default=None)
        if composition:
            return self.work("generate_recording", composition=composition)
        if self.r.mode != "lyrical":
            return self.work("generate_recording")
        if self.subject:
            return deferred or self.work("compose_lyrics", subject=self.subject)
        relevant_job = next((job for job in self.jobs if job.request == self.r), None)
        if relevant_job:
            return self.result("wait", ["A relevant generation job is still pending."], pending_job_id=relevant_job.id)
        reasons = ["No nonrepeating known composition, compatible recording, or eligible fresh subject is available."]
        reasons.extend(dict.fromkeys(self.topic_diagnostics))
        return self.result("no_selection", reasons)


def plan(snapshot: Snapshot | dict) -> dict:
    """Return a JSON-serializable plan; never mutate the snapshot or execute work."""
    checked = Snapshot.from_dict(asdict(snapshot) if isinstance(snapshot, Snapshot) else snapshot)
    return _Planner(checked).run()
