import unittest
from pex_vm import VM
from pathlib import Path
import re

TRACE_EVENTS = {
    "location_enter", "location_leave", "check_start", "candidate",
    "no_performer", "slot_chosen", "vanilla_stopped", "vanilla_unavailable",
    "vanilla_restarted", "idle_failed", "performance_start", "performance_stop",
    "receipt_failed", "session_cap", "disabled", "trace_rolled",
    "idle_failed_state", "performance_interrupt_guard",
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

    def test_dead_unregistered_actor_does_not_block_living_performer(self):
        v=VM(); v.actors['Other']['dead']=True
        v.candidates=['Other','Sven']; v.enter(); v.advance(15)
        self.assertEqual([x for x in v.effects if x[0]=='play'],[('play',2,'Sven')])
        self.assertEqual(self.traces(v,'candidate'),[
            'id=sven owner=hold_music eligible=true region=whiterun cooled=true'])
        self.assertFalse(v.receipts)

    def test_dead_owned_actor_is_rejected_before_living_performer(self):
        v=VM(); v.actors['Mikael']['dead']=True
        v.candidates=['Mikael','Sven']; v.enter(); v.advance(15)
        self.assertEqual(self.traces(v,'candidate'),[
            'id=mikael owner=hold_music eligible=false region=whiterun cooled=true',
            'id=sven owner=hold_music eligible=true region=whiterun cooled=true'])
        self.assertEqual([x for x in v.effects if x[0]=='play'],[('play',2,'Sven')])
        self.assertNotIn(('idle','Mikael','IdleLuteStart'),v.effects)
        self.assertEqual(self.traces(v,'slot_chosen'),['id=sven slot=2 mode=instrumental'])
        self.assertFalse(v.receipts)

    def test_all_dead_candidates_leave_vanilla_and_audio_untouched(self):
        v=VM(); v.candidates=['Other','Mikael','Sven']
        for name in v.candidates: v.actors[name]['dead']=True
        v.enter(); v.advance(15)
        self.assertEqual(self.traces(v,'no_performer'),['scanned=3 matched=2'])
        self.assertEqual(self.traces(v,'candidate'),[
            'id=mikael owner=hold_music eligible=false region=whiterun cooled=true',
            'id=sven owner=hold_music eligible=false region=whiterun cooled=true'])
        self.assertFalse(any(x[0] in ('idle','stop_vanilla','play','stop') for x in v.effects))
        self.assertFalse(v.receipts)
        self.assertIsNone(v.state['hm_controller']['performer'])
        self.assertFalse(v.state['hm_controller']['busy'])

    def test_null_and_unloaded_candidates_preserve_name_only_matching(self):
        v=VM(); v.actors['Mikael']['loaded']=False
        row=next(r for r in v.files['../HoldMusic/registry.json']['performers'] if r['id']=='sven')
        row['form']=None
        v.candidates=[None,'Mikael','Sven']; v.enter(); v.advance(15)
        self.assertEqual(self.traces(v,'candidate'),[
            'id=mikael owner=hold_music eligible=false region=whiterun cooled=true',
            'id=sven owner=hold_music eligible=true region=whiterun cooled=true'])
        self.assertEqual([x for x in v.effects if x[0]=='play'],[('play',2,'Sven')])
        self.assertNotIn(('idle','Mikael','IdleLuteStart'),v.effects)

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

    def test_idle_refusal_records_current_actor_state_without_retry(self):
        v=VM()
        original=v.method
        def refuse_after_actor_changes(obj, name, args):
            if name=='playidle' and args==['IdleLuteStart']:
                v.actors['Mikael']['sit']=3
                v.scene_playing[2]=True
                v.idle_succeeds=False
            return original(obj,name,args)
        v.method=refuse_after_actor_changes
        v.enter(); v.advance(15)
        details=self.traces(v,'idle_failed_state')
        self.assertEqual(len(details),1)
        for field in ('reason=native_idle_refused','loaded=1','sit=3','sleep=0',
                      'same_cell=1','vanilla_scenes_playing=1'):
            self.assertIn(field,details[0])
        self.assertEqual(v.effects.count(('idle','Mikael','IdleLuteStart')),1)
        self.assertFalse(v.receipts)
        self.assertFalse(any(effect[0]=='play' for effect in v.effects))
        self.assertFalse(any(v.state['hm_library']['locked']))

    def test_poll_interruptions_record_exact_first_guard_and_state(self):
        cases=[('loaded',False,'actor_unloaded'),('dead',True,'actor_dead'),
               ('combat',True,'actor_combat'),('dialogue',True,'actor_dialogue'),
               ('follower',True,'actor_follower'),('sit',3,'actor_sit'),
               ('sleep',3,'actor_sleep'),('cell','other','cell_changed'),
               ('disabled',True,'disabled'),('stop',True,'stop_requested'),
               ('venue',True,'venue_changed')]
        for key,value,reason in cases:
            with self.subTest(reason=reason):
                v=self.start()
                if key=='disabled': v.settings['HM_Enabled']=0
                elif key=='stop': v.state['hm_config']['::stoprequested_var']=True
                elif key=='venue': v.actors['P']['location']='outside'
                else: v.actors['Mikael'][key]=value
                v.advance(2)
                details=self.traces(v,'performance_interrupt_guard')
                self.assertEqual(len(details),1)
                self.assertIn('reason='+reason,details[0])
                self.assertIn('id=mikael slot=1',details[0])
                self.assertEqual([row['outcome'] for row in v.receipts],['interrupted'])
                self.assertEqual(self.traces(v,'performance_stop'),['outcome=interrupted id=mikael slot=1'])
                self.assertEqual(len([effect for effect in v.effects if effect[0]=='play']),1)

    def test_guard_reason_survives_state_change_during_diagnostic_snapshot(self):
        v=self.start(); original=v.method; reads=0
        def changing_combat(obj,name,args):
            nonlocal reads
            if obj=='Mikael' and name=='isincombat':
                reads+=1
                return reads==1
            return original(obj,name,args)
        v.method=changing_combat
        v.advance(2)
        detail=self.traces(v,'performance_interrupt_guard')[0]
        self.assertIn('reason=actor_combat',detail)
        self.assertIn('combat=0',detail)
        self.assertEqual(v.receipts[0]['outcome'],'interrupted')

    def test_successful_polls_do_not_emit_failure_diagnostics(self):
        v=self.start(); v.advance(2); v.advance(4)
        self.assertEqual(v.receipts[0]['outcome'],'completed')
        self.assertEqual(self.traces(v,'performance_interrupt_guard'),[])
        self.assertEqual(self.traces(v,'idle_failed_state'),[])

    def test_poll_guard_preserves_original_precedence(self):
        v=self.start()
        v.settings['HM_Enabled']=0
        v.state['hm_config']['::stoprequested_var']=True
        v.actors['Mikael'].update(loaded=False,dead=True,combat=True,sit=3)
        v.advance(2)
        self.assertIn('reason=disabled',self.traces(v,'performance_interrupt_guard')[0])

    def test_guard_short_circuit_avoids_unneeded_actor_native_calls(self):
        v=VM(); original=v.method
        def reject_actor_reads(obj,name,args):
            if obj=='Mikael':
                raise AssertionError('unexpected actor read: '+name)
            return original(obj,name,args)
        v.method=reject_actor_reads
        self.assertEqual(v.run('hm_controller','EligibilityFailure',None),'actor_missing')
        v.state['hm_controller']['performer']='Mikael'
        v.settings['HM_Enabled']=0
        self.assertEqual(v.run('hm_controller','PollInterruptionReason'),'disabled')
        v.settings['HM_Enabled']=1
        v.state['hm_config']['::stoprequested_var']=True
        self.assertEqual(v.run('hm_controller','PollInterruptionReason'),'stop_requested')
        v.state['hm_config']['::stoprequested_var']=False
        def unloaded_actor_only(obj,name,args):
            if obj=='Mikael' and name=='is3dloaded': return False
            return reject_actor_reads(obj,name,args)
        v.method=unloaded_actor_only
        self.assertEqual(v.run('hm_controller','PollInterruptionReason'),'actor_unloaded')

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


class StopRaceTests(unittest.TestCase):
    """Reenter compiled PEX at mocked native/script call boundaries.

    These deterministically reproduce the engine's overlapping stop stacks;
    they do not claim a general Papyrus scheduler or native AI simulation.
    """

    @staticmethod
    def started():
        v = VM()
        v.enter()
        v.advance(15)
        return v

    def inject_once(self, v, kind, predicate, callback, *, after=False):
        original = getattr(v, kind)
        hits = []

        def injected(*args):
            if not hits and predicate(*args):
                hits.append(args)
                if after:
                    result = original(*args)
                    callback()
                    return result
                callback()
            return original(*args)

        setattr(v, kind, injected)
        return hits

    @staticmethod
    def boundary(name):
        if name == 'sound':
            return 'static', lambda owner, method, args: (owner, method) == ('sound', 'stopinstance')
        if name == 'receipt_save':
            return 'static', lambda owner, method, args: (owner, method) == ('jsonutil', 'save') and args[0] == 'HoldMusic/receipts.json'
        return 'method', lambda obj, method, args: (
            name == 'unregister' and method == 'unregisterforupdate'
            or name == 'idle' and method == 'playidle' and args == ['IdleStop']
            or name == 'trace' and method == 'trace' and args[0] == 'performance_stop'
            or name == 'receipt' and method == 'appendreceipt'
        )

    def assert_single_stop(self, v, outcome='completed'):
        self.assertEqual(len(v.receipts), 1)
        row = v.receipts[0]
        self.assertEqual((row['slot'], row['performer_id'], row['composition_id'], row['outcome']),
                         (1, 'mikael', 'c1', outcome))
        self.assertEqual(v.effects.count(('stop', 1001)), 1)
        self.assertEqual(v.effects.count(('idle', 'Mikael', 'IdleStop')), 1)
        self.assertIsNone(v.state['hm_controller']['performer'])
        self.assertIsNone(v.scheduled)

    def test_first_stop_wins_at_every_cleanup_boundary(self):
        for boundary in ('unregister', 'sound', 'idle', 'trace', 'receipt', 'receipt_save'):
            for after in (False, True):
                with self.subTest(boundary=boundary, after=after):
                    v = self.started()
                    kind, predicate = self.boundary(boundary)
                    hits = self.inject_once(v, kind, predicate,
                                            lambda: v.run('hm_controller', 'StopPerformance', 'interrupted'),
                                            after=after)
                    v.run('hm_controller', 'StopPerformance', 'completed')
                    self.assertEqual(len(hits), 1)
                    self.assert_single_stop(v)

    def test_stop_defers_update_before_mutable_library_selection(self):
        v = self.started()
        v.candidates = ['Sven']
        self.assertFalse(v.state['hm_controller']['busy'])
        kind, predicate = self.boundary('sound')
        hits = self.inject_once(v, kind, predicate, lambda: v.run('hm_controller', 'OnUpdate'))
        v.run('hm_controller', 'StopPerformance', 'completed')
        self.assertEqual(len(hits), 1)
        self.assert_single_stop(v)
        self.assertEqual(v.state['hm_library']['activecomposition'], 'c1')
        self.assertEqual([x for x in v.effects if x[0] == 'play'], [('play', 1, 'Mikael')])

    def test_stop_blocks_direct_start_until_cleanup_has_drained(self):
        for boundary in ('unregister', 'sound', 'idle', 'trace', 'receipt', 'receipt_save'):
            with self.subTest(boundary=boundary):
                v = self.started()
                kind, predicate = self.boundary(boundary)
                hits = self.inject_once(v, kind, predicate,
                                        lambda: v.run('hm_controller', 'StartPerformance', 'Sven', 'sven', 'whiterun', 2))
                v.run('hm_controller', 'StopPerformance', 'completed')
                self.assertEqual(len(hits), 1)
                self.assert_single_stop(v)
                self.assertEqual(v.effects.count(('stop_vanilla',)), 1)
                self.assertNotIn(('idle', 'Sven', 'IdleLuteStart'), v.effects)
                self.assertNotIn(('play', 2, 'Sven'), v.effects)
                # Admission opens after complete cleanup, with no old tail left
                # that can reset the new instance or unregister its timer.
                v.run('hm_library', 'ChooseSlot', 'sven', 'whiterun', 'vocal')
                v.run('hm_controller', 'StartPerformance', 'Sven', 'sven', 'whiterun', 2)
                self.assertEqual(v.state['hm_controller']['performer'], 'Sven')
                self.assertEqual(v.state['hm_controller']['instance'], 1002)
                self.assertEqual(v.scheduled, 2)

    def test_stop_uses_snapshot_receipt_arguments_across_native_calls(self):
        v = self.started()
        v.state['hm_config']['::worldid_var'] = 'original-world'
        original_start = v.state['hm_controller']['started']

        def mutate_observed_shared_fields():
            state = v.state['hm_controller']
            state.update(slot=0, performerid='changed', performanceregion='other', started=999)
            v.state['hm_config']['::worldid_var'] = 'changed-world'

        kind, predicate = self.boundary('sound')
        self.inject_once(v, kind, predicate, mutate_observed_shared_fields)
        v.run('hm_controller', 'StopPerformance', 'completed')
        self.assert_single_stop(v)
        row = v.receipts[0]
        self.assertEqual((row['region'], row['world_id'], row['started_real_seconds']),
                         ('whiterun', 'original-world', original_start))

    def test_idle_stop_preserves_explicit_cancellation_semantics(self):
        v = self.started()
        v.run('hm_controller', 'StopPerformance', 'completed')
        v.run('hm_controller', 'ScheduleCheck')
        v.state['hm_config']['::stoprequested_var'] = True
        before = list(v.effects)
        v.run('hm_controller', 'StopPerformance', 'interrupted')
        self.assertIsNone(v.scheduled)
        self.assertEqual(v.effects, before)
        self.assertEqual(len(v.receipts), 1)
        self.assertFalse(v.state['hm_config']['::stoprequested_var'])

    def test_reentrant_noop_stop_does_not_unregister_a_newer_timer(self):
        v = self.started()

        def concurrent_noop():
            v.scheduled = 23.0
            v.run('hm_controller', 'StopPerformance', 'interrupted')

        kind, predicate = self.boundary('receipt')
        self.inject_once(v, kind, predicate, concurrent_noop, after=True)
        v.run('hm_controller', 'StopPerformance', 'completed')
        self.assertEqual(v.scheduled, 23.0)
        self.assertEqual(len(v.receipts), 1)
        self.assertEqual(v.receipts[0]['slot'], 1)

    def test_stop_during_idle_start_compensates_without_audio_or_new_start(self):
        v = VM()

        def cancel_and_try_start():
            v.run('hm_controller', 'StopPerformance', 'interrupted')
            v.run('hm_controller', 'StartPerformance', 'Sven', 'sven', 'whiterun', 2)
            v.run('hm_controller', 'OnUpdate')

        hits = self.inject_once(v, 'method',
                                lambda obj, name, args: name == 'playidle' and args == ['IdleLuteStart'],
                                cancel_and_try_start, after=True)
        v.enter()
        v.advance(15)
        self.assertEqual(len(hits), 1)
        self.assertEqual([x for x in v.effects if x[0] == 'play'], [])
        self.assertEqual(v.effects.count(('idle', 'Mikael', 'IdleStop')), 1)
        self.assertEqual(v.receipts, [])
        self.assertIsNone(v.state['hm_controller']['performer'])
        self.assertIsNone(v.scheduled)

    def test_stop_during_late_sound_return_stops_exact_returned_instance(self):
        v = VM()

        def cancel_and_try_start():
            v.run('hm_controller', 'StopPerformance', 'interrupted')
            v.run('hm_controller', 'StopPerformance', 'completed')
            v.run('hm_controller', 'StartPerformance', 'Sven', 'sven', 'whiterun', 2)

        hits = self.inject_once(v, 'method',
                                lambda obj, name, args: isinstance(obj, tuple) and obj[0] == 'sound' and name == 'play',
                                cancel_and_try_start, after=True)
        v.enter()
        v.advance(15)
        self.assertEqual(len(hits), 1)
        self.assert_single_stop(v, 'interrupted')
        self.assertEqual([x for x in v.effects if x[0] == 'play'], [('play', 1, 'Mikael')])
        self.assertFalse(v.state['hm_controller'].get('starting', False))
        self.assertFalse(v.state['hm_controller'].get('stopping', False))

    def test_stop_during_start_trace_or_timer_drains_before_reopening_admission(self):
        for boundary in ('trace', 'timer'):
            with self.subTest(boundary=boundary):
                v = VM()
                hits = self.inject_once(v, 'method',
                    lambda obj, name, args: (boundary == 'trace' and name == 'trace' and args[0] == 'performance_start'
                                            or boundary == 'timer' and name == 'registerforsingleupdate' and args == [2.0]),
                    lambda: v.run('hm_controller', 'StopPerformance', 'interrupted'), after=True)
                v.enter()
                v.advance(15)
                self.assertEqual(len(hits), 1)
                self.assert_single_stop(v, 'interrupted')


class AdmissionTests(unittest.TestCase):
    """Compiled-code cancellation tests; natives/scheduler remain mocks."""

    inject_once = StopRaceTests.inject_once

    @staticmethod
    def scan_boundary(point):
        if point == 'scan':
            return 'static', lambda owner, name, args: (owner, name) == ('miscutil', 'scancellnpcs')
        return 'method', lambda obj, name, args: (
            point == 'find' and name == 'findperformer'
            or point == 'eligible' and name == 'eligibilityfailure'
            or point == 'choose' and name == 'chooseslot'
            or point in ('candidate', 'slot_chosen') and name == 'trace' and args[0] == point
            or point == 'start_dispatch' and name in ('startperformance', 'startselectedperformance')
        )

    def test_stop_invalidates_scan_selection_and_last_start_dispatch(self):
        # These use only the old public API and fail on stopfix01 PEX: a stop
        # returned, but its already-admitted scan subsequently began playback.
        for point in ('scan', 'find', 'eligible', 'choose', 'candidate', 'slot_chosen', 'start_dispatch'):
            for after in ((False,) if point == 'start_dispatch' else (False, True)):
                with self.subTest(point=point, after=after):
                    v = VM()
                    kind, predicate = self.scan_boundary(point)
                    hits = self.inject_once(v, kind, predicate,
                        lambda: v.run('hm_controller', 'StopPerformance', 'interrupted'), after=after)
                    v.enter()
                    v.advance(15)
                    self.assertTrue(hits)
                    self.assertFalse(any(e[0] in ('play', 'idle', 'stop_vanilla') for e in v.effects))
                    self.assertFalse(v.receipts)
                    self.assertFalse(v.state['hm_controller']['busy'])

    def test_stop_cancels_late_idle_and_playback_timer_registrations(self):
        for playing in (False, True):
            for after in (False, True):
                with self.subTest(playing=playing, after=after):
                    v = StopRaceTests.started() if playing else VM()
                    hits = self.inject_once(v, 'method',
                        lambda obj, name, args: name == 'registerforsingleupdate',
                        lambda: v.run('hm_controller', 'StopPerformance', 'interrupted'), after=after)
                    if playing:
                        v.run('hm_controller', 'Poll')
                    else:
                        v.enter()
                    self.assertTrue(hits)
                    self.assertIsNone(v.scheduled)
                    self.assertEqual(len(v.receipts), int(playing))

    def test_location_departure_invalidates_an_admitted_scan(self):
        v = VM()
        hits = self.inject_once(v, 'static',
            lambda owner, name, args: (owner, name) == ('miscutil', 'scancellnpcs'),
            lambda: v.enter('outside'), after=True)
        v.enter()
        v.advance(15)
        self.assertTrue(hits)
        self.assertFalse(any(e[0] == 'play' for e in v.effects))
        self.assertIsNone(v.scheduled)

    def test_stop_compensates_late_vanilla_idle_reassertion(self):
        for after in (False, True):
            with self.subTest(after=after):
                v = StopRaceTests.started()
                v.scene_playing[0] = True
                hits = self.inject_once(v, 'method',
                    lambda obj, name, args: name == 'playidle' and args == ['IdleLuteStart'],
                    lambda: v.run('hm_controller', 'StopPerformance', 'interrupted'), after=after)
                v.run('hm_controller', 'CheckVanillaScenes')
                self.assertTrue(hits)
                self.assertEqual([e for e in v.effects if e[0] == 'idle'][-1], ('idle', 'Mikael', 'IdleStop'))
                self.assertEqual(len(v.receipts), 1)
                self.assertIsNone(v.scheduled)

    def test_ticket_is_sticky_single_owner_and_resume_has_no_automatic_effects(self):
        v = VM()
        settings = v.settings.copy()
        ticket = v.run('hm_controller', 'SuspendAdmission')
        self.assertGreater(ticket, 0)
        self.assertTrue(v.run('hm_controller', 'IsAdmissionDrained', ticket))
        self.assertEqual(v.run('hm_controller', 'SuspendAdmission'), 0)
        for wrong in (-1, 0, ticket + 1):
            self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', wrong))
            self.assertFalse(v.run('hm_controller', 'ResumeAdmission', wrong))
        before = list(v.effects)
        v.enter()
        v.advance(15)
        v.run('hm_controller', 'StartPerformance', 'Sven', 'sven', 'whiterun', 2)
        v.run('hm_controller', 'ScheduleCheck')
        v.run('hm_controller', 'Poll')
        self.assertEqual(v.effects, before)
        self.assertIsNone(v.scheduled)
        self.assertEqual(v.settings, settings)
        self.assertTrue(v.run('hm_controller', 'ResumeAdmission', ticket))
        self.assertEqual(v.effects, before)
        self.assertIsNone(v.scheduled)
        self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', ticket))
        self.assertFalse(v.run('hm_controller', 'ResumeAdmission', ticket))
        v.enter()
        v.advance(15)
        self.assertIn(('play', 1, 'Mikael'), v.effects)
        next_ticket = v.run('hm_controller', 'SuspendAdmission')
        self.assertGreater(next_ticket, ticket)
        self.assertFalse(v.run('hm_controller', 'ResumeAdmission', ticket))
        self.assertTrue(v.run('hm_controller', 'IsAdmissionDrained', next_ticket))
        self.assertTrue(v.state['hm_library']['locked'][0])

    def test_suspension_does_not_acknowledge_until_scan_stack_returns(self):
        for point in ('scan', 'find', 'eligible', 'choose', 'candidate', 'slot_chosen', 'start_dispatch'):
            with self.subTest(point=point):
                v = VM()
                tickets = []

                def suspend():
                    ticket = v.run('hm_controller', 'SuspendAdmission')
                    tickets.append(ticket)
                    self.assertGreater(ticket, 0)
                    self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', ticket))
                    self.assertFalse(v.run('hm_controller', 'ResumeAdmission', ticket))
                    v.run('hm_controller', 'OnUpdate')
                    v.run('hm_controller', 'StartPerformance', 'Sven', 'sven', 'whiterun', 2)

                kind, predicate = self.scan_boundary(point)
                self.inject_once(v, kind, predicate, suspend)
                v.enter()
                v.advance(15)
                self.assertEqual(len(tickets), 1)
                self.assertTrue(v.run('hm_controller', 'IsAdmissionDrained', tickets[0]))
                self.assertFalse(any(e[0] in ('play', 'idle', 'stop_vanilla') for e in v.effects))
                self.assertFalse(v.receipts)

    def test_suspension_waits_for_native_start_compensation(self):
        for point in ('vanilla', 'idle', 'sound', 'start_trace', 'start_timer'):
            for after in (False, True):
                with self.subTest(point=point, after=after):
                    v = VM()
                    tickets = []

                    def suspend():
                        ticket = v.run('hm_controller', 'SuspendAdmission')
                        tickets.append(ticket)
                        self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', ticket))
                        self.assertFalse(v.run('hm_controller', 'ResumeAdmission', ticket))
                        v.run('hm_controller', 'StartPerformance', 'Sven', 'sven', 'whiterun', 2)

                    hits = self.inject_once(v, 'method', lambda obj, name, args: (
                        point == 'vanilla' and name == 'stopallsongs'
                        or point == 'idle' and name == 'playidle' and args == ['IdleLuteStart']
                        or point == 'sound' and isinstance(obj, tuple) and obj[0] == 'sound' and name == 'play'
                        or point == 'start_trace' and name == 'trace' and args[0] == 'performance_start'
                        or point == 'start_timer' and name == 'registerforsingleupdate' and args == [2.0]
                    ), suspend, after=after)
                    v.enter()
                    v.advance(15)
                    self.assertTrue(hits)
                    self.assertTrue(v.run('hm_controller', 'IsAdmissionDrained', tickets[0]))
                    self.assertIsNone(v.scheduled)
                    self.assertIsNone(v.state['hm_controller']['performer'])
                    self.assertNotIn(('play', 2, 'Sven'), v.effects)
                    if point in ('sound', 'start_trace', 'start_timer'):
                        self.assertEqual(v.effects.count(('stop', 1001)), 1)
                        self.assertEqual([r['outcome'] for r in v.receipts], ['interrupted'])
                    else:
                        self.assertFalse(v.receipts)
                        self.assertFalse(any(e[0] == 'play' for e in v.effects))

    def test_suspension_waits_for_location_and_timer_stacks(self):
        for point in ('location_trace', 'location_getter', 'timer'):
            for after in (False, True):
                with self.subTest(point=point, after=after):
                    v = VM()
                    tickets = []

                    def suspend():
                        ticket = v.run('hm_controller', 'SuspendAdmission')
                        tickets.append(ticket)
                        self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', ticket))
                        self.assertFalse(v.run('hm_controller', 'ResumeAdmission', ticket))
                        v.enter('outside')
                        self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', ticket))

                    hits = self.inject_once(v, 'method', lambda obj, name, args: (
                        point == 'location_trace' and name == 'trace' and args[0] == 'location_enter'
                        or point == 'location_getter' and obj == 'inn' and name == 'haskeyword'
                        or point == 'timer' and name == 'registerforsingleupdate'
                    ), suspend, after=after)
                    v.enter()
                    self.assertTrue(hits)
                    self.assertTrue(v.run('hm_controller', 'IsAdmissionDrained', tickets[0]))
                    self.assertIsNone(v.scheduled)

    def test_suspension_waits_for_scene_stack_and_compensates_late_idle(self):
        for point in ('scene', 'vanilla', 'idle'):
            for after in (False, True):
                with self.subTest(point=point, after=after):
                    v = StopRaceTests.started()
                    v.scene_playing[0] = True
                    tickets = []

                    def suspend():
                        ticket = v.run('hm_controller', 'SuspendAdmission')
                        tickets.append(ticket)
                        self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', ticket))
                        self.assertFalse(v.run('hm_controller', 'ResumeAdmission', ticket))

                    hits = self.inject_once(v, 'method', lambda obj, name, args: (
                        point == 'scene' and name == 'isplaying'
                        or point == 'vanilla' and name == 'stopallsongs'
                        or point == 'idle' and name == 'playidle' and args == ['IdleLuteStart']
                    ), suspend, after=after)
                    v.run('hm_controller', 'CheckVanillaScenes')
                    self.assertTrue(hits)
                    self.assertTrue(v.run('hm_controller', 'IsAdmissionDrained', tickets[0]))
                    self.assertEqual([e for e in v.effects if e[0] == 'idle'][-1], ('idle', 'Mikael', 'IdleStop'))
                    self.assertEqual(v.effects.count(('stop', 1001)), 1)
                    self.assertEqual(len(v.receipts), 1)

    def test_suspension_during_stop_keeps_first_outcome_and_waits_for_receipt(self):
        v = StopRaceTests.started()
        tickets = []

        def suspend():
            ticket = v.run('hm_controller', 'SuspendAdmission')
            tickets.append(ticket)
            self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', ticket))
            self.assertFalse(v.run('hm_controller', 'ResumeAdmission', ticket))

        self.inject_once(v, 'method', lambda obj, name, args: name == 'appendreceipt', suspend)
        v.run('hm_controller', 'StopPerformance', 'completed')
        self.assertEqual([r['outcome'] for r in v.receipts], ['completed'])
        self.assertTrue(v.run('hm_controller', 'IsAdmissionDrained', tickets[0]))
        self.assertEqual(v.effects.count(('stop', 1001)), 1)

    def test_load_with_held_ticket_fails_closed_without_faking_a_drain(self):
        v = VM()
        ticket = v.run('hm_controller', 'SuspendAdmission')
        state = v.state['hm_controller']
        state['busy'] = True  # Persisted unknown stack; do not reset as evidence.
        v.run('hm_controller', 'OnPlayerLoadGame')
        self.assertTrue(state['busy'])
        self.assertTrue(state['admissionsuspended'])
        self.assertTrue(state['admissionunsafe'])
        self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', ticket))
        self.assertFalse(v.run('hm_controller', 'ResumeAdmission', ticket))
        self.assertEqual(v.run('hm_controller', 'SuspendAdmission'), 0)
        v.run('hm_controller', 'StartPerformance', 'Sven', 'sven', 'whiterun', 2)
        self.assertFalse(any(e[0] == 'play' for e in v.effects))

    def test_ticket_or_work_epoch_exhaustion_cannot_reuse_an_old_capability(self):
        for field in ('suspensionserial', 'workepoch'):
            with self.subTest(field=field):
                v = VM()
                v.state['hm_controller'][field] = 2147483646
                ticket = v.run('hm_controller', 'SuspendAdmission')
                self.assertTrue(v.state['hm_controller']['admissionunsafe'])
                self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', ticket))
                self.assertFalse(v.run('hm_controller', 'ResumeAdmission', ticket))

    def test_suspension_arriving_inside_load_is_not_a_valid_new_process_ticket(self):
        v = VM()
        tickets = []
        self.inject_once(v, 'method', lambda obj, name, args: name == 'unregisterforupdate',
                         lambda: tickets.append(v.run('hm_controller', 'SuspendAdmission')))
        v.run('hm_controller', 'OnPlayerLoadGame')
        self.assertEqual(tickets, [0])
        self.assertTrue(v.state['hm_controller']['admissionsuspended'])
        self.assertTrue(v.state['hm_controller']['admissionunsafe'])
        self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', 0))
        self.assertFalse(v.run('hm_controller', 'ResumeAdmission', 0))

    def test_load_during_native_scan_preserves_unknown_ownership_instead_of_resetting_busy(self):
        v = VM()
        v.state['hm_library']['locked'][0] = True
        v.state['hm_controller']['lastrealtime'] = 200.0

        def load_and_suspend():
            v.run('hm_controller', 'OnPlayerLoadGame')
            self.assertTrue(v.state['hm_controller']['busy'])
            self.assertTrue(v.state['hm_controller']['admissionunsafe'])
            self.assertTrue(v.state['hm_library']['locked'][0])
            ticket = v.run('hm_controller', 'SuspendAdmission')
            self.assertEqual(ticket, 0)
            self.assertFalse(v.run('hm_controller', 'IsAdmissionDrained', ticket))
            self.assertFalse(v.run('hm_controller', 'ResumeAdmission', ticket))

        hits = self.inject_once(v, 'static',
            lambda owner, name, args: (owner, name) == ('miscutil', 'scancellnpcs'), load_and_suspend)
        v.enter()
        v.advance(15)
        self.assertTrue(hits)
        self.assertFalse(v.state['hm_controller']['busy'])  # Its real stack returned.
        self.assertTrue(v.state['hm_controller']['admissionunsafe'])
        self.assertTrue(v.state['hm_library']['locked'][0])
        self.assertFalse(any(e[0] == 'play' for e in v.effects))

    def test_suspension_is_refused_until_first_real_initialization_finishes(self):
        attempts = []

        class InitVM(VM):
            def method(self, obj, name, args):
                if name == 'resetsession' and not attempts:
                    ticket = self.run('hm_controller', 'SuspendAdmission')
                    attempts.append((ticket, self.run('hm_controller', 'IsAdmissionDrained', ticket)))
                return super().method(obj, name, args)

        v = InitVM()
        self.assertEqual(attempts, [(0, False)])
        self.assertTrue(v.state['hm_controller']['admissioninitialized'])
        ticket = v.run('hm_controller', 'SuspendAdmission')
        self.assertGreater(ticket, 0)
        self.assertTrue(v.run('hm_controller', 'IsAdmissionDrained', ticket))
        self.assertTrue(v.run('hm_controller', 'ResumeAdmission', ticket))
        # Simulate a saved quest predating this variable, without resetting
        # other normal controller behavior or inventing an initialization call.
        v.state['hm_controller']['admissioninitialized'] = False
        self.assertEqual(v.run('hm_controller', 'SuspendAdmission'), 0)
        self.assertFalse(v.state['hm_controller']['admissionsuspended'])
        v.enter()
        v.advance(15)
        self.assertIn(('play', 1, 'Mikael'), v.effects)


class TraceContractTests(unittest.TestCase):
    def test_all_emitted_event_names_match_frozen_contract(self):
        source=Path(__file__).resolve().parents[1]/'src/Scripts/Source'
        text='\n'.join(p.read_text() for p in source.glob('*.psc'))
        emitted=set(re.findall(r'(?<!Debug\.)\b(?:Trace|AppendTraceEntry)\("([^"\n]+)"',text))
        self.assertEqual(emitted,TRACE_EVENTS)

if __name__=='__main__': unittest.main()
