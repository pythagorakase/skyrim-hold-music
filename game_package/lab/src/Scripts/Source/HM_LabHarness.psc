Scriptname HM_LabHarness extends Quest

; LAB ONLY. Autorun requires an explicit fresh request with auto_run=true.
; Use a disposable, isolated test save.
; This quest does not replace or override the production controller.
HM_Library Property Library Auto
HM_Config Property Config Auto
Quest Property HoldMusicQuest Auto
GlobalVariable Property HM_Enabled Auto
GlobalVariable Property HM_InstrumentalPercent Auto
GlobalVariable Property HM_SessionCap Auto
GlobalVariable Property HM_MinDelaySeconds Auto
GlobalVariable Property HM_MaxDelaySeconds Auto
Keyword Property LocTypeInn Auto

String ControlFile = "HoldMusicSELab/control.json"
String RequestFile = "HoldMusicSELab/request.json"
String ResultFile = "HoldMusicSELab/result.json"
HM_Controller Controller
Bool Active = False
Bool GlobalsSaved = False
String RunId = ""
String StartedAtUtc = ""
String Scenario = ""
String ExpectedOutcome = "completed"
Float Began = 0.0
Float Deadline = 0.0
Float OldEnabled
Float OldInstrumental
Float OldCap
Float OldMinDelay
Float OldMaxDelay
Int TraceBaseline = 0
Int TraceCursor = 0
Int ReceiptBaseline = 0
Int SelectedSlot = 0
Int ReceiptIndex = -1
String SelectedIdentity = ""
Bool EntryObserved = False
Bool ScanObserved = False
Bool CandidateObserved = False
Bool SelectionObserved = False
Bool StartObserved = False
Bool StopObserved = False
Bool ProductionStopSeen = False
Bool ReceiptObserved = False
Bool IdentityObserved = False
Bool InterruptRequested = False
Bool CleanupObserved = False
Bool EvidenceValid = True
String FailureReason = ""
Bool StartupPending = False
Int StartupAttempts = 0
Bool AwaitingFocusedEntry = False
Bool AutomatedFixture = False
Bool FixtureMoved = False

Event OnInit()
    ; Merely installing this quest never moves actors or enables a test.
    If JsonUtil.Load(RequestFile) && JsonUtil.IsPathBool(RequestFile, ".auto_run") && JsonUtil.GetPathBoolValue(RequestFile, ".auto_run", False)
        StartupPending = True
        RegisterForSingleUpdate(2.0)
    EndIf
EndEvent

Function TryAutorun()
    StartupAttempts += 1
    ; MCM Helper may not have initialized the production world's settings yet.
    If !Guard()
        If StartupAttempts < 15
            RegisterForSingleUpdate(2.0)
        Else
            StartupPending = False
            Log("HoldMusic LAB: autorun guard unavailable after 30 seconds.")
        EndIf
        Return
    EndIf
    StartupPending = False
    If !JsonUtil.Load(RequestFile) || !JsonUtil.IsPathBool(RequestFile, ".auto_run") || !JsonUtil.GetPathBoolValue(RequestFile, ".auto_run", False)
        Return
    EndIf
    String requested = JsonUtil.GetPathStringValue(RequestFile, ".scenario", "")
    String name = ""
    If requested == "ambient-entry"
        name = "ambient_entry"
    ElseIf requested == "focused-complete"
        name = "focused_complete"
    ElseIf requested == "focused-interrupt"
        name = "focused_interrupt"
    Else
        Log("HoldMusic LAB: unknown explicit autorun scenario.")
        Return
    EndIf
    Location current = Game.GetPlayer().GetCurrentLocation()
    If current && current.HasKeyword(LocTypeInn)
        Log("HoldMusic LAB: autorun requires the outside-inn starting cell.")
        Return
    EndIf
    AutomatedFixture = True
    If !BeginRun(name)
        Return
    EndIf
    ; Verified against the lab's Skyrim.esm: these persistent references share
    ; RiverwoodSleepingGiantInn CELL 000133C6. No cell override is required.
    ObjectReference stage = Game.GetFormFromFile(0x001027DA, "Skyrim.esm") as ObjectReference
    ObjectReference anchor = Game.GetFormFromFile(0x0010FCB7, "Skyrim.esm") as ObjectReference
    Actor fixtureActor = Game.GetFormFromFile(0x00013491, "Skyrim.esm") as Actor
    If !stage || !anchor || !fixtureActor || Library.FindPerformer(fixtureActor) != "sven"
        Finish("failed", "Explicit verified inn/Sven fixture references are unavailable.")
        Return
    EndIf
    Location destination = anchor.GetCurrentLocation()
    If !destination || !destination.HasKeyword(LocTypeInn) || stage.GetCurrentLocation() != destination
        Finish("failed", "Fixture anchor is not in an inn location.")
        Return
    EndIf
    fixtureActor.MoveTo(stage, 0.0, 0.0, 0.0, True)
    If Scenario != "ambient_entry"
        AwaitingFocusedEntry = True
    EndIf
    ; A real engine location transition, not a call to OnLocationChange.
    ; This tests scripted teleport entry, not walking through a door.
    Game.GetPlayer().MoveTo(anchor, 0.0, 0.0, 0.0, True)
    FixtureMoved = True
    SaveResult("running", "")
    RegisterForSingleUpdate(0.25)
