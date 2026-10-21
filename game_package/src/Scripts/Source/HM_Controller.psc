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
; Cooperative, process-local admission hold. A positive ticket is ownership,
; not proof that Skyrim's other controllers or actors are quiescent.
Bool AdmissionSuspended = False
Bool AdmissionUnsafe = False
Int SuspensionSerial = 0
Int SuspensionTicket = 0
Int WorkEpoch = 0
Int LocationWork = 0
Bool Scheduling = False
Bool SceneWork = False
Bool Loading = False
Bool AdmissionInitialized = False
Bool Initializing = False
String[] RecentPerformers
Float[] RecentTimes
Int RecentCount = 0

Event OnInit()
    If Initializing || AdmissionInitialized
        Return
    EndIf
    Initializing = True
    Library.ResetSession()
    RecentPerformers = new String[128]
    RecentTimes = new Float[128]
    AdmissionInitialized = True
    Initializing = False
EndEvent

Event OnPlayerLoadGame()
    If Loading
        AdmissionUnsafe = True
        Return
    EndIf
    Loading = True
    If AdmissionSuspended || AdmissionUnsafe || Busy || Starting || Stopping || LocationWork > 0 || Scheduling || SceneWork
        ; A serialized ticket/counter/sound handle cannot establish that old
        ; native calls drained in this process. Preserve the hold, fail closed,
        ; and require a fresh-world test; never acknowledge a reset as cleanup.
        AdmissionUnsafe = True
        UnregisterForUpdate()
        Loading = False
        Return
    EndIf
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
    Loading = False
EndEvent

Int Function SuspendAdmission()
    ; Old saved quest instances do not acquire this readiness flag by magic.
    ; Refuse the new protocol until actual first initialization has returned.
    If !AdmissionInitialized || Initializing || AdmissionSuspended || AdmissionUnsafe
        Return 0
    EndIf
    AdmissionSuspended = True
    If Loading
        ; A request arriving inside the preexisting load cleanup cannot turn
        ; serialized ownership into a current-process drain acknowledgment.
        AdmissionUnsafe = True
        Return 0
    EndIf
    If SuspensionSerial >= 2147483646
        AdmissionUnsafe = True
        StopPerformance("interrupted")
        Return 0
    EndIf
    SuspensionSerial += 1
    SuspensionTicket = SuspensionSerial
    Int ticket = SuspensionTicket
    ; Claim before StopPerformance or UnregisterForUpdate can yield. Startup
    ; may only queue cancellation here; acknowledgment remains false until its
    ; late idle/audio result has been compensated by the owning start stack.
    StopPerformance("interrupted")
    Return ticket
EndFunction

Bool Function IsAdmissionDrained(Int ticket)
    ; Read only, no native calls. Counters remain owned until real returns.
    Return ticket > 0 && ticket == SuspensionTicket && AdmissionSuspended && AdmissionInitialized && !Initializing && !AdmissionUnsafe && !Busy && !Starting && !Stopping && !Performer && Instance < 0 && LocationWork == 0 && !Scheduling && !SceneWork && !Loading
EndFunction

Bool Function ResumeAdmission(Int ticket)
    ; Inline the snapshot: no yielding helper between validation and release.
    If ticket <= 0 || ticket != SuspensionTicket || !AdmissionSuspended || !AdmissionInitialized || Initializing || AdmissionUnsafe || Busy || Starting || Stopping || Performer || Instance >= 0 || LocationWork != 0 || Scheduling || SceneWork || Loading
        Return False
    EndIf
    SuspensionTicket = 0
    AdmissionSuspended = False
    ; No scheduling, idle, playback, or global-setting changes on resume.
    Return True
EndFunction

Function InvalidateWork()
    If WorkEpoch >= 2147483646
        AdmissionUnsafe = True
    Else
        WorkEpoch += 1
    EndIf
EndFunction

Bool Function WorkAllowed(Int expectedEpoch)
    Return !AdmissionSuspended && !AdmissionUnsafe && !Loading && expectedEpoch == WorkEpoch
EndFunction

Event OnLocationChange(Location akOldLoc, Location akNewLoc)
    LocationWork += 1
    InvalidateWork()
    Int expectedEpoch = WorkEpoch
    HandleLocationChange(akOldLoc, akNewLoc, expectedEpoch)
    LocationWork -= 1
EndEvent

