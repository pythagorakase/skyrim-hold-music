Scriptname HM_Controller extends ReferenceAlias

HM_Library Property Library Auto
HM_Config Property Config Auto
Keyword Property LocTypeInn Auto
Faction Property CurrentFollowerFaction Auto
Idle Property IdleLuteStart Auto
Idle Property IdleStop Auto
Sound[] Property SlotSounds Auto
Quest Property BardSongsQuest Auto
Scene[] Property VanillaScenes Auto
GlobalVariable Property HM_Enabled Auto
GlobalVariable Property HM_InstrumentalPercent Auto
GlobalVariable Property HM_SessionCap Auto
GlobalVariable Property HM_MinDelaySeconds Auto
GlobalVariable Property HM_MaxDelaySeconds Auto

Actor Performer
Location Venue
String PerformerId
String PerformanceRegion
Int Slot = 0
Int Instance = -1
Float Started = 0.0
Float LastRealTime = 0.0
Float Ends = 0.0
Int SessionCount = 0
Bool Busy = False
Bool Starting = False
Bool Stopping = False
Bool StartCancelled = False
String StartStopOutcome = ""
String[] RecentPerformers
Float[] RecentTimes
Int RecentCount = 0

Event OnInit()
    Library.ResetSession()
    RecentPerformers = new String[128]
    RecentTimes = new Float[128]
EndEvent

Event OnPlayerLoadGame()
    UnregisterForUpdate()
    StopPerformance("interrupted")
    SessionCount = 0
    Busy = False
    Config.StopRequested = False
    Float now = Utility.GetCurrentRealTime()
    ; Cached WAV buffers survive save loads, but cannot survive a process restart.
    If now < LastRealTime
        Library.ResetSession()
    EndIf
    LastRealTime = now
    ; Conservatively restart cooldowns on every load.
    Int i = 0
    While i < RecentCount
        RecentTimes[i] = Utility.GetCurrentRealTime()
        i += 1
    EndWhile
EndEvent

Event OnLocationChange(Location akOldLoc, Location akNewLoc)
    UnregisterForUpdate()
    ; Trace only inn transitions: the ring holds 300 entries and ordinary
    ; travel changes location constantly.
    If akOldLoc && akOldLoc != akNewLoc && akOldLoc.HasKeyword(LocTypeInn)
        Library.Trace("location_leave", "")
    EndIf
    Bool inn = akNewLoc && akNewLoc.HasKeyword(LocTypeInn)
    If inn
        Library.Trace("location_enter", "inn=true")
        If HM_Enabled.GetValue() == 0.0
            Library.Trace("disabled", "")
        EndIf
    EndIf
    If Performer && akNewLoc != Venue
        StopPerformance("interrupted")
    EndIf
    If HM_Enabled.GetValue() == 0.0 || !akNewLoc || !akNewLoc.HasKeyword(LocTypeInn)
        StopPerformance("interrupted")
        Return
    EndIf
    If !Performer
        Config.StopRequested = False
        Venue = akNewLoc
        ScheduleCheck()
    Else
        RegisterForSingleUpdate(2.0)
    EndIf
EndEvent

Function ScheduleCheck()
    If Starting || Stopping
        Return
    ElseIf HM_Enabled.GetValue() == 0.0
        Library.Trace("disabled", "")
        Return
    ElseIf SessionCount >= HM_SessionCap.GetValue()
        Library.Trace("session_cap", "")
        Return
    ElseIf Performer
        Return
    EndIf
    Float low = HM_MinDelaySeconds.GetValue()
    Float high = HM_MaxDelaySeconds.GetValue()
    If low < 0.1
        low = 0.1
    EndIf
    If high < low
        high = low
    EndIf
    RegisterForSingleUpdate(Utility.RandomFloat(low, high))
EndFunction

Bool Function Eligible(Actor candidate)
    ; Reject all furniture transitions/sitting and sleep states. This is a
    ; conservative cheap check, not a package graph inspection.
    Return EligibilityFailure(candidate) == ""
EndFunction