EndFunction

; The runner writes a new run_id before EACH new scenario. Commands during a
; scenario (Interrupt, Cleanup, Status) continue its existing request.
Function ArmAmbient()
    AutomatedFixture = False
    Location current = Game.GetPlayer().GetCurrentLocation()
    If current && current.HasKeyword(LocTypeInn)
        Log("HoldMusic LAB: ArmAmbient requires the player outside an inn.")
        Return
    EndIf
    If BeginRun("ambient_entry")
        Log("HoldMusic LAB: armed; enter the inn normally with Sven present.")
        RegisterForSingleUpdate(0.25)
    EndIf
EndFunction

Function FocusedStart()
    StartFocused(False)
EndFunction

Function FocusedInterrupt()
    StartFocused(True)
EndFunction

Function StartFocused(Bool interruptAfterStart)
    AutomatedFixture = False
    Location current = Game.GetPlayer().GetCurrentLocation()
    If !current || !current.HasKeyword(LocTypeInn)
        Log("HoldMusic LAB: focused scenario requires the player inside an inn.")
        Return
    EndIf
    String name = "focused_complete"
    If interruptAfterStart
        name = "focused_interrupt"
    EndIf
    If !BeginRun(name)
        Return
    EndIf
    StartFocusedPrepared(current)
EndFunction

Function StartFocusedPrepared(Location current)
    ; This is explicit direct setup, NOT evidence of a real player-entry event.
    ; Production Venue is private and set only by its entry handler.
    Controller.OnLocationChange(None, current)
    Controller.UnregisterForUpdate()
    Actor[] candidates = MiscUtil.ScanCellNPCs(Game.GetPlayer(), 2000.0, None, False)
    Actor target = None
    Int i = 0
    While i < candidates.Length && !target
        If Library.FindPerformer(candidates[i]) == "sven"
            target = candidates[i]
        EndIf
        i += 1
    EndWhile
    If !target || Library.Owner("sven") != "hold_music" || !Controller.Eligible(target)
        Finish("failed", "Sven must be loaded, eligible, and owned by Hold Music.")
        Return
    EndIf
    String region = Library.Region("sven")
    SelectedSlot = Library.ChooseSlot("sven", region, "instrumental")
    If region == "" || SelectedSlot < 1 || SelectedSlot > 24
        Finish("failed", "No compatible unlocked fixture recording.")
        Return
    EndIf
    If Controller.SlotSounds.Length != 24 || !Controller.SlotSounds[SelectedSlot - 1]
        Finish("failed", "Selected slot has no bound Sound form.")
        Return
    EndIf
    If Library.Duration() <= 0.0 || Library.Duration() > 30.0
        Finish("failed", "Lab fixture duration must be positive and at most 30 seconds.")
        Return
    EndIf
    SelectedIdentity = RecordingIdentity(SelectedSlot)
    If SelectedIdentity == ""
        Finish("failed", "Lab fixture requires an explicit projected recording identity.")
        Return
    EndIf
    SelectionObserved = True
    Controller.StartPerformance(target, "sven", region, SelectedSlot)
    CollectEvidence()
    If !StartObserved
        Finish("failed", "No fresh production performance_start after direct start.")
        Return
    EndIf
    SaveResult("running", "")
    RegisterForSingleUpdate(0.25)