Function HandleLocationChange(Location akOldLoc, Location akNewLoc, Int expectedEpoch)
    If !WorkAllowed(expectedEpoch)
        Return
    EndIf
    UnregisterForUpdate()
    If !WorkAllowed(expectedEpoch)
        Return
    EndIf
    ; Trace only inn transitions: the ring holds 300 entries and ordinary
    ; travel changes location constantly.
    If akOldLoc && akOldLoc != akNewLoc && akOldLoc.HasKeyword(LocTypeInn)
        Library.Trace("location_leave", "")
    EndIf
    Bool inn = akNewLoc && akNewLoc.HasKeyword(LocTypeInn)
    If !WorkAllowed(expectedEpoch)
        Return
    EndIf
    If inn
        Library.Trace("location_enter", "inn=true")
        If HM_Enabled.GetValue() == 0.0
            Library.Trace("disabled", "")
        EndIf
    EndIf
    If !WorkAllowed(expectedEpoch)
        Return
    EndIf
    If Performer && akNewLoc != Venue
        StopPerformance("interrupted")
        expectedEpoch = WorkEpoch
    EndIf
    If !WorkAllowed(expectedEpoch)
        Return
    EndIf
    If HM_Enabled.GetValue() == 0.0 || !akNewLoc || !akNewLoc.HasKeyword(LocTypeInn)
        StopPerformance("interrupted")
        Return
    EndIf
    If !WorkAllowed(expectedEpoch)
        Return
    EndIf
    If !Performer
        Config.StopRequested = False
        Venue = akNewLoc
        ScheduleCheck()
    Else
        RegisterOwnedUpdate(2.0)
    EndIf
EndFunction

Function ScheduleCheck()
    If Scheduling || AdmissionSuspended || AdmissionUnsafe || Loading || Starting || Stopping
        Return
    EndIf
    Scheduling = True
    Int expectedEpoch = WorkEpoch
    ScheduleCheckOwned(expectedEpoch)
    Scheduling = False
EndFunction

Function ScheduleCheckOwned(Int expectedEpoch)
    If !Scheduling || !WorkAllowed(expectedEpoch) || Starting || Stopping
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
    Float delay = Utility.RandomFloat(low, high)
    If !WorkAllowed(expectedEpoch)
        Return
    EndIf
    RegisterForSingleUpdate(delay)
    If !WorkAllowed(expectedEpoch)
        ; The old native registration may return after a stop unregistered it.
        ; Keep Scheduling claimed through compensation, preventing resume.
        UnregisterForUpdate()
    EndIf
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
    Actor observedPerformer = Performer
    Location observedVenue = Venue
    If HM_Enabled.GetValue() == 0.0
        Return "disabled"
    ElseIf Config.StopRequested
        Return "stop_requested"
    EndIf
    String failure = EligibilityFailure(observedPerformer)
    If failure != ""
        Return failure
    ElseIf Game.GetPlayer().GetCurrentLocation() != observedVenue
        Return "venue_changed"
    ElseIf observedPerformer.GetParentCell() != Game.GetPlayer().GetParentCell()
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
    If Busy || Starting || Stopping || AdmissionSuspended || AdmissionUnsafe || Loading
        Return
    EndIf
    Busy = True
    Int expectedEpoch = WorkEpoch
    UpdateOwned(expectedEpoch)
    Busy = False
EndEvent

