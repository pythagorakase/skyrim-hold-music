"""Build an exact-name hold lookup from a trusted, locally audited record snapshot.

The --audit-module interface expects records.py from the MGO bard audit. It reads
winning records and localized names; no game plugin or asset is redistributed.
Use --records-json for a portable list with id/type/name/editor_id/parent fields.
"""
import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path

HOLDS = ('haafingar', 'eastmarch', 'whiterun', 'reach', 'falkreath',
         'rift', 'winterhold', 'pale', 'hjaalmarch')


def registry(records):
    by_id = {r['id']: r for r in records}
    roots = {region + 'holdlocation': region for region in HOLDS}

    def region_for(identifier):
        visited = set()
        while identifier in by_id and identifier not in visited:
            visited.add(identifier)
            row = by_id[identifier]
            region = roots.get(row.get('editor_id', '').casefold())
            if region:
                return region
            identifier = row.get('parent')
        return None

    candidates = defaultdict(set)
    for row in records:
        region = region_for(row['id'])
        for name in (row.get('name'), row.get('editor_id')):
            if name and not name.startswith('[unresolved text '):
                candidates[' '.join(name.casefold().split())].add(region)
    # Keep unknown homonyms as ambiguous rather than assigning a known hold.
    relevant = {name: values for name, values in candidates.items() if values != {None}}
    return {
        'version': 1,
        'scope': 'MGO RC4.1 experimental profile; winning LCTN parent chains and CELL location references',
        'locations': {name: next(iter(values)) if len(values) == 1 else None
                      for name, values in sorted(relevant.items())},
        'ambiguous_names': {name: sorted(value or 'unknown' for value in values)
                            for name, values in sorted(relevant.items()) if len(values) > 1},
    }


def audit_records(path):
    spec = importlib.util.spec_from_file_location('hold_music_location_audit', path)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    def stable(key):
        return f'{key[0]}|{key[1]:06x}' if key else None
    result = []
    for key, row in audit.R.items():
        if row['sig'] not in ('LCTN', 'CELL') or row['flags'] & 0x20:
            continue
        fields = audit.values(row)
        parent = fields.get(b'PNAM' if row['sig'] == 'LCTN' else b'XLCN')
        result.append({'id': stable(key), 'type': row['sig'], 'name': audit.ltext(row, b'FULL'),
                       'editor_id': audit.edid(key), 'parent': stable(audit.ref(row, parent)) if parent else None})
    hashes = [(name, item['sha256']) for name, item in sorted(audit.D['pluginmeta'].items())]
    provenance = {'profile': audit.PROFILE.name, 'record_count': len(result),
                  'plugin_hashes_sha256': hashlib.sha256(json.dumps(hashes).encode()).hexdigest(),
                  'audit_module_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    return result, provenance


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--audit-module', type=Path)
    source.add_argument('--records-json', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.audit_module:
        records, provenance = audit_records(args.audit_module)
    else:
        records = json.loads(args.records_json.read_text(encoding='utf-8'))
        provenance = {'records_json_sha256': hashlib.sha256(args.records_json.read_bytes()).hexdigest()}
    result = registry(records)
    result['provenance'] = provenance
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"Saved {len(result['locations'])} names; {len(result['ambiguous_names'])} ambiguous names use Nord fallback.")