String Function EligibilityFailure(Actor candidate)
    ; Preserve the original short-circuit order and acceptance criteria.
    If !candidate
        Return "actor_missing"
    ElseIf !candidate.Is3DLoaded()
        Return "actor_unloaded"
    ElseIf candidate.IsDead()
        Return "actor_dead"
    ElseIf candidate.IsInCombat()
        Return "actor_combat"
    ElseIf candidate.IsInDialogueWithPlayer()
        Return "actor_dialogue"
    ElseIf candidate.IsInFaction(CurrentFollowerFaction)
        Return "actor_follower"
    ElseIf candidate.GetSitState() != 0
        Return "actor_sit"
    ElseIf candidate.GetSleepState() != 0
        Return "actor_sleep"
    EndIf
    Return ""
EndFunction

String Function PollInterruptionReason()
    If HM_Enabled.GetValue() == 0.0
        Return "disabled"
    ElseIf Config.StopRequested
        Return "stop_requested"
    EndIf
    String failure = EligibilityFailure(Performer)
    If failure != ""
        Return failure
    ElseIf Game.GetPlayer().GetCurrentLocation() != Venue
        Return "venue_changed"
    ElseIf Performer.GetParentCell() != Game.GetPlayer().GetParentCell()
        Return "cell_changed"
    EndIf
    Return ""
EndFunction

String Function FailureState(Actor candidate, String id, Int chosen, String reason)
    ; Event-only snapshot, not an animation or AI diagnosis. The triggering
    ; guard reason is captured first; native actor state may change afterward.
    String detail = "id=" + id + " slot=" + chosen + " reason=" + reason
    detail += " enabled=" + HM_Enabled.GetValue() + " stop_requested=" + (Config.StopRequested as Int)
    detail += " venue_match=" + ((Game.GetPlayer().GetCurrentLocation() == Venue) as Int)
    detail += " actor_present=" + ((candidate != None) as Int)
    If candidate
        detail += " loaded=" + (candidate.Is3DLoaded() as Int) + " dead=" + (candidate.IsDead() as Int)
        detail += " combat=" + (candidate.IsInCombat() as Int) + " dialogue=" + (candidate.IsInDialogueWithPlayer() as Int)
        detail += " follower=" + (candidate.IsInFaction(CurrentFollowerFaction) as Int)
        detail += " sit=" + candidate.GetSitState() + " sleep=" + candidate.GetSleepState()
        detail += " same_cell=" + ((candidate.GetParentCell() == Game.GetPlayer().GetParentCell()) as Int)
    EndIf
    Int playing = 0
    Int i = 0
    While i < VanillaScenes.Length
        If VanillaScenes[i] && VanillaScenes[i].IsPlaying()
            playing += 1
        EndIf
        i += 1
    EndWhile
    Return detail + " vanilla_scenes_playing=" + playing
EndFunction

Bool Function CooledDown(String id)
    Int i = 0
    While i < RecentCount
        If RecentPerformers[i] == id
            Return Utility.GetCurrentRealTime() - RecentTimes[i] >= 1800.0
        EndIf
        i += 1
    EndWhile
    Return True
EndFunction

Function Remember(String id)
    If !RecentPerformers
        RecentPerformers = new String[128]
        RecentTimes = new Float[128]
    EndIf
    Int i = 0
    Int oldest = 0
    While i < RecentCount
        If RecentPerformers[i] == id
            RecentTimes[i] = Utility.GetCurrentRealTime()
            Return
        EndIf
        If RecentTimes[i] < RecentTimes[oldest]
            oldest = i
        EndIf
        i += 1
    EndWhile
    If RecentCount < 128
        oldest = RecentCount
        RecentCount += 1
    EndIf
    RecentPerformers[oldest] = id
    RecentTimes[oldest] = Utility.GetCurrentRealTime()
EndFunction

