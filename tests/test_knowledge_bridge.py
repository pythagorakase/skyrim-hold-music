from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from hold_music.knowledge_bridge import classify, read_database, resolve_uuid, snapshot
from hold_music.library import Library
from hold_music.lyria_client import MODEL
from hold_music.registry import load_registry
from hold_music.repertoire import Snapshot, plan

FIXTURE = Path(__file__).parent / 'fixtures/skyrimnet_knowledge_sample.json'


def make_database(path):
    fixture = json.loads(FIXTURE.read_text())
    assert fixture['synthetic']
    with closing(sqlite3.connect(path)) as db, db:
        for table, columns in fixture['schema'].items():
            db.execute(f'CREATE TABLE {table} ({columns})')
        for table, rows in fixture['rows'].items():
            for row in rows:
                db.execute(f'INSERT INTO {table} ({",".join(row)}) VALUES ({",".join("?" for _ in row)})',
                           tuple(row.values()))
    return path


def request():
    return dict(tradition='whiterun', arrangement='solo_lute_and_voice', mode='lyrical',
                voice='male', recipe_id='whiterun/vocal', model_id=MODEL)


class KnowledgeBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = make_database(self.root / 'SkyrimNet-synthetic-save.db')
        self.performer = load_registry().find_by_name('Mikael')
        self.library = Library(self.root / 'library')

    def snap(self, **kwargs):
        return snapshot(self.performer, self.db, self.library, kwargs.pop('now_hours', None),
                        request(), allow_name_match=kwargs.pop('allow_name_match', True), **kwargs)

    def test_identity_is_plugin_scoped_and_opt_in(self):
        with read_database(self.db) as db:
            self.assertIsNone(resolve_uuid(self.performer, db))
            self.assertEqual(resolve_uuid(self.performer, db, allow_name_match=True), 101)
            self.assertEqual(db.execute('PRAGMA query_only').fetchone()[0], 1)
            with self.assertRaises(sqlite3.OperationalError):
                db.execute('DELETE FROM memories')
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE uuid_mappings SET local_form_id=108144 WHERE uuid=101')
        with read_database(self.db) as db:
            self.assertEqual(resolve_uuid(self.performer, db), 101)

    def test_ambiguous_name_is_unresolved(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("INSERT INTO uuid_mappings(uuid,form_id,actor_name,mod_file,local_form_id) VALUES(404,7,'MIKAEL','SKYRIM.ESM',7)")
        data, report = self.snap()
        self.assertFalse(report['uuid_resolved'])
        self.assertEqual(report['resolution'], 'ambiguous_actor_name')
        self.assertEqual(data['observations'], [])

    def test_observations_scope_mapping_and_clocks(self):
        before = self.db.read_bytes()
        data, report = self.snap()
        Snapshot.from_dict(data)
        rows = {row['id']: row for row in data['observations']}
        self.assertEqual(set(rows), {'mem:1', 'mem:2', 'mem:3', 'evt:21', 'evt:22', 'evt:24'})
        self.assertEqual(data['save_id'], 'synthetic-save')
        self.assertEqual(data['world_id'], 'synthetic-save')
        self.assertEqual(data['now_hours'], 102)  # All events, not another actor's memories.
        direct = rows['mem:1']
        self.assertEqual((direct['happened_at'], direct['learned_at']), (100, 100))
        self.assertEqual((direct['topic_id'], direct['event_id']), ('evt:21', 'evt:21'))
        self.assertEqual(direct['source_id'], 'skyrimnet:memory:1')
        self.assertEqual((direct['kind'], direct['evidence']), ('quest_success', 'direct'))
        self.assertEqual((direct['interest'], direct['local_relevance']), (.9, 1))
        self.assertEqual((rows['mem:2']['happened_at'], rows['mem:2']['learned_at']), (None, 99))
        self.assertEqual((rows['mem:2']['interest'], rows['mem:2']['local_relevance']), (1, .5))
        self.assertEqual((rows['mem:3']['interest'], rows['mem:3']['local_relevance']), (0, .2))
        self.assertEqual(rows['mem:3']['topic_id'], 'mem:3')
        self.assertIsNone(rows['mem:3']['happened_at'])
        self.assertIsNone(rows['mem:3']['learned_at'])
        self.assertIsNone(rows['evt:24']['learned_at'])
        self.assertEqual(rows['evt:22']['learned_at'], 101)
        self.assertEqual(report['memories'], 3)
        self.assertEqual(report['events'], 3)
        self.assertEqual(report['observations'], 6)
        self.assertEqual(before, self.db.read_bytes())
        self.assertNotIn('fictional', json.dumps(report))
        self.assertEqual(plan(data)['action'], 'compose_lyrics')

    def test_limits_since_and_null_times(self):
        data, report = self.snap(max_observations=2, since_hours=100, now_hours=105)
        self.assertEqual(len(data['observations']), 2)
        self.assertEqual(data['now_hours'], 105)
        self.assertTrue(all(row['learned_at'] >= 100 for row in data['observations']))
        self.assertEqual(self.snap(max_observations=0)[0]['observations'], [])
        with self.assertRaises(ValueError):
            self.snap(now_hours=float('nan'))

    def test_summary_trim_and_invalid_time_importance(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE memories SET content=?, game_time=-1, importance_score=NULL WHERE id=1", ('x' * 600,))
        rows = {row['id']: row for row in self.snap()[0]['observations']}
        self.assertEqual(len(rows['mem:1']['summary']), 500)
        self.assertIsNone(rows['mem:1']['learned_at'])
        self.assertEqual(rows['mem:1']['interest'], .5)

    def test_kind_rules_do_not_infer_quest_success(self):
        cases = [
            ('EXPERIENCE', '[]', ('everyday_news', 'rumor')),
            ('EXPERIENCE', '["quest_completed"]', ('everyday_news', 'rumor')),
            ('EXPERIENCE', '["witnessed", "quest_completed"]', ('quest_success', 'direct')),
            ('EXPERIENCE', '["witnessed", "hearsay", "quest_completed"]', ('gossip', 'rumor')),
            ('EXPERIENCE', '["theft_accusation", "hearsay"]', ('scandal', 'rumor')),
            ('EXPERIENCE', '["affair"]', ('scandal', 'rumor')),
            ('GOSSIP', None, ('gossip', 'rumor')),
            ('mystery', None, ('other', 'rumor')),
            ('', None, ('other', 'rumor')),
        ]
        for kind, tags, expected in cases:
            with self.subTest(kind=kind, tags=tags):
                self.assertEqual(classify(kind, tags), expected)

    def test_unresolved_and_missing_database(self):
        data, report = self.snap(allow_name_match=False)
        self.assertEqual(data['observations'], [])
        self.assertIn('actor_uuid', report['unresolved_fields'])
        with self.assertRaises(sqlite3.OperationalError):
            with read_database(self.root / 'absent.db'):
                pass
        self.assertFalse((self.root / 'absent.db').exists())


if __name__ == '__main__':
    unittest.main()
