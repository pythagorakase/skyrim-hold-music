import unittest
from pex_vm import VM
from pathlib import Path
import re

TRACE_EVENTS = {
    "location_enter", "location_leave", "check_start", "candidate",
    "no_performer", "slot_chosen", "vanilla_stopped", "vanilla_unavailable",
    "vanilla_restarted", "idle_failed", "performance_start", "performance_stop",
    "receipt_failed", "session_cap", "disabled", "trace_rolled",
}

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
        v=VM(); row=next(r for r in v.files['../HoldMusic/registry.json']['performers'] if r['id']=='mikael')
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

    def traces(self, v, event=None):
        entries = v.files.get('HoldMusic/trace.json', {}).get('entries', [])
        for entry in entries:
            self.assertIn(entry['event'], TRACE_EVENTS)
            self.assertEqual(set(entry), {'seq', 'real_seconds', 'game_hours', 'event', 'detail'})
        return [e['detail'] for e in entries if event is None or e['event'] == event]

    def test_owner_gate_and_continue_to_owned_candidate(self):
        v=VM(); v.files['../HoldMusic/registry.json']['performers'][0]['owner']='skyrimnet'
        v.candidates=['Mikael','Sven']; v.enter(); v.advance(15)
        self.assertNotIn(('play',1,'Mikael'),v.effects)
        self.assertIn(('play',2,'Sven'),v.effects)
        self.assertEqual(self.traces(v,'candidate'),[
            'id=mikael owner=skyrimnet eligible=true region=whiterun cooled=true',
            'id=sven owner=hold_music eligible=true region=whiterun cooled=true'])

    def test_owner_missing_unknown_and_skyrimnet_never_perform(self):
        for owner in (None, '', 'unknown', 'skyrimnet'):
            with self.subTest(owner=owner):
                v=VM(); row=v.files['../HoldMusic/registry.json']['performers'][0]
                if owner is None: del row['owner']
                else: row['owner']=owner
                self.assertEqual(v.run('hm_library','Owner','mikael'), owner or '')
                self.assertEqual(v.run('hm_library','Owner','absent'),'')
                v.enter(); v.advance(15)
                self.assertFalse(any(x[0] in ('play','idle','stop_vanilla') for x in v.effects))
                self.assertEqual(self.traces(v,'candidate'),['id=mikael owner=skyrimnet eligible=true region=whiterun cooled=true'])
                self.assertEqual(self.traces(v,'no_performer'),['scanned=1 matched=1'])

    def test_vanilla_stopped_before_idle_and_sound(self):
        v=self.start()
        self.assertLess(v.effects.index(('stop_vanilla',)),v.effects.index(('idle','Mikael','IdleLuteStart')))
        self.assertEqual(self.traces(v,'vanilla_stopped'),[''])
        self.assertEqual(self.traces(v,'slot_chosen'),['id=mikael slot=1 mode=instrumental'])
        self.assertEqual(self.traces(v,'performance_start'),['id=mikael slot=1 duration=6.0'])
        self.assertEqual(self.traces(v,'check_start'),['venue=117644'])

    def test_every_vanilla_scene_can_restart_without_restarting_sound(self):
        for scene in range(16):
            with self.subTest(scene=scene):
                v=self.start(); v.scene_playing[scene]=True; mark=len(v.effects); v.advance(2)
                effects=v.effects[mark:]
                self.assertEqual([x[1] for x in effects if x[0]=='scene_check'],list(range(16)))
                self.assertLess(effects.index(('stop_vanilla',)),effects.index(('idle','Mikael','IdleLuteStart')))
                self.assertEqual(self.traces(v,'vanilla_restarted'),['scene='+str(scene)])
                self.assertEqual(len([x for x in v.effects if x[0]=='play']),1)
                self.assertFalse(any(x[0]=='stop' for x in effects))
                self.assertEqual(v.state['hm_controller']['instance'],1001)
                self.assertEqual(v.scheduled,2)
                self.assertFalse(v.receipts)

    def test_vanilla_unavailable_still_performs_and_polls(self):
        v=VM(); v.vanilla_available=False; self.start(v)
        self.assertEqual(self.traces(v,'vanilla_unavailable'),[''])
        self.assertNotIn(('stop_vanilla',),v.effects)
        v.scene_playing[15]=True; v.advance(2)
        self.assertEqual(self.traces(v,'vanilla_unavailable'),['',''])
        self.assertEqual(v.scheduled,2)
        self.assertEqual(len([x for x in v.effects if x[0]=='play']),1)

    def test_no_performer_counts_and_ineligible_candidates_are_traced(self):
        v=VM(); v.candidates=['Other','Mikael','Sven']
        v.actors['Mikael']['sleep']=3
        v.files['../HoldMusic/registry.json']['performers'][1]['region']=None
        v.enter(); v.advance(15)
        self.assertEqual(self.traces(v,'no_performer'),['scanned=3 matched=2'])
        self.assertEqual(self.traces(v,'candidate'),[
            'id=mikael owner=hold_music eligible=false region=whiterun cooled=true',
            'id=sven owner=hold_music eligible=true region=none cooled=true'])
        v=VM(); v.candidates=[]; v.enter(); v.advance(15)
        self.assertEqual(self.traces(v,'no_performer'),['scanned=0 matched=0'])
        self.assertEqual(self.traces(v,'candidate'),[])

    def test_cooldown_and_missing_recording_trace(self):
        v=self.start(); v.advance(6); v.enter(); v.advance(15)
        self.assertEqual(self.traces(v,'candidate')[-1],'id=mikael owner=hold_music eligible=true region=whiterun cooled=false')
        self.assertEqual(self.traces(v,'no_performer'),['scanned=1 matched=1'])
        v=VM(); v.files['HoldMusic/library.json']['recordings']=[]; v.enter(); v.advance(15)
        self.assertEqual(self.traces(v,'no_performer'),['scanned=1 matched=1'])
        self.assertEqual(self.traces(v,'slot_chosen'),[])

    def test_lifecycle_trace_and_no_load_event(self):
        v=VM(); v.enter('outside')
        # Non-inn locations are not traced: the ring must hold inn evidence.
        self.assertEqual(self.traces(v,'location_enter'),[])
        self.start(v); v.advance(6)
        self.assertEqual(self.traces(v,'performance_stop'),['outcome=completed id=mikael slot=1'])
        v=self.start(); before=len(self.traces(v,'location_enter'))
        v.run('hm_controller','OnPlayerLoadGame')
        self.assertEqual(len(self.traces(v,'location_enter')),before)
        self.assertEqual(self.traces(v,'performance_stop'),['outcome=interrupted id=mikael slot=1'])
        v=self.start(); v.actors['P']['location']='outside'
        v.run('hm_controller','OnLocationChange','inn','outside')
        self.assertEqual(self.traces(v,'location_leave'),[''])
        self.assertEqual(self.traces(v,'location_enter'),['inn=true'])
        v=self.start(); v.actors['P']['location']='outside'
        v.run('hm_controller','OnLocationChange','outside','outside')
        self.assertEqual(self.traces(v,'location_leave'),[])
        v=VM(); v.settings['HM_Enabled']=0; v.enter()
        self.assertEqual(self.traces(v,'disabled'),[''])
        v=VM(); v.settings['HM_SessionCap']=0; v.enter()
        self.assertEqual(self.traces(v,'session_cap'),[''])
        v=self.start(); v.settings['HM_Enabled']=0; v.advance(2)
        self.assertEqual(self.traces(v,'disabled'),[''])
        self.assertEqual(self.traces(v,'performance_stop'),['outcome=interrupted id=mikael slot=1'])

    def test_idle_and_receipt_failure_trace(self):
        v=VM(); v.idle_succeeds=False; v.enter(); v.advance(15)
        self.assertEqual(self.traces(v,'idle_failed'),['id=mikael slot=1'])
        self.assertEqual(self.traces(v,'performance_start'),[])
        self.assertEqual(self.traces(v,'no_performer'),['scanned=1 matched=1'])
        self.assertFalse(any(x[0]=='play' for x in v.effects))
        v=self.start(); v.save_failures.add('HoldMusic/receipts.json'); v.advance(6)
        self.assertEqual(self.traces(v,'receipt_failed'),['id=mikael slot=1'])
        self.assertIn(('save','HoldMusic/trace.json'),v.effects)

    def test_trace_schema_ring_and_monotonic_sequence(self):
        v=VM()
        for i in range(300): v.run('hm_library','Trace','candidate','id='+str(i))
        entries=v.files['HoldMusic/trace.json']['entries']
        self.assertEqual(len(entries),300)
        self.assertEqual([e['seq'] for e in entries],list(range(1,301)))
        self.assertEqual(entries[0],dict(seq=1,real_seconds=100.0,game_hours=1008.0,event='candidate',detail='id=0'))
        self.assertEqual(v.files['HoldMusic/trace.json']['version'],1)
        # Simulate loading a save with an older script counter.
        v.state['hm_library']['tracesequence']=2
        v.run('hm_library','Trace','disabled','')
        self.assertEqual(v.files['HoldMusic/trace.json']['entries'],[
            dict(seq=301,real_seconds=100.0,game_hours=1008.0,event='trace_rolled',detail='dropped=300'),
            dict(seq=302,real_seconds=100.0,game_hours=1008.0,event='disabled',detail='')])
        self.assertIn(('clearpath','HoldMusic/trace.json','.entries'),v.effects)
        self.assertEqual(v.effects.count(('save','HoldMusic/trace.json')),302)
        self.traces(v)

    def test_trace_save_failure_warns_once_per_session(self):
        v=VM(); v.save_failures.add('HoldMusic/trace.json')
        for _ in range(3): v.run('hm_library','Trace','disabled','')
        self.assertEqual([x for x in v.effects if x[0]=='trace'],[('trace','HoldMusic: trace save failed',0)])
        self.assertEqual(v.effects.count(('save','HoldMusic/trace.json')),3)
        v.run('hm_library','ResetSession'); v.run('hm_library','Trace','disabled','')
        self.assertEqual(len([x for x in v.effects if x[0]=='trace']),2)
        self.traces(v)


class TraceContractTests(unittest.TestCase):
    def test_all_emitted_event_names_match_frozen_contract(self):
        source=Path(__file__).resolve().parents[1]/'src/Scripts/Source'
        text='\n'.join(p.read_text() for p in source.glob('*.psc'))
        emitted=set(re.findall(r'(?<!Debug\.)\b(?:Trace|AppendTraceEntry)\("([^"\n]+)"',text))
        self.assertEqual(emitted,TRACE_EVENTS)

if __name__=='__main__': unittest.main()