Event OnUpdate()
    ; A direct harness/event stop need not own Busy. Do not select another
    ; recording while cleanup still reads the library's active selection.
    If Busy || Starting || Stopping
        Return
    EndIf
    Busy = True
    If HM_Enabled.GetValue() == 0.0
        Library.Trace("disabled", "")
    ElseIf !Performer && SessionCount >= HM_SessionCap.GetValue()
        Library.Trace("session_cap", "")
    EndIf
    If Performer
        CheckVanillaScenes()
        String interruption = PollInterruptionReason()
        If interruption != ""
            Library.Trace("performance_interrupt_guard", FailureState(Performer, PerformerId, Slot, interruption))
            StopPerformance("interrupted")
        ElseIf Utility.GetCurrentRealTime() >= Ends
            StopPerformance("completed")
            ScheduleCheck()
        Else
            Poll()
        EndIf
    ElseIf HM_Enabled.GetValue() != 0.0 && SessionCount < HM_SessionCap.GetValue() && Venue && Game.GetPlayer().GetCurrentLocation() == Venue && Venue.HasKeyword(LocTypeInn) && !Config.StopRequested
        Library.Trace("check_start", "venue=" + Venue.GetFormID())
        ; PapyrusUtil VR 3.6's IgnoreDead=True branch dispatches the wrong
        ; actor vtable slot (0x99), reaching CellChange instead of IsDead.
        ; Include corpses here; Eligible() uses Skyrim's native IsDead()
        ; before any scene, idle or sound changes. See the 2026-10-15 RCA.
        Actor[] candidates = MiscUtil.ScanCellNPCs(Game.GetPlayer(), 2000.0, None, False)
        Int i = 0
        Int matched = 0
        While i < candidates.Length && !Performer
            Actor candidate = candidates[i]
            String id = Library.FindPerformer(candidate)
            If id != ""
                matched += 1
                String owner = Library.Owner(id)
                Bool ours = owner == "hold_music"
                If !ours
                    owner = "skyrimnet"
                EndIf
                Bool allowed = Eligible(candidate)
                Bool cooled = CooledDown(id)
                String region = Library.Region(id)
                String traceRegion = region
                If traceRegion == ""
                    traceRegion = "none"
                EndIf
                Library.Trace("candidate", "id=" + id + " owner=" + owner + " eligible=" + BoolText(allowed) + " region=" + traceRegion + " cooled=" + BoolText(cooled))
                If ours && allowed && region != "" && cooled
                    String mode = "vocal"
                    If Utility.RandomInt(1, 100) <= HM_InstrumentalPercent.GetValue()
                        mode = "instrumental"
                    EndIf
                    Int chosen = Library.ChooseSlot(id, region, mode)
                    If chosen > 0 && SlotSounds.Length == 24 && SlotSounds[chosen - 1]
                        Library.Trace("slot_chosen", "id=" + id + " slot=" + chosen + " mode=" + mode)
                        StartPerformance(candidate, id, region, chosen)
                    EndIf
                EndIf
            EndIf
            i += 1
        EndWhile
        If !Performer
            Library.Trace("no_performer", "scanned=" + i + " matched=" + matched)
        EndIf
        ; No performer/recording: remain idle until the next location entry.
    EndIf
    Busy = False
EndEvent

Function StartPerformance(Actor candidate, String id, String region, Int chosen)
    ; Claim admission before any call can yield. A stop during startup queues
    ; cancellation; this stack retains ownership until late native calls drain.
    If Starting || Stopping || Performer
        Return
    EndIf
    Starting = True
    StartCancelled = False
    StartStopOutcome = ""
    BardSongsScript vanilla = BardSongsQuest as BardSongsScript
    If vanilla
        vanilla.StopAllSongs()
        If StartCancelled
            EndStartWithoutPlayback(candidate, False)
            Return
        EndIf
        Library.Trace("vanilla_stopped", "")
    Else
        Library.Trace("vanilla_unavailable", "")
    EndIf
    If StartCancelled
        EndStartWithoutPlayback(candidate, False)
        Return
    EndIf
    Bool idleAccepted = candidate.PlayIdle(IdleLuteStart)
    If StartCancelled
        EndStartWithoutPlayback(candidate, idleAccepted)
        Return
    EndIf
    If !idleAccepted
        Library.Trace("idle_failed", "id=" + id + " slot=" + chosen)
        Library.Trace("idle_failed_state", FailureState(candidate, id, chosen, "native_idle_refused"))
        EndStartWithoutPlayback(candidate, False)
        Return
    EndIf
    Library.LockSlot(chosen)
    Float began = Utility.GetCurrentRealTime()
    Float duration = Library.Duration()
    If StartCancelled
        EndStartWithoutPlayback(candidate, True)
        Return
    EndIf
    Remember(id)
    If StartCancelled
        EndStartWithoutPlayback(candidate, True)
        Return
    EndIf
    Performer = candidate
    PerformerId = id
    PerformanceRegion = region
    Slot = chosen
    Started = began
    LastRealTime = Started
    Ends = Started + duration
    SessionCount += 1
    Int startedInstance = SlotSounds[chosen - 1].Play(candidate)
    Instance = startedInstance
    If startedInstance < 0 && !StartCancelled
        StartCancelled = True
        StartStopOutcome = "interrupted"
    EndIf
    If !StartCancelled
        Library.Trace("performance_start", "id=" + id + " slot=" + chosen + " duration=" + duration)
    EndIf
    If !StartCancelled
        Poll()
    EndIf
    If StartCancelled
        ; Transfer ownership without opening admission between startup and
        ; cleanup. Never leave a late Sound.Play result alive after cancellation.
        Stopping = True
        Starting = False
        FinishClaimedStop(StartStopOutcome)
    Else
        Starting = False
    EndIf
