"""Derive the JsonUtil registry from the validated authored registry (stdlib)."""
import argparse
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from hold_music.registry import DEFAULT_PATH, load_registry

OUTPUT = REPO / 'game_package/src/SKSE/Plugins/HoldMusic/registry.json'


def derive_registry(source=DEFAULT_PATH):
    performers = []
    for row in load_registry(source).performers:
        form = row['form']
        performers.append(dict(
            id=row['id'], name=row['name'],
            form=None if form is None else dict(plugin=form['plugin'], id=int(form['id'], 16)),
            region=row['region'], venue=row['venue'], instrument=row['instrument'],
            gender=row['gender'], traditions=list(row['traditions'])))
    return dict(schema_version=2, performers=performers)


def build_registry(source=DEFAULT_PATH, output=OUTPUT, *, check=False):
    expected = (json.dumps(derive_registry(source), indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    output = Path(output)
    if check:
        if not output.is_file() or output.read_bytes() != expected:
            raise ValueError('Game registry is stale; run python -B game_package/tools/build_registry.py and review the derived file')
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(expected)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail instead of writing when the committed derivation differs')
    args = parser.parse_args()
    build_registry(check=args.check)
