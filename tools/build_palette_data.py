#!/usr/bin/env python3
"""Extract the editorial palette from the repository's Markdown documents.

The snapshot date is an explicit editorial value, never the current clock or
file modification time, so unchanged inputs produce byte-identical output.
"""
from __future__ import annotations

import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPEC = REPO_ROOT / "docs" / "bard-regional-music-spec.md"
DEFAULT_BANK = REPO_ROOT / "docs" / "bard-musical-traditions-exploration.md"
DEFAULT_OUTPUT = REPO_ROOT / "dashboard" / "palette-data.json"
DEFAULT_DATE = "2026-10-08"


class BuildError(RuntimeError):
    """A source document or dependency needs attention."""


def clean(value):
    return value.replace("**", "").replace("`", "").strip()


def section(source, heading):
    marker = f"## {heading}\n"
    if marker not in source:
        raise BuildError(f"Missing Markdown section: {heading}")
    return source.split(marker, 1)[1].split("\n## ", 1)[0]


def rows(source):
    result = []
    for line in source.splitlines():
        if not line.startswith("|"):
            continue
        cells = [clean(value) for value in line.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r"[-: ]+", value) for value in cells):
            continue
        result.append(cells)
    return result


def documents(source):
    try:
        import yaml
    except ImportError as exc:
        raise BuildError(
            "PyYAML is required. From the repository root, run "
            "python -m pip install -r requirements.txt with the same Python "
            "interpreter used for this build."
        ) from exc
    result = {}
    for number, block in enumerate(re.findall(r"```yaml\s*\n(.*?)\n```", source, re.S), 1):
        try:
            parsed = yaml.safe_load(block)
        except yaml.YAMLError as exc:
            raise BuildError(f"Invalid YAML in fenced block {number}: {exc}") from exc
        if not isinstance(parsed, dict):
            raise BuildError(f"YAML block {number} must contain a mapping.")
        for key, value in parsed.items():
            if key in result:
                raise BuildError(f"Repeated YAML section: {key}")
            result[key] = value
    for key in ("cultures", "holds", "traditions"):
        if not isinstance(result.get(key), dict):
            raise BuildError(f"Missing YAML mapping: {key}")
    if "audition_context" in result and not isinstance(result["audition_context"], str):
        raise BuildError("audition_context must be text.")
    for key in ("audition_races", "audition_regions", "audition_voices"):
        if not isinstance(result.get(key), dict) or not all(isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in result[key].items()):
            raise BuildError(f"{key} must map IDs to nonempty text.")
    return result


def snapshot_date(value):
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use an ISO snapshot date: YYYY-MM-DD.") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("Use an ISO snapshot date: YYYY-MM-DD.")
    return value


NAMES = {
    "nord": ("Nord", "Nord ballads"),
    "imperial": ("Imperial", "Imperial expressive solo song"),
    "imperial_vernacular": ("Imperial", "Cyrodiil vernacular"),
    "breton_court": ("Breton", "Breton court song"),
    "breton_folk": ("Breton", "Breton folk lament"),
    "redguard": ("Redguard", "Redguard articulated cycles"),
    "dunmer": ("Dunmer", "Dunmer modal lament"),
    "altmer": ("Altmer", "Altmer counterpoint"),
    "khajiit": ("Khajiit", "Khajiit unfolding drone"),
    "argonian": ("Argonian", "Argonian interlocking cells"),
    "haafingar": ("Nord", "Haafingar / Solitude"),
    "eastmarch": ("Nord", "Eastmarch / Windhelm"),
    "whiterun": ("Nord", "Whiterun"),
    "reach": ("Nord", "The Reach / Markarth"),
    "falkreath": ("Nord", "Falkreath"),
    "rift": ("Nord", "The Rift / Riften"),
    "winterhold": ("Nord", "Winterhold"),
    "pale": ("Nord", "The Pale / Dawnstar"),
    "hjaalmarch": ("Nord", "Hjaalmarch / Morthal"),
}

