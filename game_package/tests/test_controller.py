import unittest
from pex_vm import VM

class ControllerTests(unittest.TestCase):
    def start(self, vm=None):
        v=vm or VM(); v.enter(); v.advance(15)
        self.assertTrue(any(x[0]=='play' for x in v.effects))
        return v

    def test_inn_entry_schedules_randomized_check(self):
        v=VM(); v.enter(); self.assertEqual(v.scheduled,15)
        self.assertFalse(any(x[0]=='play' for x in v.effects))

    def test_non_inn_ignored(self):
        v=VM(); v.enter('outside'); self.assertIsNone(v.scheduled)

    def test_no_registered_performer(self):
        v=VM(); v.candidates=['Other']; v.enter(); v.advance(15)
        self.assertFalse(any(x[0]=='play' for x in v.effects))
        self.assertIsNone(v.state['hm_controller']['performer'])

    def test_start_uses_idle_and_matching_sound(self):
        v=self.start()
        self.assertIn(('idle','Mikael','IdleLuteStart'),v.effects)
        self.assertIn(('play',1,'Mikael'),v.effects)
        self.assertEqual(v.scheduled,2)
        self.assertLess(v.effects.index(('idle','Mikael','IdleLuteStart')),v.effects.index(('play',1,'Mikael')))

    def test_duration_elapsed_completed_receipt(self):
        v=self.start(); v.advance(2); self.assertFalse(v.receipts)
        v.advance(4)
        self.assertIn(('stop',1001),v.effects)
        self.assertIn(('idle','Mikael','IdleStop'),v.effects)
        self.assertEqual(v.receipts[0]['outcome'],'completed')
        self.assertEqual(v.receipts[0]['slot'],1)
        self.assertEqual(v.receipts[0]['composition_id'],'c1')
        self.assertTrue(v.receipts[0]['save_id'].startswith('20:P:'))
        self.assertIn(('save','HoldMusic/receipts.json'),v.effects)

    def test_dialogue_interrupts(self):
        v=self.start(); v.actors['Mikael']['dialogue']=True; v.advance(2)
        self.assertEqual(v.receipts[0]['outcome'],'interrupted')
        self.assertIsNone(v.scheduled)

    def test_session_cap(self):
        v=VM(); v.settings['HM_SessionCap']=1
        self.start(v); v.advance(6); v.candidates=['Sven']; v.enter(); v.advance(60)
        self.assertEqual(len([x for x in v.effects if x[0]=='play']),1)

    def test_disabled_entry_and_running_toggle(self):
        v=VM(); v.settings['HM_Enabled']=0; v.enter(); v.advance(60)
        self.assertFalse(any(x[0]=='play' for x in v.effects))
        v.settings['HM_Enabled']=1; self.start(v)
        v.settings['HM_Enabled']=0; v.advance(2)
        self.assertEqual(v.receipts[0]['outcome'],'interrupted')

    def test_load_game_cleanup_and_preserved_locks(self):
        v=self.start(); v.run('hm_controller','OnPlayerLoadGame')
        self.assertEqual(v.receipts[0]['outcome'],'interrupted')
        self.assertIsNone(v.state['hm_controller']['performer'])
        self.assertEqual(v.state['hm_controller']['sessioncount'],0)
        self.assertIsNone(v.scheduled)
        self.assertTrue(v.state['hm_library']['locked'][0])
        v.run('hm_controller','OnPlayerLoadGame'); self.assertEqual(len(v.receipts),1)

    def test_all_interruption_conditions(self):
        for key,value in [('combat',True),('loaded',False),('dead',True),('cell','other'),('sleep',3),('sit',3)]:
            with self.subTest(key=key):
                v=self.start(); v.actors['Mikael'][key]=value; v.advance(2)
                self.assertEqual(v.receipts[0]['outcome'],'interrupted')
        v=self.start(); v.enter('outside')
        self.assertEqual(v.receipts[0]['outcome'],'interrupted')
        v=self.start(); v.run('hm_config','StopPerformance'); v.advance(2)
        self.assertEqual(v.receipts[0]['outcome'],'interrupted')

    def test_eligibility_filters(self):
        for key,value in [('combat',True),('loaded',False),('dead',True),('follower',True),('dialogue',True),('sleep',3),('sit',3)]:
            with self.subTest(key=key):
                v=VM(); v.actors['Mikael'][key]=value; v.enter(); v.advance(15)
                self.assertFalse(any(x[0]=='play' for x in v.effects))

    def test_performer_cooldown_and_single_performance(self):
        v=self.start(); v.run('hm_controller','OnUpdate')
        self.assertEqual(len([x for x in v.effects if x[0]=='play']),1)
        v.advance(6)
        row=v.files['HoldMusic/library.json']['recordings'][0].copy(); row.update(slot=3,composition_id='c3')
        v.files['HoldMusic/library.json']['recordings'].append(row)
        v.enter(); v.advance(60)
        self.assertEqual(len([x for x in v.effects if x[0]=='play']),1)
        v.now+=1800; v.enter(); v.advance(15)
        self.assertIn(('play',3,'Mikael'),v.effects)

    def test_slot_selection_unperformed_oldest_and_locks(self):
        v=VM(); rows=v.files['HoldMusic/library.json']['recordings']
        rows.append(dict(rows[0],slot=3,composition_id='c3'))
        v.receipts.extend([{'composition_id':'c1'},{'composition_id':'c3'}])
        self.assertEqual(v.run('hm_library','ChooseSlot','mikael','whiterun','instrumental'),1)
        rows.append(dict(rows[0],slot=4,composition_id='c4'))
        self.assertEqual(v.run('hm_library','ChooseSlot','mikael','whiterun','instrumental'),4)
        v.run('hm_library','LockSlot',4)
        self.assertEqual(v.run('hm_library','ChooseSlot','mikael','whiterun','instrumental'),1)
        self.assertEqual(v.run('hm_library','ChooseSlot','mikael','rift','instrumental'),0)

    def test_registry_null_fallback_and_malformed_form_rejection(self):
        v=VM(); row=v.files['../HoldMusic/registry.json']['performers'][0]
        row['form']=None
        self.assertEqual(v.run('hm_library','FindPerformer','Mikael'),'mikael')
        for form in ({'plugin':'Skyrim.esm','id':123},'garbage',[],12,True):
            row['form']=form
            self.assertEqual(v.run('hm_library','FindPerformer','Mikael'),'')
        del row['form']
        self.assertEqual(v.run('hm_library','FindPerformer','Mikael'),'')

    def test_mcm_settings_and_world_id(self):
        v=VM(); v.modsettings.update({'bEnabled:General':False,'iSessionCap:General':5,'sWorldId:General':'world-a'})
        v.run('hm_config','OnSettingChange','bEnabled:General')
        self.assertEqual(v.settings['HM_Enabled'],0)
        self.assertEqual(v.settings['HM_SessionCap'],5)
        self.assertEqual(v.state['hm_config']['::worldid_var'],'world-a')

if __name__=='__main__': unittest.main()
