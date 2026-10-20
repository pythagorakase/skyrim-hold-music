"""Read-only provenance and listening-study index for the local workshop.

Study files supply IDs, never filesystem paths to serve or delete. Reviews stay
bound to the exact takes and current recipe, so a changed prompt cannot inherit
an earlier listening decision.
"""

import hashlib
import json
from pathlib import Path
import re


TAKE_ID = re.compile(r"[a-f0-9]{32}")
SLUG = re.compile(r"[a-zA-Z0-9_-]{1,100}")
# Bump when the shared prompt assembly contract changes.
PROMPT_CONTRACT = "workshop-prompt-v2"
RECIPE_FIELDS = (
    "reference", "reference_focus", "reference_focus_monophonic", "core", "dialect", "tint", "voice", "lute",
    "flute", "drum", "lute_instrumental", "core_monophonic", "drum_instrumental",
    "drum_reference", "audition_race", "audition_region", "audition_casting",
    "ensemble_clause", "ensemble_roles", "required_vocal_technique", "core_instrumental",
    "core_instrumental_monophonic", "flute_instrumental",
)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def recipe_fingerprint(profile, palette):
    recipe = {key: profile.get(key) for key in RECIPE_FIELDS}
    recipe["instruments"] = {key: profile.get("workshop", {}).get(key)
                             for key in ("plucked", "flute", "drum")}
    recipe["instrument_family_rules"] = profile.get("workshop", {}).get("family_rules", {})
    recipe["admission"] = {key: profile.get("audition", {}).get(key)
                           for key in ("revision", "arrangement", "vocal_mode")}
    recipe["contexts"] = {key: palette.get(key) for key in
                           ("auditionVoices", "auditionRegions", "auditionRaces")}
    return digest({"contract": PROMPT_CONTRACT, "recipe": recipe})


def read_json(path, limit=2_000_000):
    """Ignore unsafe or incomplete local evidence instead of breaking the UI."""
    path = Path(path)
    try:
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            return None
        if path.stat().st_size > limit:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None


def palette_profiles(palette):
    return {p["id"]: p for group in ("finalists", "existing", "comparisons")
            for p in palette.get(group, [])}


