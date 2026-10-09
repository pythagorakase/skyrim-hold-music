Scriptname HM_Controller extends ReferenceAlias

HM_Library Property Library Auto
HM_Config Property Config Auto
Keyword Property LocTypeInn Auto
Faction Property CurrentFollowerFaction Auto
Idle Property IdleLuteStart Auto
Idle Property IdleStop Auto
Sound[] Property SlotSounds Auto
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
    If HM_Enabled.GetValue() == 0.0 || SessionCount >= HM_SessionCap.GetValue() || Performer
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
    If Performer
        If HM_Enabled.GetValue() == 0.0 || Config.StopRequested || !Eligible(Performer) || Game.GetPlayer().GetCurrentLocation() != Venue || Performer.GetParentCell() != Game.GetPlayer().GetParentCell()
            StopPerformance("interrupted")
        ElseIf Utility.GetCurrentRealTime() >= Ends
            StopPerformance("completed")
            ScheduleCheck()
        Else
            Poll()
        EndIf
    ElseIf HM_Enabled.GetValue() != 0.0 && SessionCount < HM_SessionCap.GetValue() && Venue && Game.GetPlayer().GetCurrentLocation() == Venue && Venue.HasKeyword(LocTypeInn) && !Config.StopRequested
        Actor[] candidates = MiscUtil.ScanCellNPCs(Game.GetPlayer(), 2000.0, None, True)
        Int i = 0
        While i < candidates.Length && !Performer
            Actor candidate = candidates[i]
            If Eligible(candidate)
                String id = Library.FindPerformer(candidate)
                If id != "" && Library.Region(id) != "" && CooledDown(id)
                    String region = Library.Region(id)
                    String mode = "vocal"
                    If Utility.RandomInt(1, 100) <= HM_InstrumentalPercent.GetValue()
                        mode = "instrumental"
                    EndIf
                    Int chosen = Library.ChooseSlot(id, region, mode)
                    If chosen > 0 && SlotSounds.Length == 24 && SlotSounds[chosen - 1]
                        StartPerformance(candidate, id, region, chosen)
                    EndIf
                EndIf
            EndIf
            i += 1
        EndWhile
        ; No performer/recording: remain idle until the next location entry.
    EndIf
    Busy = False
EndEvent

Function StartPerformance(Actor candidate, String id, String region, Int chosen)
    If !candidate.PlayIdle(IdleLuteStart)
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
        Library.AppendReceipt(Slot, PerformerId, PerformanceRegion, Started, outcome, Config.WorldId)
    EndIf
    Performer = None
    Instance = -1
    Slot = 0
    Config.StopRequested = False
EndFunction
