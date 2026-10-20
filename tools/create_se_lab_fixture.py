#!/usr/bin/env python3
"""Create a new, synthetic eight-second library in the isolated SE lab only."""
from __future__ import annotations

import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hold_music.library import Library
from hold_music.runtime_contract import manifest_runtime_selection_errors, runtime_identity_key
from hold_music.promotion import _no_alias

LAB = Path(r"C:\MGO\HoldMusic-SE-Lab")


def main():
    _no_alias(LAB)
    destination = _no_alias(LAB / "MO2/mods/Hold Music Lab Data")
    source = _no_alias(LAB / "build/synthetic-audio-v1")
    control = _no_alias(LAB / "MO2/overwrite/SKSE/Plugins/StorageUtilData/HoldMusicSELab/control.json")
    runtime = _no_alias(LAB / "MO2/overwrite/SKSE/Plugins/StorageUtilData/HoldMusic")
    runtime_seeds = {
        _no_alias(runtime / "trace.json"): dict(version=1, entries=[]),
        _no_alias(runtime / "receipts.json"): dict(version=1, performances=[]),
    }
    bootstrap = _no_alias(LAB / "checkpoints/bootstrap.json")
    if not bootstrap.is_file():
        raise SystemExit("Missing isolated lab bootstrap receipt.")
    if source.exists() or destination.exists():
        raise SystemExit("Fixture already exists; preserve it and its runtime history.")
    if control.exists():
        raise SystemExit("Control already exists; refusing to overwrite.")
    if any(path.exists() for path in runtime_seeds):
        raise SystemExit("Runtime history already exists; refusing to overwrite.")
    source.mkdir()
    wav = source / "synthetic-pluck.wav"
    rate = 44100
    frames = array.array("h")
    # A quiet repeated decaying tone, explicitly synthetic; never a style audition.
    for index in range(rate * 8):
        t = index / rate
        phase = t % 1.0
        envelope = (1.0 - math.exp(-phase * 150.0)) * math.exp(-phase * 7.0)
        fade = min(1.0, (8.0 - t) * 20)
        sample = envelope * fade * (math.sin(2 * math.pi * 220 * t)
                                   + .25 * math.sin(2 * math.pi * 440 * t))
        frames.append(round(sample * 1800))
    if sys.byteorder != "little":
        frames.byteswap()
    with wave.open(str(wav), "wb") as output:
        output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        output.writeframes(frames.tobytes())
    identity = dict(performer_id="sven", region="whiterun", mode="instrumental",
                    recipe_id="lab/synthetic-pluck", recipe_revision="lab-v1",
                    model_id="deterministic-pcm-fixture", instrument_family="plucked_string",
                    instrument_name="synthetic plucked-string test signal",
                    arrangement="solo_lute", voice="none")
    identity["identity_key"] = runtime_identity_key(identity)
    library = Library(source / "library")
    row = library.add_recording(
        wav, gender="male", composition_id="lab:synthetic-pluck-v1",
        source=dict(kind="import", path_or_request_id="synthetic-pluck.wav",
                    sha256=hashlib.sha256(wav.read_bytes()).hexdigest()),
        provenance=dict(kind="synthetic_test_fixture", musical_style_validation=False),
        **identity)
    manifest = library.load().manifest
    manifest["runtime_selection"] = dict(version=1, contracts=[identity])
    (library.root / "library.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    errors = library.validate() + manifest_runtime_selection_errors(manifest, required=True)
    if errors:
        raise SystemExit("; ".join(errors))
    storage = destination / "SKSE/Plugins/StorageUtilData/HoldMusic"
    storage.mkdir(parents=True)
    audio = destination / "Sound/fx/holdmusic"
    audio.mkdir(parents=True)
    shutil.copy2(library.root / "library.json", storage / "library.json")
    shutil.copy2(library.root / row["file"], audio / row["file"])
    settings = destination / "MCM/Settings/HoldMusic.ini"
    settings.parent.mkdir(parents=True)
    settings.write_text("[General]\nbEnabled=1\niInstrumentalPercent=100\niSessionCap=1\n"
                        "sWorldId=hold-music-se-lab\n", encoding="ascii")
    _no_alias(runtime).mkdir(parents=True, exist_ok=True)
    for path, value in runtime_seeds.items():
        with _no_alias(path).open("x", encoding="utf-8") as output:
            output.write(json.dumps(value, indent=2) + "\n")
    _no_alias(control)
    control.parent.mkdir(parents=True, exist_ok=True)
    with control.open("x", encoding="utf-8") as output:
        output.write(json.dumps(dict(version=1, enabled=True, world_id="hold-music-se-lab"),
                                indent=2) + "\n")
    print(json.dumps(dict(status="fixture_created", duration_seconds=8,
                          library_errors=errors, paid_calls=0, mod=str(destination)), indent=2))


if __name__ == "__main__":
    main()
