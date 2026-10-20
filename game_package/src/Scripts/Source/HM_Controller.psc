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
    If HM_Enabled.GetValue() == 0.0
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
    Return candidate && candidate.Is3DLoaded() && !candidate.IsDead() && !candidate.IsInCombat() && !candidate.IsInDialogueWithPlayer() && !candidate.IsInFaction(CurrentFollowerFaction) && candidate.GetSitState() == 0 && candidate.GetSleepState() == 0
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
    If Busy
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
        If HM_Enabled.GetValue() == 0.0 || Config.StopRequested || !Eligible(Performer) || Game.GetPlayer().GetCurrentLocation() != Venue || Performer.GetParentCell() != Game.GetPlayer().GetParentCell()
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
    BardSongsScript vanilla = BardSongsQuest as BardSongsScript
    If vanilla
        vanilla.StopAllSongs()
        Library.Trace("vanilla_stopped", "")
    Else
        Library.Trace("vanilla_unavailable", "")
    EndIf
    If !candidate.PlayIdle(IdleLuteStart)
        Library.Trace("idle_failed", "id=" + id + " slot=" + chosen)
        Return
    EndIf
    Performer = candidate
    PerformerId = id
    PerformanceRegion = region
    Slot = chosen
    Library.LockSlot(chosen)
    Started = Utility.GetCurrentRealTime()
    LastRealTime = Started
    Ends = Started + Library.Duration()
    SessionCount += 1
    Remember(id)
    Instance = SlotSounds[chosen - 1].Play(candidate)
    If Instance < 0
        StopPerformance("interrupted")
    Else
        Library.Trace("performance_start", "id=" + id + " slot=" + chosen + " duration=" + Library.Duration())
        Poll()
    EndIf
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
    UnregisterForUpdate()
    If Performer
        If Instance >= 0
            Sound.StopInstance(Instance)
        EndIf
        Performer.PlayIdle(IdleStop)
        Library.Trace("performance_stop", "outcome=" + outcome + " id=" + PerformerId + " slot=" + Slot)
        Library.AppendReceipt(Slot, PerformerId, PerformanceRegion, Started, outcome, Config.WorldId)
    EndIf
    Performer = None
    Instance = -1
    Slot = 0
    Config.StopRequested = False
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