EndFunction

Function EndStartWithoutPlayback(Actor candidate, Bool idleAccepted)
    ; Starting remains claimed throughout compensation and native callbacks.
    UnregisterForUpdate()
    If idleAccepted
        candidate.PlayIdle(IdleStop)
    EndIf
    Config.StopRequested = False
    StartCancelled = False
    StartStopOutcome = ""
    Starting = False
EndFunction

Function Poll()
    Float remaining = Ends - Utility.GetCurrentRealTime()
    If remaining > 2.0
        remaining = 2.0
    ElseIf remaining < 0.1
        remaining = 0.1
    EndIf
    RegisterForSingleUpdate(remaining)
EndFunction

Function StopPerformance(String outcome)
    ; First stop wins, before even UnregisterForUpdate can yield. Reentrant
    ; stops must not touch sound, idle, receipts or another operation's timer.
    If Stopping
        Return
    EndIf
    If Starting
        If !StartCancelled
            StartStopOutcome = outcome
            StartCancelled = True
        EndIf
        Return
    EndIf
    Stopping = True
    FinishClaimedStop(outcome)
EndFunction

Function FinishClaimedStop(String outcome)
    ; Called only after admission is claimed, including the startup handoff.
    ; Freeze arguments and detach active fields before native/script calls.
    Actor stoppedPerformer = Performer
    Int stoppedInstance = Instance
    Int stoppedSlot = Slot
    String stoppedId = PerformerId
    String stoppedRegion = PerformanceRegion
    Float stoppedStarted = Started
    String stoppedWorld = Config.WorldId
    Performer = None
    Instance = -1
    Slot = 0
    UnregisterForUpdate()
    If stoppedPerformer
        If stoppedInstance >= 0
            Sound.StopInstance(stoppedInstance)
        EndIf
        stoppedPerformer.PlayIdle(IdleStop)
        Library.Trace("performance_stop", "outcome=" + outcome + " id=" + stoppedId + " slot=" + stoppedSlot)
        Library.AppendReceipt(stoppedSlot, stoppedId, stoppedRegion, stoppedStarted, outcome, stoppedWorld)
    EndIf
    Config.StopRequested = False
    StartCancelled = False
    StartStopOutcome = ""
    Stopping = False
EndFunction

String Function BoolText(Bool value)
    If value
        Return "true"
    EndIf
    Return "false"
EndFunction

Function CheckVanillaScenes()
    Int i = 0
    While i < VanillaScenes.Length
        If VanillaScenes[i] && VanillaScenes[i].IsPlaying()
            BardSongsScript vanilla = BardSongsQuest as BardSongsScript
            If vanilla
                vanilla.StopAllSongs()
                Performer.PlayIdle(IdleLuteStart)
                Library.Trace("vanilla_restarted", "scene=" + i)
            Else
                Library.Trace("vanilla_unavailable", "")
            EndIf
        EndIf
        i += 1
    EndWhile
EndFunction