FINALIST_IDS = {
    "Resonant Name-Songs": "orc_resonant_names",
    "Resonant Name-Songs · throat singing": "orc_resonant_names",
    "Seven-Step Oath-Songs": "orc_seven_step",
    "Close-Circle Songs": "orc_close_circle",
    "Leaping tales": "bosmer_leaping_tales",
    "Hunting-call airs": "bosmer_hunting_calls",
    "Spinner's tales": "bosmer_spinners_tales",
}

ARRANGEMENTS = {"lute_voice", "lute", "flute", "flute_voice", "drum", "drum_voice", "voice", "trio"}

COMPARISONS = {
    "orc_resonant_names": (
        "Eastmarch declamation; Khajiit drone; sparse northern song",
        "A visibly moving upper overtone melody over one steady vocal fundamental is the defining feature. Ordinary low chanting is not enough. Keep the tempo and tonal center settled; its instrumental arrangement is an explicitly weaker reduction.",
    ),
    "orc_seven_step": (
        "Argonian work cycles; Nord communal song; Bosmer Leaping tales",
        "Maintain deliberate 2+2+3 grouping, firm shared attacks and decisive rests. Argonian cells overlap continuously; Bosmer leaps through quicker 3+2 groups with light interrupted answers.",
    ),
    "orc_close_circle": (
        "Altmer counterpoint; Nord open-fifth song",
        "Compact chord blocks change and stop together, unlike Altmer independently moving lines. The full vocal form needs the three listed singers. Solo flute or drum omits the chordal core; one lute may supply the explicit reduction.",
    ),
    "bosmer_leaping_tales": (
        "Orsimer Seven-Step; Falkreath five-beat lament; Reach dance",
        "Current audition meter is five pulses grouped 3+2. Quick wide leaps, dry attacks and sudden gaps distinguish it from Orsimer 2+2+3, Falkreath slow descending cells and Reach connected ornamental flow.",
    ),
    "bosmer_hunting_calls": (
        "Winterhold circular vocables; Pale exposed calls; Argonian cells",
        "Use brief precise calls in separated registers, each followed by a complete gap and clean ending. Avoid a continuous northern melodic circle, long rocking Pale phrases or Argonian overlapping texture.",
    ),
    "bosmer_spinners_tales": (
        "Eastmarch narrative declamation; Altmer formal development",
        "One conversational voice changes character through register and pacing around a recurring three-note tag. Keep the line agile and discontinuous; instrumental reductions retain the tag and phrase structure without implying speech or extra characters.",
    ),
}


