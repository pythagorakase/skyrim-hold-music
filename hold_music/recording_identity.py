"""Recording compatibility metadata, independent of providers and the game.

The version fields are an optional group so old manifests remain readable.
Absence means unknown; readers must never fill it from today's musical recipe.
Arrangement names describe the visible animation, not a literal instrument.
"""
from __future__ import annotations

VERSION_FIELDS = ("recipe_revision", "instrument_family", "instrument_name")
CONTRACT_FIELDS = ("recipe_id", "recipe_revision", "model_id", "instrument_family",
                   "instrument_name", "arrangement", "mode", "voice")


def identity_errors(value):
    """Check the optional identity extension without upgrading legacy metadata."""
    values = [value.get(key) for key in VERSION_FIELDS]
    if all(item is None for item in values):
        return []
    errors = []
    for key in (*VERSION_FIELDS, "arrangement", "voice"):
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            errors.append(f"versioned recording identity requires nonempty {key}")
    return errors


def recording_request(row):
    """Adapt a manifest row without guessing its missing sound sources.

    Legacy instrumental mode proves absence of voice, but a performer's gender
    alone does not identify a sung voice or a visible instrument arrangement.
    """
    mode = "lyrical" if row["mode"] == "vocal" else row["mode"]
    return dict(
        tradition=row["region"], mode=mode,
        arrangement=row.get("arrangement", "unknown"),
        voice=row.get("voice", "none" if mode == "instrumental" else "unknown"),
        recipe_id=row["recipe_id"], model_id=row["model_id"],
        **{key: row.get(key) for key in VERSION_FIELDS},
    )
