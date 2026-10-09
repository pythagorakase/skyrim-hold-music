"""Portable source contract; compiled artifact checks live in game_package/tests."""
import json
from pathlib import Path
import re
import unittest
import tempfile

from game_package.tools.build_registry import build_registry, derive_registry
from hold_music.registry import REGIONS, load_registry

ROOT=Path(__file__).resolve().parents[1]/'game_package'

class GamePackageSourceTests(unittest.TestCase):
    def test_required_sources_and_configuration(self):
        for name in ('HM_Controller','HM_Library','HM_Config'):
            p=ROOT/'src/Scripts/Source'/f'{name}.psc'
            self.assertTrue(p.is_file(),str(p))
            self.assertRegex(p.read_text(),rf'(?i)Scriptname {name} extends ')
        for path in ('src/mcm/config/HoldMusic/config.json','src/SKSE/Plugins/HoldMusic/registry.json','data/forms.json','data/slots.json'):
            self.assertIsInstance(json.loads((ROOT/path).read_text()),(dict,list))
        config=json.loads((ROOT/'src/mcm/config/HoldMusic/config.json').read_text())
        self.assertEqual(config['modName'],'HoldMusic')
        valid={'PropertyValueBool','PropertyValueInt','PropertyValueFloat','ModSettingBool','ModSettingInt','ModSettingFloat','GlobalValue'}
        for control in config['pages'][0]['content']:
            source=control.get('valueOptions',{}).get('sourceType')
            if source is not None: self.assertIn(source,valid)
        self.assertEqual({c['id'] for c in config['pages'][0]['content']},{'bEnabled:General','iInstrumentalPercent:General','iSessionCap:General','sWorldId:General','stop'})

    def test_resolved_form_ids(self):
        forms=json.loads((ROOT/'data/forms.json').read_text())['forms']
        self.assertTrue(forms)
        for form in forms:
            self.assertRegex(form['id'],r'^0x[0-9A-F]{8}$')
            self.assertRegex(form['plugin'],r'(?i)\.(esm|esp|esl)$')
            self.assertTrue(form['edid'])
            self.assertEqual(len(form['type']),4)
        ids={f['edid']:f['id'] for f in forms}
        self.assertEqual(ids['LocTypeInn'],'0x0001CB87')
        registry=json.loads((ROOT/'src/SKSE/Plugins/HoldMusic/registry.json').read_text())
        self.assertEqual(registry, derive_registry())
        authored = load_registry().performers
        self.assertEqual(len(registry['performers']), len(authored))
        for performer, source in zip(registry['performers'], authored):
            self.assertTrue(performer['region'] is None or performer['region'] in REGIONS)
            if source['form'] is not None:
                self.assertEqual(performer['form'], dict(plugin=source['form']['plugin'], id=int(source['form']['id'], 16)))
        build_registry(check=True)

    def test_registry_check_rejects_drift_without_rewriting(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'registry.json'
            build_registry(output=path)
            build_registry(output=path, check=True)
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'stale'):
                build_registry(output=path, check=True)
            self.assertEqual(path.read_text(), '{}')

    def test_shared_slot_contract_and_builder_binding(self):
        slots=json.loads((ROOT/'data/slots.json').read_text())
        self.assertEqual([s['slot'] for s in slots],list(range(1,25)))
        ids=[]
        for s in slots:
            n=s['slot']
            self.assertEqual(s['descriptor'],f'HM_Slot{n:02}')
            self.assertEqual(s['marker'],f'HM_Sound_{n:02}')
            self.assertEqual(s['file'],f'Sound\\fx\\holdmusic\\hm_slot_{n:02}.wav')
            ids.extend((s['descriptor_id'],s['marker_id']))
        self.assertEqual(len(set(ids)),48)
        source=(ROOT/'src/Scripts/Source/HM_Controller.psc').read_text()
        builder=(ROOT/'tools/PluginBuilder/Program.cs').read_text()
        self.assertRegex(source,r'Sound\[\] Property SlotSounds Auto')
        self.assertIn('SlotSounds[chosen - 1].Play(candidate)',source)
        self.assertIn('SlotSounds.Length == 24',source)
        self.assertIn('"slots.json"',builder)
        self.assertIn('Name = "SlotSounds"',builder)
        self.assertIn('mod.SoundDescriptors.Add(descriptor)',builder)
        self.assertIn('mod.SoundMarkers.Add(marker)',builder)
        self.assertIn('sounds.Objects.Add(value)',builder)
        named=set(re.findall(r'HM_(?:Slot|Sound_)[0-9]{2}',source))
        self.assertLessEqual(named,{s[k] for s in slots for k in ('descriptor','marker')})