def build_dataset(spec_path=DEFAULT_SPEC, bank_path=DEFAULT_BANK, updated_at=DEFAULT_DATE):
    """Return data and source hashes without writing files."""
    spec_text = Path(spec_path).read_text(encoding="utf-8-sig")
    bank_text = Path(bank_path).read_text(encoding="utf-8-sig")
    doc = documents(spec_text)
    finalists = []
    for row in rows(section(spec_text, "Orsimer and Bosmer finalists"))[1:]:
        if len(row) != 5 or row[0] not in ("Orsimer", "Bosmer"):
            continue
        culture, name, audible, mood, role = row
        if name not in FINALIST_IDS:
            raise BuildError(f"Add an explicit FINALIST_IDS mapping for finalist {name!r}.")
        ident = FINALIST_IDS[name]
        if ident not in doc["traditions"]:
            raise BuildError(f"Missing tradition YAML: {ident}")
        item = {"id": ident, "culture": culture, "name": name,
                "mood": mood, "role": role, **doc["traditions"][ident]}
        item["neighbor"], item["boundary"] = COMPARISONS[ident]
        finalists.append(item)

    existing = []
    for source, kind in (("cultures", "culture"), ("holds", "region")):
        for ident, profile in doc[source].items():
            if ident in ("orc", "bosmer"):
                continue
            core = profile.get("core") or profile.get("dialect")
            if not core:
                raise BuildError(f"Profile {ident} needs a core or dialect.")
            if ident not in NAMES:
                raise BuildError(f"Add a culture/display-name NAMES mapping for {ident!r}.")
            culture, name = NAMES[ident]
            instrument_defaults = (
                {field: doc["cultures"]["nord"][field]
                 for field in ("voice", "lute", "flute", "drum")}
                if kind == "region" else {}
            )
            existing.append({"id": ident, "kind": kind, "culture": culture,
                             "name": name, **instrument_defaults, **profile, "core": core})

    ideas = []
    for row in rows(section(bank_text, "Orsimer candidate bank"))[1:]:
        if len(row) != 3:
            raise BuildError(f"Expected three columns in Orsimer candidate row: {row}")
        numbered_name, full, verdict = row
        try:
            number, name = numbered_name.split(". ", 1)
            description, mood = full.rstrip(".").rsplit(". ", 1)
            ident = f"orsimer_idea_{int(number):02}"
        except ValueError as exc:
            raise BuildError(f"Cannot parse Orsimer candidate row: {row}") from exc
        item = {"id": ident, "culture": "Orsimer", "name": name,
                "description": description + ".", "mood": mood, "verdict": verdict}
        if name in FINALIST_IDS:
            item["finalistId"] = FINALIST_IDS[name]
        ideas.append(item)
    for row in rows(section(bank_text, "Bosmer candidate bank"))[1:]:
        if len(row) != 5:
            raise BuildError(f"Expected five columns in Bosmer candidate row: {row}")
        number, name, description, mood, verdict = row
        if name == "Leaping tales":
            description = (
                "Historical initial proposal: " + description +
                " Current audition correction: five pulses grouped 3+2 replace "
                "the original seven pulses; use the current finalist fragments."
            )
            verdict = (
                "Finalist; first candidate to audition. Original 'default' wording "
                "is historical; the production core remains unset. Current meter: 3+2."
            )
        try:
            ident = f"bosmer_idea_{int(number):02}"
        except ValueError as exc:
            raise BuildError(f"Invalid Bosmer candidate number: {number}") from exc
        item = {"id": ident, "culture": "Bosmer", "name": name,
                "description": description, "mood": mood, "verdict": verdict}
        if name in FINALIST_IDS:
            item["finalistId"] = FINALIST_IDS[name]
        ideas.append(item)

    boundaries = []
    for row in rows(section(spec_text, "Palette boundaries and alternatives"))[1:]:
        if len(row) != 3:
            raise BuildError(f"Expected three columns in boundary row: {row}")
        boundaries.append(dict(zip(("pair", "boundary", "reserve"), row)))
    result = {"version": 1, "updatedAt": updated_at,
              "auditionContext": doc.get("audition_context", "").strip(),
              "auditionRaces": doc["audition_races"], "auditionRegions": doc["audition_regions"],
              "auditionVoices": doc["audition_voices"], "finalists": finalists,
              "existing": existing, "ideas": ideas, "boundaries": boundaries}
    policies = doc.get("workshop_arrangements", {})
    omissions = doc.get("workshop_omissions", {})
    expected = {item["id"] for item in finalists + existing}
    if not isinstance(policies, dict) or set(policies) != expected:
        raise BuildError("workshop_arrangements must cover exactly the active palette profiles.")
    if not isinstance(omissions, dict) or set(omissions) != ARRANGEMENTS:
        raise BuildError("workshop_omissions must explain every arrangement family.")
    for item in finalists + existing:
        policy = policies[item["id"]]
        if not isinstance(policy, dict):
            raise BuildError(f"Profile {item['id']} needs a workshop arrangement mapping.")
        allowed = policy.get("allowed")
        if not isinstance(allowed, list) or not allowed or any(not isinstance(key, str) or key not in ARRANGEMENTS for key in allowed) or len(set(allowed)) != len(allowed):
            raise BuildError(f"Profile {item['id']} needs a unique list of supported arrangements.")
        if item["id"] in ("khajiit", "argonian") and set(allowed) - {"lute", "flute", "drum"}:
            raise BuildError(f"Profile {item['id']} is instrumental only in the workshop.")
        if "trio" in allowed and not (isinstance(item.get("ensemble_roles"), list) and len(item["ensemble_roles"]) == 3 and item.get("ensemble_clause")):
            raise BuildError(f"Profile {item['id']} has no defined three-voice arrangement.")
        instruments = {"plucked": policy.get("plucked"), "flute": policy.get("flute", "flute"), "drum": policy.get("drum", "hand drum")}
        if any(not isinstance(value, str) or not value.strip() for value in instruments.values()):
            raise BuildError(f"Profile {item['id']} needs instrument names.")
        if not isinstance(policy.get("omitted", {}), dict) or not isinstance(policy.get("note", ""), str):
            raise BuildError(f"Profile {item['id']} needs text notes and a mapping of omission reasons.")
        reasons = {**omissions, **policy.get("omitted", {})}
        omitted = {key: reasons[key] for key in sorted(ARRANGEMENTS - set(allowed))}
        if any(not isinstance(reason, str) or not reason.strip() for reason in omitted.values()):
            raise BuildError(f"Profile {item['id']} needs explanations for omitted arrangements.")
        item["workshop"] = {**instruments, "allowed": allowed, "omitted": omitted, "note": policy.get("note", "")}
    for item in finalists + existing:
        item.setdefault("audition_race", "orc" if item["culture"] == "Orsimer" else item["culture"].lower())
        item.setdefault("audition_region", item["id"] if item.get("kind") == "region" else "skyrim")
        if item["audition_race"] not in doc["audition_races"] or item["audition_region"] not in doc["audition_regions"]:
            raise BuildError(f"Profile {item['id']} needs a known audition race and region.")
    seen = set()
    for key in ("finalists", "existing", "ideas"):
        if not result[key]:
            raise BuildError(f"No {key} were extracted; check the source headings and tables.")
        for item in result[key]:
            if item["id"] in seen:
                raise BuildError(f"Duplicate dashboard ID: {item['id']}")
            seen.add(item["id"])
            if "audition_casting" in item and not isinstance(item["audition_casting"], str):
                raise BuildError(f"Profile {item['id']} audition_casting must be text.")
    finalist_ids = {item["id"] for item in finalists}
    for item in finalists + existing:
        if not isinstance(item.get("reference"), str) or not item["reference"].strip():
            raise BuildError(f"Profile {item['id']} needs an explicit musical style reference.")
        for field in ("reference_focus", "reference_focus_monophonic", "drum_reference"):
            if field in item and (not isinstance(item[field], str) or not item[field].strip()):
                raise BuildError(f"Profile {item['id']} {field} must be nonempty text.")
    for item in ideas:
        if "finalistId" in item and item["finalistId"] not in finalist_ids:
            raise BuildError(f"Idea links to an absent finalist: {item['finalistId']}")
    for item in finalists:
        required = ("core", "voice", "lute", "flute", "drum", "neighbor", "boundary")
        missing = [key for key in required if not item.get(key)]
        if missing:
            raise BuildError(f"Finalist {item['id']} lacks: {', '.join(missing)}")
    provenance = {
        "spec_sha256": hashlib.sha256(spec_text.encode("utf-8")).hexdigest(),
        "bank_sha256": hashlib.sha256(bank_text.encode("utf-8")).hexdigest(),
    }
    return result, provenance


def write_dataset(data, output=DEFAULT_OUTPUT):
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return path


def parser():
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--spec", type=Path, default=DEFAULT_SPEC,
                     help="source spec (default: docs/bard-regional-music-spec.md)")
    cli.add_argument("--bank", type=Path, default=DEFAULT_BANK,
                     help="idea bank (default: docs/bard-musical-traditions-exploration.md)")
    cli.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                     help="JSON destination (default: dashboard/palette-data.json)")
    cli.add_argument("--date", type=snapshot_date, default=DEFAULT_DATE,
                     help=f"editorial snapshot date, not build time (default: {DEFAULT_DATE})")
    return cli


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    try:
        data, provenance = build_dataset(args.spec, args.bank, args.date)
        output = write_dataset(data, args.output)
    except (BuildError, OSError, KeyError, TypeError) as exc:
        cli.exit(1, f"Palette build failed: {exc}\n")
    print(json.dumps({"output": str(output), "date": data["updatedAt"],
                      "counts": {key: len(data[key]) for key in ("finalists", "existing", "ideas", "boundaries")},
                      **provenance}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