EndFunction

Bool Function Guard()
    If !Library || !Config || !HoldMusicQuest || !HM_Enabled || !HM_InstrumentalPercent || !HM_SessionCap || !HM_MinDelaySeconds || !HM_MaxDelaySeconds || !LocTypeInn
        Log("HoldMusic LAB: missing plugin property binding.")
        Return False
    EndIf
    If !JsonUtil.Load(ControlFile) || !JsonUtil.IsGood(ControlFile)
        Log("HoldMusic LAB: control file unavailable.")
        Return False
    EndIf
    If !JsonUtil.IsPathNumber(ControlFile, ".version") || JsonUtil.GetPathFloatValue(ControlFile, ".version", 0.0) != 1.0 || !JsonUtil.IsPathBool(ControlFile, ".enabled") || !JsonUtil.GetPathBoolValue(ControlFile, ".enabled", False)
        Log("HoldMusic LAB: control file is not enabled version 1.")
        Return False
    EndIf
    String world = JsonUtil.GetPathStringValue(ControlFile, ".world_id", "")
    If world != "hold-music-se-lab" || Config.WorldId != world
        Log("HoldMusic LAB: world_id must be hold-music-se-lab in control and MCM settings.")
        Return False
    EndIf
    Controller = HoldMusicQuest.GetAlias(0) as HM_Controller
    If !Controller
        Log("HoldMusic LAB: production controller alias unavailable.")
        Return False
    EndIf
    Return True
EndFunction