def load_studies(root):
    studies = []
    base = Path(root) / "local" / "listening-tests"
    if base.is_symlink():
        return studies
    for path in sorted(base.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        if not SLUG.fullmatch(path.parent.name):
            continue
        manifest = read_json(path)
        if not isinstance(manifest, dict) or not isinstance(manifest.get("corpus"), dict):
            continue
        if not isinstance(manifest.get("trials"), list):
            continue
        studies.append((path.parent, manifest))
    return studies


def snapshot_fingerprints(studies):
    # Legacy snapshots omit the assembly-contract version. Changed recipe fields
    # (including v2 family rules/revision) invalidate them, but a future contract-
    # only change must not assume this reconstruction proves the old assembly.
    result = {}
    for directory, manifest in studies:
        palette = read_json(directory / "palette-snapshot.json")
        if not isinstance(palette, dict):
            continue
        profiles = palette_profiles(palette)
        for sample in manifest["corpus"].values():
            if not isinstance(sample, dict):
                continue
            identifier, profile = sample.get("take_id"), profiles.get(sample.get("profile_id"))
            if isinstance(identifier, str) and TAKE_ID.fullmatch(identifier) and profile:
                result.setdefault(identifier, recipe_fingerprint(profile, palette))
    return result


def prompt_status(take, profiles, palette, snapshots):
    profile = profiles.get(take["profile_id"])
    result = {"current_revision": (profile or {}).get("audition", {}).get("revision")}
    if not profile or profile.get("audition", {}).get("stage") == "deferred":
        return {**result, "state": "deferred", "label": "Deferred style",
                "reason": "This style is outside the provisional baseline. Its original prompt is preserved."}
    admission = profile.get("audition", {})
    fingerprint = take.get("recipe_fingerprint") or snapshots.get(take["id"])
    if fingerprint:
        if fingerprint != recipe_fingerprint(profile, palette):
            return {**result, "state": "obsolete", "label": "Obsolete prompt",
                    "reason": "The saved recipe differs from the current recipe."}
        return {**result, "state": "current", "label": "Current prompt",
                "reason": "Matches the current recipe. Performer choices and supplied lyrics may vary.",
                "evidence": "Saved fingerprint" if take.get("recipe_fingerprint") else "Saved batch recipe snapshot"}
    if take.get("recipe_revision") and take["recipe_revision"] != admission.get("revision"):
        return {**result, "state": "obsolete", "label": "Obsolete prompt",
                "reason": "Generated under an earlier recipe revision: " + take["recipe_revision"] + "."}
    if take.get("recipe_revision"):
        return {**result, "state": "unverified", "label": "Revision matches · unverified",
                "reason": "The revision matches, but no recipe fingerprint was saved. Compare the exact prompt."}
    return {**result, "state": "unknown", "label": "Prompt version unknown",
            "reason": "This older take has no recorded recipe version. Its exact prompt is still available."}


def comparison_samples(corpus, trials, profile_ids, audio_ids, kind):
    """Keep the batch's full sample set, including slots whose generation failed.

    Repeatability trials declare the planned replicates. Never replace a missing
    batch sample with a newer library take or borrow one from another study.
    """
    groups = []
    for profile_id in dict.fromkeys(profile_ids):
        selected = list(audio_ids) if kind == "repeatability" else []
        if kind == "neighbor":
            selected.extend(a for a, s in corpus.items()
                            if isinstance(s, dict) and s.get("profile_id") == profile_id)
            for trial in trials:
                if not isinstance(trial, dict) or trial.get("kind") != "repeatability":
                    continue
                for audio_id in trial.get("audio_ids", []):
                    if not isinstance(audio_id, str) or not SLUG.fullmatch(audio_id):
                        continue
                    sample = corpus.get(audio_id, {})
                    if isinstance(sample, dict) and (sample.get("profile_id") or audio_id.rsplit("_", 1)[0]) == profile_id:
                        selected.append(audio_id)
        samples = []
        for audio_id in set(selected):
            if not isinstance(audio_id, str) or not SLUG.fullmatch(audio_id):
                continue
            sample = corpus.get(audio_id, {})
            if not isinstance(sample, dict):
                continue
            identifier = sample.get("take_id")
            if identifier is not None and (not isinstance(identifier, str) or not TAKE_ID.fullmatch(identifier)):
                continue
            replicate = sample.get("replicate")
            if type(replicate) is not int or replicate < 1:
                suffix = audio_id.rsplit("_", 1)[-1]
                replicate = int(suffix) if suffix.isdigit() else 1
            samples.append({"audio_id": audio_id, "take_id": identifier, "replicate": replicate,
                            "lyric_id": sample.get("lyric_id"), "vocal_mode": sample.get("vocal_mode")})
        samples.sort(key=(lambda s: selected.index(s["audio_id"])) if kind == "repeatability"
                     else (lambda s: (s["replicate"], s["audio_id"])))
        groups.append({"profile_id": profile_id, "samples": samples})
    return groups


def study_queue(studies, takes, profiles, palette, reviews):
    """Show the latest pair study; reversed/identical AI controls aren't human chores."""
    studies = [(d, m) for d, m in studies if any(isinstance(t, dict) and t.get("kind") in ("neighbor", "repeatability") for t in m["trials"])]
    if not studies:
        return {"study": None, "comparisons": []}
    directory, manifest = studies[0]
    corpus = manifest["corpus"]
    flags = read_json(directory / "review-flags.json") or []
    comparisons, seen = [], set()
    trials = manifest["trials"] + manifest.get("excluded_conditions", [])
    for trial in sorted(trials, key=lambda t: str(t.get("id", "")) if isinstance(t, dict) else ""):
        if not isinstance(trial, dict) or trial.get("kind") not in ("neighbor", "repeatability"):
            continue
        tid, audio_ids = trial.get("id"), trial.get("audio_ids")
        if not isinstance(tid, str) or not SLUG.fullmatch(tid) or not isinstance(audio_ids, list) or len(audio_ids) != 2:
            continue
        if not all(isinstance(a, str) and SLUG.fullmatch(a) for a in audio_ids):
            continue
        samples = [corpus.get(a, {}) for a in audio_ids]
        ids = [s.get("take_id") if isinstance(s, dict) else None for s in samples]
        if any(i is not None and (not isinstance(i, str) or not TAKE_ID.fullmatch(i)) for i in ids):
            continue
        pair_key = tuple(sorted(audio_ids))
        if pair_key in seen:
            continue
        seen.add(pair_key)
        identifier = directory.name + ":" + tid
        pair = [takes.get(i) for i in ids]
        profile_ids = [s.get("profile_id") or a.rsplit("_", 1)[0] for a, s in zip(audio_ids, samples)]
        reasons, judgments = [], []
        for model in manifest.get("models", []):
            if not isinstance(model, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}", model):
                continue
            judgment = read_json(directory / model / "requests" / (tid + "__" + model) / "judgment.json")
            if isinstance(judgment, dict) and isinstance(judgment.get("pair"), dict):
                judgments.append({"model": model, "pair": judgment["pair"], "clips": judgment.get("clips", [])})
        relationships = {j["pair"].get("relationship") for j in judgments}
        if len(relationships) > 1:
            reasons.append("The judges disagree about whether these sound like different styles.")
        if any(isinstance(f, dict) and f.get("trial") == tid for f in flags):
            reasons.append("The automated review contains conflicting or invalid evidence.")
        if len(judgments) > 1 and any(
            len({j["clips"][n].get("observed_vocal_mode") for j in judgments if len(j["clips"]) > n}) > 1
            for n in (0, 1)
        ):
            reasons.append("The judges disagree about whether a recording contains lyrics or instruments alone.")
        kind = trial["kind"]
        if not reasons:
            reasons.append("Check that both takes retain the same musical identity." if kind == "repeatability"
                           else "Check whether the musical difference survives without relying on the words.")
        pair_version = digest({"ids": ids, "prompts": [p["prompt"] if p else None for p in pair],
                               "recipes": [recipe_fingerprint(profiles[p], palette) if p in profiles else None for p in profile_ids]})
        groups = comparison_samples(corpus, trials, profile_ids, audio_ids, kind)
        evidence = [s for group in groups for s in group["samples"]]
        evidence_ids = [s["take_id"] for s in evidence]
        evidence_takes = [takes.get(i) for i in evidence_ids]
        # Preserve existing repeatability reviews; neighbor reviews now cover the
        # entire batch sample set rather than a single judge-request pair.
        version = pair_version if kind == "repeatability" else digest({
            "scope": "all_style_takes_v1", "groups": groups,
            "prompts": [p["prompt"] if p else None for p in evidence_takes],
            "recipes": [recipe_fingerprint(profiles[p], palette) if p in profiles else None for p in profile_ids],
        })
        stored = reviews.get(identifier)
        review = stored if isinstance(stored, dict) and stored.get("version") == version else None
        previous_scope = "pair" if isinstance(stored, dict) and stored.get("version") == pair_version and kind == "neighbor" else "earlier"
        missing = [s["audio_id"] for s, p in zip(evidence, evidence_takes) if not p]
        stale = any(p and p["prompt_status"]["state"] in ("obsolete", "deferred") for p in evidence_takes)
        uncertain = review and (review.get("outcome") == "uncertain" or "uncertain" in review.get("consistency", {}).values())
        state = "waiting" if missing else "obsolete" if stale else "revisit" if uncertain else "reviewed" if review else "pending"
        comparisons.append({"id": identifier, "title": trial.get("title", tid), "kind": kind,
                            "audio_ids": audio_ids, "take_ids": ids, "profile_ids": profile_ids,
                            "groups": groups, "evidence_take_ids": evidence_ids,
                            "review_scope": "all_style_takes" if kind == "neighbor" else "repeatability",
                            "version": version, "state": state, "reasons": reasons,
                            "priority": 0 if any("judges disagree" in r or "automated review" in r for r in reasons) else 1,
                            "review": review, "previous_review": stored if not review else None,
                            "previous_review_scope": previous_scope,
                            "missing": missing, "judgments": judgments})
    comparisons.sort(key=lambda c: (c["priority"], c["kind"] != "neighbor", c["id"]))
    return {"study": directory.name, "comparisons": comparisons}