Function UpdateOwned(Int expectedEpoch)
    If !Busy || !WorkAllowed(expectedEpoch)
        Return
    EndIf
    If HM_Enabled.GetValue() == 0.0
        Library.Trace("disabled", "")
    ElseIf !Performer && SessionCount >= HM_SessionCap.GetValue()
        Library.Trace("session_cap", "")
    EndIf
    If !WorkAllowed(expectedEpoch)
        Return
    EndIf
    If Performer
        CheckVanillaScenes()
        If !WorkAllowed(expectedEpoch) || !Performer
            Return
        EndIf
        String interruption = PollInterruptionReason()
        If !WorkAllowed(expectedEpoch) || !Performer
            Return
        EndIf
        If interruption != ""
            Library.Trace("performance_interrupt_guard", FailureState(Performer, PerformerId, Slot, interruption))
            If !WorkAllowed(expectedEpoch)
                Return
            EndIf
            StopPerformance("interrupted")
        Else
            Float now = Utility.GetCurrentRealTime()
            If !WorkAllowed(expectedEpoch) || !Performer
                Return
            EndIf
            If now >= Ends
                StopPerformance("completed")
                ScheduleCheck()
            Else
                Poll()
            EndIf
        EndIf
    ElseIf HM_Enabled.GetValue() != 0.0 && SessionCount < HM_SessionCap.GetValue() && Venue && Game.GetPlayer().GetCurrentLocation() == Venue && Venue.HasKeyword(LocTypeInn) && !Config.StopRequested
        If !WorkAllowed(expectedEpoch)
            Return
        EndIf
        Library.Trace("check_start", "venue=" + Venue.GetFormID())
        If !WorkAllowed(expectedEpoch)
            Return
        EndIf
        ; PapyrusUtil VR 3.6's IgnoreDead=True branch dispatches the wrong
        ; actor vtable slot (0x99), reaching CellChange instead of IsDead.
        ; Include corpses here; Eligible() uses Skyrim's native IsDead()
        ; before any scene, idle or sound changes. See the 2026-10-15 RCA.
        Actor[] candidates = MiscUtil.ScanCellNPCs(Game.GetPlayer(), 2000.0, None, False)
        If !WorkAllowed(expectedEpoch)
            Return
        EndIf
        Int i = 0
        Int matched = 0
        While i < candidates.Length && !Performer && WorkAllowed(expectedEpoch)
            Actor candidate = candidates[i]
            String id = Library.FindPerformer(candidate)
            If !WorkAllowed(expectedEpoch)
                Return
            EndIf
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
                If !WorkAllowed(expectedEpoch)
                    Return
                EndIf
                String traceRegion = region
                If traceRegion == ""
                    traceRegion = "none"
                EndIf
                Library.Trace("candidate", "id=" + id + " owner=" + owner + " eligible=" + BoolText(allowed) + " region=" + traceRegion + " cooled=" + BoolText(cooled))
                If !WorkAllowed(expectedEpoch)
                    Return
                EndIf
                If ours && allowed && region != "" && cooled
                    String mode = "vocal"
                    If Utility.RandomInt(1, 100) <= HM_InstrumentalPercent.GetValue()
                        mode = "instrumental"
                    EndIf
                    If !WorkAllowed(expectedEpoch)
                        Return
                    EndIf
                    Int chosen = Library.ChooseSlot(id, region, mode)
                    If !WorkAllowed(expectedEpoch)
                        Return
                    EndIf
                    If chosen > 0 && SlotSounds.Length == 24 && SlotSounds[chosen - 1]
                        Library.Trace("slot_chosen", "id=" + id + " slot=" + chosen + " mode=" + mode)
                        ; Pass the scan's epoch into the start admission guard;
                        ; a stop at the last scripted-call boundary is not lost.
                        StartSelectedPerformance(candidate, id, region, chosen, expectedEpoch)
                    EndIf
                EndIf
            EndIf
            i += 1
        EndWhile
        If !Performer && WorkAllowed(expectedEpoch)
            Library.Trace("no_performer", "scanned=" + i + " matched=" + matched)
        EndIf
        ; No performer/recording: remain idle until the next location entry.
    EndIf
EndFunction

Function StartPerformance(Actor candidate, String id, String region, Int chosen)
    ; Preserve the four-argument external API. Claim before entering the shared
    ; implementation so a yielding scripted-call boundary is also accounted.
    If Starting || Stopping || Performer || AdmissionSuspended || AdmissionUnsafe || Loading || Scheduling || SceneWork || LocationWork > 0
        Return
    EndIf
    Starting = True
    StartCancelled = False
    StartStopOutcome = ""
    Int startEpoch = WorkEpoch
    StartClaimedPerformance(candidate, id, region, chosen, startEpoch)
EndFunction

Function StartSelectedPerformance(Actor candidate, String id, String region, Int chosen, Int expectedEpoch)
    ; Claim admission before any call can yield. A stop during startup queues
    ; cancellation; this stack retains ownership until late native calls drain.
    If Starting || Stopping || Performer || AdmissionSuspended || AdmissionUnsafe || Loading || Scheduling || SceneWork || LocationWork > 0
        Return
    EndIf
    If expectedEpoch != WorkEpoch
        Return
    EndIf
    Starting = True
    StartCancelled = False
    StartStopOutcome = ""
    StartClaimedPerformance(candidate, id, region, chosen, expectedEpoch)
EndFunction