Bool Function BeginRun(String name)
    If Active || GlobalsSaved
        Log("HoldMusic LAB: a run is active; Cleanup before beginning another.")
        Return False
    EndIf
    If !Guard()
        Return False
    EndIf
    If !JsonUtil.Load(RequestFile) || !JsonUtil.IsGood(RequestFile) || !JsonUtil.IsPathNumber(RequestFile, ".version") || JsonUtil.GetPathFloatValue(RequestFile, ".version", 0.0) != 1.0
        Log("HoldMusic LAB: fresh version 1 request required.")
        Return False
    EndIf
    String requestedId = JsonUtil.GetPathStringValue(RequestFile, ".run_id", "")
    String requestedUtc = JsonUtil.GetPathStringValue(RequestFile, ".started_at_utc", "")
    If requestedId == "" || requestedUtc == "" || requestedId == RunId
        Log("HoldMusic LAB: request must contain a new run_id and started_at_utc.")
        Return False
    EndIf
    If JsonUtil.Load(ResultFile) && JsonUtil.GetPathStringValue(ResultFile, ".run_id", "") == requestedId
        Log("HoldMusic LAB: request already has a result; use a new run_id.")
        Return False
    EndIf
    If !JsonUtil.Load(Library.TraceFile) || !JsonUtil.IsGood(Library.TraceFile) || !JsonUtil.IsPathArray(Library.TraceFile, ".entries") || !JsonUtil.Load(Library.ReceiptsFile) || !JsonUtil.IsGood(Library.ReceiptsFile) || !JsonUtil.IsPathArray(Library.ReceiptsFile, ".performances")
        Log("HoldMusic LAB: valid existing trace and receipt arrays are required.")
        Return False
    EndIf
    ; Stop any old controller update before taking baselines. Never clear its
    ; slot locks, receipts, trace, cooldowns, or remembered session count.
    Controller.StopPerformance("interrupted")
    TraceBaseline = LastTraceSequence()
    TraceCursor = TraceBaseline
    ReceiptBaseline = JsonUtil.PathCount(Library.ReceiptsFile, ".performances")
    RunId = requestedId
    StartedAtUtc = requestedUtc
    Scenario = name
    ExpectedOutcome = "completed"
    Began = Utility.GetCurrentRealTime()
    Deadline = Began + 120.0
    If Scenario != "ambient_entry"
        Deadline = Began + 40.0
    EndIf
    SelectedSlot = 0
    ReceiptIndex = -1
    SelectedIdentity = ""
    EntryObserved = False
    ScanObserved = False
    CandidateObserved = False
    SelectionObserved = False
    StartObserved = False
    StopObserved = False
    ProductionStopSeen = False
    ReceiptObserved = False
    IdentityObserved = False
    InterruptRequested = False
    CleanupObserved = False
    EvidenceValid = True
    FailureReason = ""
    AwaitingFocusedEntry = False
    FixtureMoved = False
    JsonUtil.ClearAll(ResultFile)
    Active = True
    ; Establish fresh evidence on disk before enabling/scheduling any test.
    If !SaveResult("running", "")
        Active = False
        Return False
    EndIf
    OldEnabled = HM_Enabled.GetValue()
    OldInstrumental = HM_InstrumentalPercent.GetValue()
    OldCap = HM_SessionCap.GetValue()
    OldMinDelay = HM_MinDelaySeconds.GetValue()
    OldMaxDelay = HM_MaxDelaySeconds.GetValue()
    GlobalsSaved = True
    HM_Enabled.SetValue(1.0)
    HM_InstrumentalPercent.SetValue(100.0)
    HM_SessionCap.SetValue(24.0)
    Float delay = 1.0
    If Scenario != "ambient_entry"
        ; Direct setup must not race an automatically scheduled ambient scan.
        delay = 600.0
    EndIf
    HM_MinDelaySeconds.SetValue(delay)
    HM_MaxDelaySeconds.SetValue(delay)
    Return True
EndFunction

Event OnUpdate()
    If StartupPending
        TryAutorun()
        Return
    EndIf
    If !Active
        Return
    EndIf
    Float now = Utility.GetCurrentRealTime()
    If now < Began
        Finish("failed", "Real-time clock reset; stale saved test state.")
        Return
    EndIf
    If !Guard() || !JsonUtil.Load(RequestFile) || JsonUtil.GetPathStringValue(RequestFile, ".run_id", "") != RunId
        Finish("failed", "Lab guard or active request changed during the run.")
        Return
    EndIf
    If AwaitingFocusedEntry
        Location current = Game.GetPlayer().GetCurrentLocation()
        If current && current.HasKeyword(LocTypeInn)
            AwaitingFocusedEntry = False
            StartFocusedPrepared(current)
        ElseIf now >= Deadline
            Finish("failed", "Timed out waiting for the scripted inn transition.")
        Else
            RegisterForSingleUpdate(0.25)
        EndIf
        Return
    EndIf
    CollectEvidence()
    If !EvidenceValid
        Finish("failed", FailureReason)
        Return
    EndIf
    If Scenario == "focused_interrupt" && StartObserved && !InterruptRequested && now >= Began + 2.0
        Interrupt()
    EndIf
    If ReceiptObserved
        Bool passed = StartObserved && StopObserved && SelectionObserved && CleanupObserved
        If Scenario == "ambient_entry"
            passed = passed && EntryObserved && ScanObserved && CandidateObserved
        EndIf
        If SelectedIdentity == "" || !IdentityObserved
            Finish("failed", "Receipt identity does not match the selected projected fixture.")
            Return
        EndIf
        If passed
            Finish("passed", "")
            Return
        EndIf
        ; Papyrus can interleave stacks between our trace and receipt reads.
        ; Allow a subsequent poll to observe the stop trace and cleared flag.
    EndIf
    If now >= Deadline
        Finish("failed", "Timed out waiting for the expected production trace and receipt.")
    Else
        If !SaveResult("running", "")
            Finish("failed", "Could not save lab evidence.")
            Return
        EndIf
        RegisterForSingleUpdate(0.25)
    EndIf
