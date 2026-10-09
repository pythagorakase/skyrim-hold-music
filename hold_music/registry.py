"""Authored performers, independent of SkyrimNet's runtime bard predicate."""
from __future__ import annotations

import json
from pathlib import Path
import re

REGIONS = frozenset({'haafingar', 'eastmarch', 'whiterun', 'reach', 'falkreath',
                     'rift', 'winterhold', 'pale', 'hjaalmarch'})
DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'game_adapter/data/performers.json'


def _form_id(value):
    if isinstance(value, str) and re.fullmatch(r'(?:0[xX])?[0-9a-fA-F]{1,8}', value):
        value = int(value, 16)
    if type(value) is not int or not 0 < value <= 0xFFFFFF:
        raise ValueError('form id must be a nonzero plugin-local hex id (no load-order prefix)')
    return value


class Registry:
    def __init__(self, data):
        if not isinstance(data, dict) or type(data.get('version')) is not int or data['version'] != 1:
            raise ValueError('registry version must be 1')
        if not isinstance(data.get('scope'), str) or not data['scope'].strip():
            raise ValueError('registry scope must be nonempty text')
        rows = data.get('performers')
        if not isinstance(rows, list):
            raise ValueError('performers must be a list')
        self.performers = rows
        self.scope = data['scope']
        self._names, self._forms = {}, {}
        ids = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('performer must be an object')
            for field in ('id', 'name', 'source'):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    raise ValueError(f'{field} must be nonempty text')
            if row['id'].casefold() in ids:
                raise ValueError(f"duplicate performer id: {row['id']}")
            ids.add(row['id'].casefold())
            if row['name'].casefold() in self._names:
                raise ValueError(f"duplicate performer name: {row['name']}")
            if 'region' not in row or (row['region'] is not None and
                                      (not isinstance(row['region'], str) or row['region'] not in REGIONS)):
                raise ValueError('region must be a known hold or null')
            if 'venue' not in row or (row['venue'] is not None and
                                     (not isinstance(row['venue'], str) or not row['venue'].strip())):
                raise ValueError('venue must be nonempty text or null')
            if row.get('gender') not in ('male', 'female'):
                raise ValueError('gender must be male or female')
            if row.get('instrument') not in ('lute', 'flute', 'drum', 'voice'):
                raise ValueError('instrument must be lute, flute, drum, or voice')
            if not isinstance(row.get('notes'), str):
                raise ValueError('notes must be text')
            traditions = row.get('traditions')
            if not isinstance(traditions, list) or any(not isinstance(x, str) or not x.strip() for x in traditions):
                raise ValueError('traditions must be a list of ids')
            if len(set(traditions)) != len(traditions):
                raise ValueError('duplicate tradition')
            if 'form' not in row:
                raise ValueError('form must be an object or null')
            form = row['form']
            if form is not None:
                if not isinstance(form, dict) or set(form) != {'plugin', 'id'}:
                    raise ValueError('form must contain plugin and id')
                plugin = form['plugin']
                if not isinstance(plugin, str) or not re.fullmatch(r'[^/\\:]+\.(?:esm|esp|esl)', plugin, re.I):
                    raise ValueError('form plugin must be a plugin filename')
                if not isinstance(form['id'], str) or not re.fullmatch(r'0x[0-9A-Fa-f]{8}', form['id']):
                    raise ValueError('stored form id must be 0x plus eight hex digits')
                key = (plugin.casefold(), _form_id(form['id']))
                if key in self._forms:
                    raise ValueError('duplicate performer form')
                self._forms[key] = row
            self._names[row['name'].casefold()] = row

    def find_by_form(self, plugin, id):
        """Exact plugin-local identity; accept a hexadecimal string or integer id."""
        return self._forms.get((plugin.casefold(), _form_id(id)))

    def find_by_name(self, name):
        """Case-insensitive exact display name; no substring/fuzzy matching."""
        return self._names.get(name.casefold())


def load_registry(path=DEFAULT_PATH):
    return Registry(json.loads(Path(path).read_text(encoding='utf-8-sig')))