Function StartClaimedPerformance(Actor candidate, String id, String region, Int chosen, Int startEpoch)
    If !Starting
        Return
    EndIf
    If StartWasCancelled(startEpoch)
        EndStartWithoutPlayback(candidate, False)
        Return
    EndIf
    BardSongsScript vanilla = BardSongsQuest as BardSongsScript
    If vanilla
        vanilla.StopAllSongs()
        If StartWasCancelled(startEpoch)
            EndStartWithoutPlayback(candidate, False)
            Return
        EndIf
        Library.Trace("vanilla_stopped", "")
    Else
        Library.Trace("vanilla_unavailable", "")
    EndIf
    If StartWasCancelled(startEpoch)
        EndStartWithoutPlayback(candidate, False)
        Return
    EndIf
    Bool idleAccepted = candidate.PlayIdle(IdleLuteStart)
    If StartWasCancelled(startEpoch)
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
    If StartWasCancelled(startEpoch)
        EndStartWithoutPlayback(candidate, True)
        Return
    EndIf
    Remember(id)
    If StartWasCancelled(startEpoch)
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
    If !StartWasCancelled(startEpoch)
        Library.Trace("performance_start", "id=" + id + " slot=" + chosen + " duration=" + duration)
    EndIf
    If !StartWasCancelled(startEpoch)
        Poll()
    EndIf
    If StartWasCancelled(startEpoch)
        ; Transfer ownership without opening admission between startup and
        ; cleanup. Never leave a late Sound.Play result alive after cancellation.
        Stopping = True
        Starting = False
        FinishClaimedStop(StartStopOutcome)
    Else
        Starting = False
    EndIf
EndFunction

Bool Function StartWasCancelled(Int expectedEpoch)
    If !WorkAllowed(expectedEpoch)
        If !StartCancelled
            StartCancelled = True
            StartStopOutcome = "interrupted"
        EndIf
    EndIf
    Return StartCancelled
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
    If Scheduling || AdmissionSuspended || AdmissionUnsafe || Loading
        Return
    EndIf
    Scheduling = True
    Int expectedEpoch = WorkEpoch
    Float remaining = Ends - Utility.GetCurrentRealTime()
    If remaining > 2.0
        remaining = 2.0
    ElseIf remaining < 0.1
        remaining = 0.1
    EndIf
    If WorkAllowed(expectedEpoch)
        RegisterForSingleUpdate(remaining)
        If !WorkAllowed(expectedEpoch)
            UnregisterForUpdate()
        EndIf
    EndIf
    Scheduling = False
EndFunction

Function RegisterOwnedUpdate(Float delay)
    If Scheduling || AdmissionSuspended || AdmissionUnsafe || Loading
        Return
    EndIf
    Scheduling = True
    Int expectedEpoch = WorkEpoch
    RegisterForSingleUpdate(delay)
    If !WorkAllowed(expectedEpoch)
        UnregisterForUpdate()
    EndIf
    Scheduling = False
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
        InvalidateWork()
        Return
    EndIf
    Stopping = True
    InvalidateWork()
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
    If SceneWork || AdmissionSuspended || AdmissionUnsafe || Loading || !Performer
        Return
    EndIf
    SceneWork = True
    Int expectedEpoch = WorkEpoch
    Actor observedPerformer = Performer
    CheckVanillaScenesOwned(observedPerformer, expectedEpoch)
    SceneWork = False
EndFunction

Function CheckVanillaScenesOwned(Actor observedPerformer, Int expectedEpoch)
    If !SceneWork || !observedPerformer || !WorkAllowed(expectedEpoch)
        Return
    EndIf
    Int i = 0
    While i < VanillaScenes.Length
        Bool playing = VanillaScenes[i] && VanillaScenes[i].IsPlaying()
        If !WorkAllowed(expectedEpoch) || Performer != observedPerformer
            Return
        EndIf
        If playing
            BardSongsScript vanilla = BardSongsQuest as BardSongsScript
            If vanilla
                vanilla.StopAllSongs()
                If !WorkAllowed(expectedEpoch) || Performer != observedPerformer
                    Return
                EndIf
                Bool accepted = observedPerformer.PlayIdle(IdleLuteStart)
                If !WorkAllowed(expectedEpoch) || Performer != observedPerformer
                    ; A late idle reassertion is still ours to compensate. No
                    ; replacement start/resume may enter while SceneWork owns it.
                    If accepted
                        observedPerformer.PlayIdle(IdleStop)
                    EndIf
                    Return
                EndIf
                Library.Trace("vanilla_restarted", "scene=" + i)
            Else
                Library.Trace("vanilla_unavailable", "")
            EndIf
        EndIf
        If !WorkAllowed(expectedEpoch)
            Return
        EndIf
        i += 1
    EndWhile
EndFunction