EndEvent

Function Interrupt()
    If !Active || !StartObserved
        Log("HoldMusic LAB: no observed active performance to interrupt.")
        Return
    EndIf
    ; Test the production poller's stop-request branch, not a direct stop call.
    ExpectedOutcome = "interrupted"
    InterruptRequested = True
    Config.StopRequested = True
    SaveResult("running", "")
EndFunction

Function Cleanup()
    StartupPending = False
    If Active
        Finish("cancelled", "Explicit lab Cleanup.")
    ElseIf GlobalsSaved
        RestoreGlobals()
    Else
        Log("HoldMusic LAB: no active run to clean up.")
    EndIf
EndFunction

Function Status()
    Log("HoldMusic LAB: run_id=" + RunId + " scenario=" + Scenario + " active=" + Active + "; evidence=" + ResultFile)
EndFunction

Int Function LastTraceSequence()
    JsonUtil.Load(Library.TraceFile)
    Int count = JsonUtil.PathCount(Library.TraceFile, ".entries")
    If count <= 0
        Return 0
    EndIf
    Return JsonUtil.GetPathIntValue(Library.TraceFile, ".entries[" + (count - 1) + "].seq", 0)
EndFunction

Int Function SlotFromDetail(String detail)
    Int start = StringUtil.Find(detail, " slot=") + 6
    If start < 6
        Return 0
    EndIf
    String tail = StringUtil.Substring(detail, start)
    Int boundary = StringUtil.Find(tail, " ")
    If boundary >= 0
        tail = StringUtil.Substring(tail, 0, boundary)
    EndIf
    Return tail as Int
EndFunction

String Function RecordingIdentity(Int slot)
    If !JsonUtil.Load(Library.LibraryFile) || !JsonUtil.IsGood(Library.LibraryFile)
        Return ""
    EndIf
    Int i = 0
    While i < JsonUtil.PathCount(Library.LibraryFile, ".recordings")
        String path = ".recordings[" + i + "]"
        If JsonUtil.GetPathIntValue(Library.LibraryFile, path + ".slot", 0) == slot
            Return JsonUtil.GetPathStringValue(Library.LibraryFile, path + ".identity_key", "")
        EndIf
        i += 1
    EndWhile
    Return ""
EndFunction

Function CollectEvidence()
    If !JsonUtil.Load(Library.TraceFile) || !JsonUtil.IsGood(Library.TraceFile) || !JsonUtil.IsPathArray(Library.TraceFile, ".entries")
        EvidenceValid = False
        FailureReason = "Production trace is missing or malformed."
        Return
    EndIf
    If LastTraceSequence() < TraceCursor
        EvidenceValid = False
        FailureReason = "Production trace sequence regressed."
        Return
    EndIf
    Int i = 0
    While i < JsonUtil.PathCount(Library.TraceFile, ".entries")
        String path = ".entries[" + i + "]"
        Int seq = JsonUtil.GetPathIntValue(Library.TraceFile, path + ".seq", 0)
        If seq > TraceCursor
            TraceCursor = seq
            String eventName = JsonUtil.GetPathStringValue(Library.TraceFile, path + ".event", "")
            String detail = JsonUtil.GetPathStringValue(Library.TraceFile, path + ".detail", "")
            If Scenario == "ambient_entry" && eventName == "location_enter"
                EntryObserved = True
            ElseIf Scenario == "ambient_entry" && EntryObserved && eventName == "check_start"
                ScanObserved = True
            ElseIf Scenario == "ambient_entry" && ScanObserved && eventName == "candidate" && StringUtil.Find(detail, "id=sven owner=hold_music eligible=true ") == 0
                CandidateObserved = True
            ElseIf Scenario == "ambient_entry" && CandidateObserved && eventName == "slot_chosen" && StringUtil.Find(detail, "id=sven slot=") == 0
                SelectedSlot = SlotFromDetail(detail)
                SelectionObserved = SelectedSlot >= 1 && SelectedSlot <= 24
                SelectedIdentity = RecordingIdentity(SelectedSlot)
                If SelectedIdentity == ""
                    EvidenceValid = False
                    FailureReason = "Lab fixture requires an explicit projected recording identity."
                EndIf
            ElseIf SelectionObserved && eventName == "performance_start" && StringUtil.Find(detail, "id=sven slot=") == 0 && SlotFromDetail(detail) == SelectedSlot
                StartObserved = True
            ElseIf StartObserved && eventName == "performance_stop" && StringUtil.Find(detail, " id=sven slot=") >= 0 && SlotFromDetail(detail) == SelectedSlot
                ProductionStopSeen = True
                If detail == "outcome=" + ExpectedOutcome + " id=sven slot=" + SelectedSlot
                    StopObserved = True
                EndIf
            ElseIf eventName == "receipt_failed"
                EvidenceValid = False
                FailureReason = "Production receipt save failed."
            EndIf
        EndIf
        i += 1
    EndWhile
    If !JsonUtil.Load(Library.ReceiptsFile) || !JsonUtil.IsGood(Library.ReceiptsFile) || !JsonUtil.IsPathArray(Library.ReceiptsFile, ".performances")
        EvidenceValid = False
        FailureReason = "Production receipts are missing or malformed."
        Return
    EndIf
    Int count = JsonUtil.PathCount(Library.ReceiptsFile, ".performances")
    If count < ReceiptBaseline
        EvidenceValid = False
        FailureReason = "Production receipt history shrank."
        Return
    EndIf
    i = ReceiptBaseline
    While i < count
        String row = ".performances[" + i + "]"
        If JsonUtil.GetPathStringValue(Library.ReceiptsFile, row + ".performer_id", "") == "sven" && JsonUtil.GetPathIntValue(Library.ReceiptsFile, row + ".slot", 0) == SelectedSlot && JsonUtil.GetPathFloatValue(Library.ReceiptsFile, row + ".started_real_seconds", 0.0) >= Began && JsonUtil.GetPathStringValue(Library.ReceiptsFile, row + ".world_id", "") == Config.WorldId && JsonUtil.GetPathStringValue(Library.ReceiptsFile, row + ".outcome", "") == ExpectedOutcome
            ReceiptObserved = True
            ReceiptIndex = i
            IdentityObserved = SelectedIdentity != "" && JsonUtil.GetPathStringValue(Library.ReceiptsFile, row + ".runtime_identity.identity_key", "") == SelectedIdentity
            ; A receipt and stop trace cover the production cleanup path.
            ; The script cannot inspect the sound engine or visually assess idle.
            CleanupObserved = StopObserved && !Config.StopRequested
        EndIf
        i += 1
    EndWhile
EndFunction

Bool Function RestoreGlobals()
    If GlobalsSaved
        HM_Enabled.SetValue(OldEnabled)
        HM_InstrumentalPercent.SetValue(OldInstrumental)
        HM_SessionCap.SetValue(OldCap)
        HM_MinDelaySeconds.SetValue(OldMinDelay)
        HM_MaxDelaySeconds.SetValue(OldMaxDelay)
        GlobalsSaved = HM_Enabled.GetValue() != OldEnabled || HM_InstrumentalPercent.GetValue() != OldInstrumental || HM_SessionCap.GetValue() != OldCap || HM_MinDelaySeconds.GetValue() != OldMinDelay || HM_MaxDelaySeconds.GetValue() != OldMaxDelay
    EndIf
    Return !GlobalsSaved
EndFunction

Function Finish(String status, String reason)
    UnregisterForUpdate()
    ; A receipt can become visible before the production stop stack clears
    ; its private Performer. Reentering StopPerformance then would append a
    ; duplicate interrupted receipt. Never stop again after evidence of that
    ; stop; only cancel scheduling. Forced stop bounds unfinished failed tests.
    If ProductionStopSeen || ReceiptObserved
        Controller.UnregisterForUpdate()
    Else
        Controller.StopPerformance("interrupted")
    EndIf
    If !RestoreGlobals()
        status = "failed"
        reason = "Global values did not read back as their saved baseline."
    EndIf
    Active = False
    AwaitingFocusedEntry = False
    SaveResult(status, reason)
    Log("HoldMusic LAB: " + status + " run_id=" + RunId + " " + reason)
EndFunction

Bool Function SaveResult(String status, String reason)
    JsonUtil.SetPathIntValue(ResultFile, ".version", 1)
    JsonUtil.SetPathStringValue(ResultFile, ".run_id", RunId)
    JsonUtil.SetPathStringValue(ResultFile, ".started_at_utc", StartedAtUtc)
    JsonUtil.SetPathStringValue(ResultFile, ".world_id", Config.WorldId)
    JsonUtil.SetPathStringValue(ResultFile, ".scenario", Scenario)
    JsonUtil.SetPathStringValue(ResultFile, ".status", status)
    JsonUtil.SetPathStringValue(ResultFile, ".reason", reason)
    JsonUtil.SetPathStringValue(ResultFile, ".expected_performer_id", "sven")
    JsonUtil.SetPathStringValue(ResultFile, ".expected_outcome", ExpectedOutcome)
    JsonUtil.SetPathFloatValue(ResultFile, ".started_real_seconds", Began)
    JsonUtil.SetPathFloatValue(ResultFile, ".observed_real_seconds", Utility.GetCurrentRealTime())
    JsonUtil.SetPathIntValue(ResultFile, ".trace_baseline", TraceBaseline)
    JsonUtil.SetPathIntValue(ResultFile, ".trace_cursor", TraceCursor)
    JsonUtil.SetPathIntValue(ResultFile, ".receipt_baseline", ReceiptBaseline)
    JsonUtil.SetPathIntValue(ResultFile, ".receipt_index", ReceiptIndex)
    JsonUtil.SetPathIntValue(ResultFile, ".selected_slot", SelectedSlot)
    JsonUtil.SetPathStringValue(ResultFile, ".selected_identity_key", SelectedIdentity)
    SaveBool(".runtime_engine_observed", True)
    SaveBool(".audio_audibility_verified", False)
    SaveBool(".animation_visual_verified", False)
    SaveBool(".ambient_scheduling_bypassed", Scenario != "ambient_entry")
    SaveBool(".controller_entry_setup_injected", Scenario != "ambient_entry")
    SaveBool(".scripted_fixture_teleport", AutomatedFixture)
    SaveBool(".fixture_moved", FixtureMoved)
    SaveBool(".globals_restored", !GlobalsSaved && !Active)
    SaveBool(".assertions.real_inn_entry", EntryObserved)
    SaveBool(".assertions.production_scan", ScanObserved)
    SaveBool(".assertions.eligible_owned_sven", CandidateObserved)
    SaveBool(".assertions.slot_selection", SelectionObserved)
    SaveBool(".assertions.performance_start", StartObserved)
    SaveBool(".assertions.performance_stop", StopObserved)
    SaveBool(".assertions.production_stop_seen", ProductionStopSeen)
    SaveBool(".assertions.receipt", ReceiptObserved)
    SaveBool(".assertions.receipt_identity_key", IdentityObserved)
    SaveBool(".assertions.stop_request_issued", InterruptRequested)
    SaveBool(".assertions.cleanup_trace_and_receipt", CleanupObserved)
    SaveBool(".assertions.evidence_valid", EvidenceValid)
    Bool saved = JsonUtil.Save(ResultFile, False)
    If !saved
        Log("HoldMusic LAB: failed to save result evidence.")
    EndIf
    Return saved
EndFunction

Function Log(String message)
    Debug.Trace(message, 0)
EndFunction

Function SaveBool(String path, Bool value)
    String raw = "false"
    If value
        raw = "true"
    EndIf
    JsonUtil.SetRawPathValue(ResultFile, path, raw)
EndFunction
