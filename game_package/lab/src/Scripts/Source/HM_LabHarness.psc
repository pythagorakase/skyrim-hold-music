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
Float PreparationDeadline = 0.0
Float PlaybackDeadline = 0.0
Float FixtureDuration = 0.0
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
Float StartObservedAt = 0.0
Float StartTraceAt = 0.0
Bool StopObserved = False
Bool ProductionStopSeen = False
Bool ReceiptObserved = False
Bool IdentityObserved = False
Bool InterruptRequested = False
Float InterruptRequestedAt = 0.0
Bool InterruptWindowMissed = False
Bool RequestedInterruptGuardObserved = False
Bool CleanupObserved = False
Bool EvidenceValid = True
String FailureReason = ""
Bool StartupPending = False
Int StartupAttempts = 0
Bool AwaitingFocusedEntry = False
Bool AutomatedFixture = False
Bool FixtureMoved = False
Bool FocusedStartInFlight = False
Bool FocusedPreparationInFlight = False
Int FinishEpoch = 0
Int FinishDepth = 0
Int BooleanSerializationErrors = 0
Bool WorldSetupRequested = False
Bool WorldSetupReady = False
Bool GameHourSaved = False
Bool WorldBaselineObserved = False
Float SetupDeadline = 0.0
Float SetupFinishedAt = 0.0
GlobalVariable LabGameHour
Quest IntroQuest
Scene IntroScene
Float OldGameHour = 0.0
Float ConfiguredGameHour = 0.0
Int IntroStageBefore = 0
Int IntroStageAfter = 0
Bool IntroStage10Before = False
Bool IntroStage10After = False
Bool IntroRunningBefore = False
Bool IntroRunningAfter = False
Bool IntroScenePlayingAfter = False
Int FixturePackageAfter = 0
Int MainQuestStageBefore = -1
Bool StoryEntryAttempted = False
Bool StoryEntryObserved = False
Bool IntroRunningObserved = False
Bool IntroNaturalCompletionObserved = False
Bool IntroCleanupRequested = False
Bool IntroCleanupAccepted = False
Int StoryWaitAttempts = 0
Int ExteriorLocationAfter = 0
ReferenceAlias FixtureHoldAlias
Package FixtureHoldPackage
Actor FixtureHeldActor
Bool FixtureHoldRequested = False
Bool FixtureHoldIntent = False
Bool FixtureHoldCallInFlight = False
Bool FixtureHoldOwned = False
Bool FixtureHoldAcquired = False
Bool FixtureHoldReleased = False
Bool FixtureStandingObserved = False
Int PackageBeforeHold = 0
Int PackageDuringHold = 0
Int PackageAfterRelease = 0
Faction AutostartFaction
Actor AutostartActor
Bool AutostartPreparing = False
Bool AutostartIntent = False
Bool AutostartBaselineObserved = False
Bool AutostartBaselineMember = False
Int AutostartBaselineRank = -1
Bool AutostartWriteIssued = False
Bool AutostartCallInFlight = False
Bool AutostartReleaseInFlight = False
Bool AutostartReady = False
Bool AutostartAcquired = False
Bool AutostartReleased = False
Bool AutostartConflict = False
Int AutostartObservedRank = -1
Int AutostartPackageBefore = 0
Bool AutostartDialogueBefore = False
Bool AutostartSceneBefore = False
Bool AutostartStarterBefore = False
Float ScanStartedAt = 0.0
Float ScanFinishedAt = 0.0
Float MatchingFinishedAt = 0.0
Float DiagnosticsFinishedAt = 0.0
Float SelectionStartedAt = 0.0
Float SelectionFinishedAt = 0.0
Float EvidenceCollectionStartedAt = 0.0
Float EvidenceCollectionFinishedAt = 0.0
Float EvidenceCollectionMaxSeconds = 0.0
Float PreviousResultSaveSeconds = 0.0
Float ResultSaveMaxSeconds = 0.0
Int AdmissionTicket = 0
Bool AdmissionAcquireInFlight = False
Bool AdmissionResumeInFlight = False
Bool AdmissionFault = False
Bool AdmissionDrainedObserved = False
Bool AdmissionRestored = False
Bool InitialDrainPending = False
Bool BaselinesReady = False
Float AdmissionDeadline = 0.0
Bool Finishing = False
Bool CleanupAdvancing = False
Bool TerminalFrozen = False
String PendingFinishStatus = ""
String PendingFinishReason = ""
Float CleanupDeadline = 0.0
Bool AwaitingAmbientExit = False
Bool AmbientExitObserved = False
Bool AmbientEntryAfterResume = False
Bool BeginRunInFlight = False
Bool BeginCancellationRequested = False
Bool BaselineWorkInFlight = False
Bool AdmissionTransitionInFlight = False
Bool FixtureTransitionInFlight = False
Bool FixtureMovementUnresolved = False

Event OnInit()
    ; Merely installing this quest never moves actors or enables a test.
    If JsonUtil.Load(RequestFile) && JsonUtil.IsPathBool(RequestFile, ".auto_run") && JsonUtil.GetPathBoolValue(RequestFile, ".auto_run", False)
        StartupPending = True
        RegisterForSingleUpdate(2.0)
    EndIf
EndEvent

Function TryAutorun()
    If Active || Finishing || BeginRunInFlight || BaselineWorkInFlight || AdmissionTransitionInFlight || FixtureTransitionInFlight || FixtureMovementUnresolved || AdmissionTicket > 0 || AdmissionAcquireInFlight || AdmissionResumeInFlight || FinishDepth > 0
        Return
    EndIf
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
    PrepareAutorun()
EndFunction

Function PrepareAutorun()
    String expectedRun = RunId
    If !ContinueRun(expectedRun)
        Return
    EndIf
    WorldSetupRequested = JsonUtil.IsPathBool(ControlFile, ".allow_disposable_world_setup") && JsonUtil.GetPathBoolValue(ControlFile, ".allow_disposable_world_setup", False)
    FixtureHoldRequested = JsonUtil.IsPathBool(ControlFile, ".allow_controlled_actor_ai") && JsonUtil.GetPathBoolValue(ControlFile, ".allow_controlled_actor_ai", False)
    If FixtureHoldRequested && !WorldSetupRequested
        Finish("failed", "Controlled actor AI requires the explicit disposable-world setup.")
        Return
    EndIf
    ; Sven only: inhibit the inspected vanilla inn-entry starter before ANY
    ; fixture transition. This cannot cancel a previously queued song request.
    If FixtureHoldRequested && !AcquireAutostartLease(expectedRun)
        If Active && RunId == expectedRun
            Finish("failed", "Sven vanilla autostart lease could not be verified.")
        EndIf
        Return
    EndIf
    If !ContinueRun(expectedRun)
        Return
    EndIf
    If WorldSetupRequested
        SetupDeadline = Utility.GetCurrentRealTime() + 90.0
        If !PrepareDisposableWorld() || !SetupStillAuthorized(expectedRun)
            If Active && RunId == expectedRun
                Finish("failed", "Explicit disposable-world setup could not be verified.")
            EndIf
            Return
        EndIf
        ; Setup has its own bounded budget. It does not consume the existing
        ; post-setup loading/performance deadline or change expected outcome.
        SetupFinishedAt = Utility.GetCurrentRealTime()
        Deadline = SetupFinishedAt + 120.0
        If Scenario != "ambient_entry"
            PreparationDeadline = SetupFinishedAt + 90.0
            Deadline = PreparationDeadline
        EndIf
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
    If !ContinueRun(expectedRun)
        Return
    EndIf
    fixtureActor.MoveTo(stage, 0.0, 0.0, 0.0, True)
    If !ContinueRun(expectedRun)
        Return
    EndIf
    ; The authored hold package uses Near Self. Acquire after placing Sven at
    ; the stage, before player entry loads the inn and permits sandbox sitting.
    If FixtureHoldRequested
        If !AcquireFixtureHold(fixtureActor, expectedRun)
            If Active && RunId == expectedRun
                Finish("failed", "Controlled standing fixture could not be acquired.")
            EndIf
            Return
        EndIf
    EndIf
    If !ContinueRun(expectedRun)
        Return
    EndIf
    If Scenario != "ambient_entry" || FixtureHoldRequested
        AwaitingFocusedEntry = True
    ElseIf !ResumeOwnedAdmission(expectedRun)
        Return
    EndIf
    ; A real engine location transition, not a call to OnLocationChange.
    ; This tests scripted teleport entry, not walking through a door.
    Game.GetPlayer().MoveTo(anchor, 0.0, 0.0, 0.0, True)
    If !ContinueRun(expectedRun)
        Return
    EndIf
    FixtureMoved = True
    If !SaveResult("running", "")
        Finish("failed", "Could not save evidence after fixture movement.")
        Return
    EndIf
    If ContinueRun(expectedRun)
        RegisterForSingleUpdate(0.25)
    EndIf
EndFunction

Bool Function AcquireAutostartLease(String expectedRun)
    ; Fence the complete native/readback sequence, including a cancelled run
    ; before mutation. A replacement run may not reuse its shared state.
    If AutostartPreparing || AutostartIntent || AutostartCallInFlight || AutostartReleaseInFlight
        Return False
    EndIf
    AutostartPreparing = True
    Bool acquired = PrepareAutostartLease(expectedRun)
    AutostartPreparing = False
    Return acquired
EndFunction

Bool Function PrepareAutostartLease(String expectedRun)
    If !AutostartPreparing || !Active || !AutomatedFixture || !WorldSetupRequested || !FixtureHoldRequested || !ContinueRun(expectedRun)
        Return False
    EndIf
    AutostartActor = Game.GetFormFromFile(0x00013491, "Skyrim.esm") as Actor
    AutostartFaction = Game.GetFormFromFile(0x000163FA, "Skyrim.esm") as Faction
    Quest starter = Game.GetFormFromFile(0x000BE159, "Skyrim.esm") as Quest
    If !AutostartActor || !AutostartFaction || !starter || Library.FindPerformer(AutostartActor) != "sven"
        Return False
    EndIf
    AutostartDialogueBefore = AutostartActor.IsInDialogueWithPlayer()
    AutostartSceneBefore = AutostartActor.GetCurrentScene() != None
    AutostartStarterBefore = starter.IsRunning()
    Package before = AutostartActor.GetCurrentPackage()
    If before
        AutostartPackageBefore = before.GetFormID()
    EndIf
    ; An unloaded actor may have no current package. Record that as unknown;
    ; later loaded/standing readback remains mandatory, not inferred here.
    If !ContinueRun(expectedRun) || AutostartDialogueBefore || AutostartSceneBefore || AutostartStarterBefore || AutostartPackageBefore == 0x000FB904
        Return False
    EndIf
    AutostartBaselineMember = AutostartActor.IsInFaction(AutostartFaction)
    AutostartBaselineRank = AutostartActor.GetFactionRank(AutostartFaction)
    If !ContinueRun(expectedRun)
        Return False
    EndIf
    AutostartBaselineObserved = True
    If AutostartBaselineMember != (AutostartBaselineRank >= 0)
        AutostartConflict = True
        Return False
    EndIf
    AutostartIntent = True
    ; Persist baseline and intent before the single native rank mutation.
    If !SaveResult("running", "") || !ContinueRun(expectedRun)
        Return False
    EndIf
    Bool member = AutostartActor.IsInFaction(AutostartFaction)
    Int rank = AutostartActor.GetFactionRank(AutostartFaction)
    If !ContinueRun(expectedRun)
        Return False
    EndIf
    If member != AutostartBaselineMember || rank != AutostartBaselineRank
        AutostartConflict = True
        Return False
    EndIf
    If !member
        ; AddToFaction is a scripted check-then-set wrapper. Use one native
        ; SetFactionRank and record an unresolved call before it can yield.
        AutostartWriteIssued = True
        AutostartCallInFlight = True
        AutostartActor.SetFactionRank(AutostartFaction, 0)
        AutostartCallInFlight = False
        If !ContinueRun(expectedRun)
            ReleaseAutostartLease()
            Return False
        EndIf
    EndIf
    If !AutostartLeaseIntact() || !ContinueRun(expectedRun)
        Return False
    EndIf
    AutostartReady = True
    AutostartAcquired = True
    Return True
EndFunction

Bool Function AutostartLeaseIntact()
    If !AutostartIntent || !AutostartActor || !AutostartFaction || AutostartCallInFlight || AutostartReleaseInFlight
        Return False
    EndIf
    Bool member = AutostartActor.IsInFaction(AutostartFaction)
    AutostartObservedRank = AutostartActor.GetFactionRank(AutostartFaction)
    Int expected = 0
    If AutostartBaselineMember
        expected = AutostartBaselineRank
    EndIf
    Bool intact = member && AutostartObservedRank == expected
    AutostartConflict = AutostartConflict || !intact
    Return intact
EndFunction

Bool Function ReleaseAutostartLease()
    If !AutostartIntent
        Return True
    EndIf
    If !CleanupAdmissionReady()
        Return False
    EndIf
    If AutostartReleaseInFlight
        Return False
    EndIf
    ; Cover native reads as well as mutation: a reentrant inactive Cleanup
    ; cannot release ownership and let a new run reset our pending stack.
    AutostartReleaseInFlight = True
    Bool released = ReconcileAutostartLease()
    AutostartReleaseInFlight = False
    Return released
EndFunction

Bool Function ReconcileAutostartLease()
    ; Keep suppression until the owned alias and any pending start have been
    ; cleaned up. A native return may compensate later, never upgrade evidence.
    If !AutostartReleaseInFlight || AutostartCallInFlight || FocusedStartInFlight || FixtureHoldIntent || FixtureHoldOwned || FixtureHoldCallInFlight || !AutostartActor || !AutostartFaction
        Return False
    EndIf
    Bool member = AutostartActor.IsInFaction(AutostartFaction)
    AutostartObservedRank = AutostartActor.GetFactionRank(AutostartFaction)
    If AutostartBaselineMember
        ; Preexisting membership is never ours to remove or restore by writing.
        AutostartReleased = member && AutostartObservedRank == AutostartBaselineRank
    ElseIf !AutostartWriteIssued
        AutostartReleased = !member && AutostartObservedRank < 0
    ElseIf !member && AutostartObservedRank < 0
        AutostartReleased = True
    ElseIf member && AutostartObservedRank == 0
        AutostartActor.RemoveFromFaction(AutostartFaction)
        member = AutostartActor.IsInFaction(AutostartFaction)
        AutostartObservedRank = AutostartActor.GetFactionRank(AutostartFaction)
        ; Native SE returned -2 for an absent entry, despite the imported PSC
        ; comment mentioning only -1. Preserve the raw rank; membership plus
        ; a negative rank establishes effective absence, not exact storage.
        AutostartReleased = !member && AutostartObservedRank < 0
    Else
        ; A changed rank is foreign state. Do not erase it to claim restoration.
        AutostartReleased = False
    EndIf
    AutostartConflict = AutostartConflict || !AutostartReleased
    If AutostartReleased
        AutostartIntent = False
        AutostartReady = False
    EndIf
    Return AutostartReleased
EndFunction

Bool Function AcquireFixtureHold(Actor fixtureActor, String expectedRun)
    If !FixtureHoldStillAuthorized(expectedRun)
        Return False
    EndIf
    FixtureHoldAlias = Self.GetAlias(0) as ReferenceAlias
    FixtureHoldPackage = Game.GetFormFromFile(0x0010FB3F, "Skyrim.esm") as Package
    If !FixtureHoldAlias || !FixtureHoldPackage || FixtureHoldAlias.GetReference() || !fixtureActor || Library.FindPerformer(fixtureActor) != "sven"
        Return False
    EndIf
    Package previous = fixtureActor.GetCurrentPackage()
    If previous
        PackageBeforeHold = previous.GetFormID()
    EndIf
    If !previous || previous == FixtureHoldPackage
        Return False
    EndIf
    FixtureHeldActor = fixtureActor
    FixtureHoldIntent = True
    ; Durable intent precedes the native ownership mutation.
    If !SaveResult("running", "") || !FixtureHoldStillAuthorized(expectedRun)
        Return False
    EndIf
    FixtureHoldCallInFlight = True
    FixtureHoldAlias.ForceRefTo(fixtureActor)
    FixtureHoldCallInFlight = False
    If !FixtureHoldStillAuthorized(expectedRun)
        If ReleaseFixtureHold()
            ReleaseAutostartLease()
        EndIf
        Return False
    EndIf
    If FixtureHoldAlias.GetReference() != fixtureActor
        Return False
    EndIf
    FixtureHoldOwned = True
    FixtureHoldAcquired = True
    fixtureActor.EvaluatePackage()
    Return FixtureHoldStillAuthorized(expectedRun)
EndFunction

Bool Function FixtureHoldStillAuthorized(String expectedRun)
    Return SetupStillAuthorized(expectedRun) && WorldSetupReady && FixtureHoldRequested && JsonUtil.IsPathBool(ControlFile, ".allow_controlled_actor_ai") && JsonUtil.GetPathBoolValue(ControlFile, ".allow_controlled_actor_ai", False)
EndFunction

Bool Function ObserveStandingFixture()
    If !FixtureHoldOwned || !FixtureHoldAlias || !FixtureHeldActor || FixtureHoldAlias.GetReference() != FixtureHeldActor
        Return False
    EndIf
    Package current = FixtureHeldActor.GetCurrentPackage()
    If current
        PackageDuringHold = current.GetFormID()
    EndIf
    Bool ready = current == FixtureHoldPackage && FixtureHeldActor.Is3DLoaded() && FixtureHeldActor.GetSitState() == 0 && FixtureHeldActor.GetSleepState() == 0
    FixtureStandingObserved = FixtureStandingObserved || ready
    Return ready
EndFunction

Bool Function ReleaseFixtureHold()
    If !FixtureHoldIntent && !FixtureHoldOwned
        Return True
    EndIf
    If !CleanupAdmissionReady()
        Return False
    EndIf
    If !FixtureHoldAlias || !FixtureHeldActor
        Return False
    EndIf
    ObjectReference observed = FixtureHoldAlias.GetReference()
    If observed && observed != FixtureHeldActor
        ; Never clear an alias that somebody replaced with a different actor.
        Return False
    EndIf
    If observed == FixtureHeldActor
        FixtureHoldAlias.Clear()
    EndIf
    If FixtureHoldAlias.GetReference()
        Return False
    EndIf
    FixtureHoldOwned = False
    FixtureHeldActor.EvaluatePackage()
    Package current = FixtureHeldActor.GetCurrentPackage()
    Int attempts = 0
    While current == FixtureHoldPackage && attempts < 10
        Utility.Wait(0.1)
        current = FixtureHeldActor.GetCurrentPackage()
        attempts += 1
    EndWhile
    If current
        PackageAfterRelease = current.GetFormID()
    EndIf
    ; A cancellation may run inside the native acquisition call. Keep intent
    ; until that call returns, so a late assignment is still cleaned up and
    ; a second run cannot start against unresolved ownership.
    FixtureHoldReleased = !FixtureHoldAlias.GetReference() && current && current != FixtureHoldPackage && !FixtureHoldCallInFlight
    If FixtureHoldReleased
        FixtureHoldIntent = False
    EndIf
    Return FixtureHoldReleased
EndFunction

Bool Function PrepareDisposableWorld()
    ; LAB AUTORUN ONLY. These forms/scripts were inspected in the actual SE
    ; archives. Stage 20 is the intro scene's authored cleanup: set 10, Stop.
    ; Quest completion history is not undone; discard this disposable world.
    String expectedRun = RunId
    If !SetupStillAuthorized(expectedRun)
        Return False
    EndIf
    IntroQuest = Game.GetFormFromFile(0x000954D9, "Skyrim.esm") as Quest
    IntroScene = Game.GetFormFromFile(0x000954DA, "Skyrim.esm") as Scene
    LabGameHour = Game.GetFormFromFile(0x00000038, "Skyrim.esm") as GlobalVariable
    Actor fixtureActor = Game.GetFormFromFile(0x00013491, "Skyrim.esm") as Actor
    Quest mainQuest = Game.GetFormFromFile(0x0004E50D, "Skyrim.esm") as Quest
    If !IntroQuest || !IntroScene || !LabGameHour || !fixtureActor || !mainQuest
        Return False
    EndIf
    OldGameHour = LabGameHour.GetValue()
    IntroStageBefore = IntroQuest.GetStage()
    IntroStage10Before = IntroQuest.GetStageDone(10)
    IntroRunningBefore = IntroQuest.IsRunning()
    MainQuestStageBefore = mainQuest.GetStage()
    WorldBaselineObserved = True
    ; Save the intended mutation and its baseline before touching quest/time.
    If !SaveResult("running", "")
        Return False
    EndIf
    If !SetupStillAuthorized(expectedRun)
        Return False
    EndIf
    ; The CLOC Story Manager node permits hours 08:00-20:00. Set the already
    ; authorized temporary hour before a natural exterior entry, not afterward.
    GameHourSaved = True
    LabGameHour.SetValue(18.0)
    ConfiguredGameHour = LabGameHour.GetValue()
    If !HourNear(ConfiguredGameHour, 18.0)
        Return False
    EndIf
    If !IntroQuest.GetStageDone(10) && !IntroQuest.IsRunning()
        If MainQuestStageBefore >= 50 || !PrimeIntroFromExterior(expectedRun)
            Return False
        EndIf
    EndIf
    If !SetupStillAuthorized(expectedRun)
        Return False
    EndIf
    ; This is an event-scoped quest: SetStage cannot start it directly.
    ; Never request cleanup until Story Manager has actually started it.
    IntroRunningObserved = IntroRunningObserved || IntroQuest.IsRunning()
    If IntroQuest.IsRunning()
        IntroCleanupRequested = True
        IntroCleanupAccepted = IntroQuest.SetStage(20)
        If !SetupStillAuthorized(expectedRun)
            Return False
        EndIf
    EndIf
    Int attempts = 0
    While attempts < 20 && (!IntroQuest.GetStageDone(10) || IntroQuest.IsRunning() || IntroScene.IsPlaying())
        Utility.Wait(0.1)
        ; A latent wait can resume after Cleanup or a changed request.
        If !SetupStillAuthorized(expectedRun)
            Return False
        EndIf
        attempts += 1
    EndWhile
    IntroStageAfter = IntroQuest.GetStage()
    IntroStage10After = IntroQuest.GetStageDone(10)
    IntroRunningAfter = IntroQuest.IsRunning()
    IntroScenePlayingAfter = IntroScene.IsPlaying()
    If !IntroStage10After || IntroRunningAfter || IntroScenePlayingAfter
        Return False
    EndIf
    If !SetupStillAuthorized(expectedRun)
        Return False
    EndIf
    fixtureActor.EvaluatePackage()
    Utility.Wait(0.25)
    If !SetupStillAuthorized(expectedRun)
        Return False
    EndIf
    Package currentPackage = fixtureActor.GetCurrentPackage()
    If currentPackage
        FixturePackageAfter = currentPackage.GetFormID()
    EndIf
    ; The package is observed, not assumed. Existing loaded/eligible checks
    ; still decide whether the actor can perform after the real transition.
    WorldSetupReady = True
    Return SaveResult("running", "")
EndFunction

Bool Function PrimeIntroFromExterior(String expectedRun)
    If !SetupStillAuthorized(expectedRun)
        Return False
    EndIf
    ; Actual active records: persistent marker 00096595 is spatially in
    ; Riverwood04 CELL 00009731, location 00013163. CLOC is a real entry event.
    ObjectReference exterior = Game.GetFormFromFile(0x00096595, "Skyrim.esm") as ObjectReference
    Location riverwood = Game.GetFormFromFile(0x00013163, "Skyrim.esm") as Location
    If !exterior || !riverwood || Game.GetPlayer().GetCurrentLocation() == riverwood
        Return False
    EndIf
    StoryEntryAttempted = True
    If !SaveResult("running", "") || !SetupStillAuthorized(expectedRun)
        Return False
    EndIf
    Game.GetPlayer().MoveTo(exterior, 0.0, 0.0, 0.0, True)
    If !SetupStillAuthorized(expectedRun)
        Return False
    EndIf
    While StoryWaitAttempts < 80
        Location observed = Game.GetPlayer().GetCurrentLocation()
        If observed
            ExteriorLocationAfter = observed.GetFormID()
        EndIf
        StoryEntryObserved = observed == riverwood && Game.GetPlayer().Is3DLoaded()
        If StoryEntryObserved
            If IntroQuest.IsRunning()
                IntroRunningObserved = True
                Return True
            EndIf
            ; Natural completion may occur between observations. Do not try
            ; to restart an already completed/stopped event-scoped quest.
            If IntroQuest.GetStageDone(10) && !IntroScene.IsPlaying()
                IntroNaturalCompletionObserved = True
                Return True
            EndIf
        EndIf
        Utility.Wait(0.25)
        If !SetupStillAuthorized(expectedRun)
            Return False
        EndIf
        StoryWaitAttempts += 1
    EndWhile
    Return False
EndFunction

Bool Function SetupStillAuthorized(String expectedRun)
    If Finishing
        Return False
    EndIf
    If !Active || !AutomatedFixture || !WorldSetupRequested || expectedRun == "" || RunId != expectedRun
        Return False
    EndIf
    If Utility.GetCurrentRealTime() > SetupDeadline || !Guard()
        Return False
    EndIf
    If !JsonUtil.IsPathBool(ControlFile, ".allow_disposable_world_setup") || !JsonUtil.GetPathBoolValue(ControlFile, ".allow_disposable_world_setup", False)
        Return False
    EndIf
    If !JsonUtil.Load(RequestFile) || JsonUtil.GetPathStringValue(RequestFile, ".run_id", "") != expectedRun || !JsonUtil.IsPathBool(RequestFile, ".auto_run") || !JsonUtil.GetPathBoolValue(RequestFile, ".auto_run", False)
        Return False
    EndIf
    Return True
EndFunction

Bool Function ContinueRun(String expectedRun)
    ; Native calls may yield to Cleanup or a changed request. This guard is
    ; shared by manual/ordinary autorun, without requiring optional setup.
    If !Active || Finishing || expectedRun == "" || RunId != expectedRun
        Return False
    EndIf
    If BeginCancellationRequested
        Finish("cancelled", "Cleanup cancelled initial lab preparation.")
        Return False
    EndIf
    Bool authorized = Guard() && JsonUtil.Load(RequestFile) && JsonUtil.GetPathStringValue(RequestFile, ".run_id", "") == expectedRun
    If AutomatedFixture
        authorized = authorized && JsonUtil.IsPathBool(RequestFile, ".auto_run") && JsonUtil.GetPathBoolValue(RequestFile, ".auto_run", False)
    EndIf
    If WorldSetupRequested
        authorized = authorized && JsonUtil.IsPathBool(ControlFile, ".allow_disposable_world_setup") && JsonUtil.GetPathBoolValue(ControlFile, ".allow_disposable_world_setup", False)
    EndIf
    If FixtureHoldRequested
        authorized = authorized && JsonUtil.IsPathBool(ControlFile, ".allow_controlled_actor_ai") && JsonUtil.GetPathBoolValue(ControlFile, ".allow_controlled_actor_ai", False)
    EndIf
    If AutostartReady
        authorized = authorized && AutostartLeaseIntact()
    EndIf
    ; Guard/readback can themselves yield; never finish a replacement run.
    If !Active || Finishing || RunId != expectedRun
        Return False
    EndIf
    If !authorized
        Finish("failed", "Lab guard or active request changed during a native continuation.")
        Return False
    EndIf
    ; Native preparation can yield longer than a budget. Refuse the next
    ; consequential step after return; do not reset this bound on each phase.
    If Scenario != "ambient_entry" && !StartObserved && Utility.GetCurrentRealTime() >= PreparationDeadline
        Finish("failed", "Focused preparation exceeded its fixed 90-second budget.")
        Return False
    EndIf
    Return Active && !Finishing && RunId == expectedRun
EndFunction

Bool Function HourNear(Float observed, Float expected)
    ; GameHour advances naturally while scripts run. Allow three game minutes
    ; for readback, not an exact equality against a moving clock.
    Float difference = observed - expected
    Return difference > -0.05 && difference < 0.05
EndFunction

; The runner writes a new run_id before EACH new scenario. Commands during a
; scenario (Interrupt, Cleanup, Status) continue its existing request.
Function ArmAmbient()
    If Active || Finishing || BeginRunInFlight || BaselineWorkInFlight || AdmissionTransitionInFlight || FixtureTransitionInFlight || FixtureMovementUnresolved || AdmissionTicket > 0 || AdmissionAcquireInFlight || AdmissionResumeInFlight || FocusedPreparationInFlight || FocusedStartInFlight || FinishDepth > 0
        Return
    EndIf
    AutomatedFixture = False
    Location current = Game.GetPlayer().GetCurrentLocation()
    If current && current.HasKeyword(LocTypeInn)
        Log("HoldMusic LAB: ArmAmbient requires the player outside an inn.")
        Return
    EndIf
    If BeginRun("ambient_entry")
        If ResumeOwnedAdmission(RunId)
            Log("HoldMusic LAB: armed; enter the inn normally with Sven present.")
            RegisterForSingleUpdate(0.25)
        EndIf
    EndIf
EndFunction

Function FocusedStart()
    StartFocused(False)
EndFunction

Function FocusedInterrupt()
    StartFocused(True)
EndFunction

Function StartFocused(Bool interruptAfterStart)
    If Active || Finishing || BeginRunInFlight || BaselineWorkInFlight || AdmissionTransitionInFlight || FixtureTransitionInFlight || FixtureMovementUnresolved || AdmissionTicket > 0 || AdmissionAcquireInFlight || AdmissionResumeInFlight || FocusedPreparationInFlight || FocusedStartInFlight || FinishDepth > 0
        Return
    EndIf
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
    If FocusedPreparationInFlight
        Return
    EndIf
    FocusedPreparationInFlight = True
    RunFocusedPrepared(current)
    FocusedPreparationInFlight = False
EndFunction

Function RunFocusedPrepared(Location current)
    String expectedRun = RunId
    If !ContinueRun(expectedRun)
        Return
    EndIf
    If !ResumeOwnedAdmission(expectedRun)
        Return
    EndIf
    ; This is explicit direct setup, NOT evidence of a real player-entry event.
    ; Production Venue is private and set only by its entry handler.
    Controller.OnLocationChange(None, current)
    If !ContinueRun(expectedRun)
        Return
    EndIf
    Controller.UnregisterForUpdate()
    If FixtureHoldRequested && !ObserveStandingFixture()
        Finish("failed", "Controlled fixture lost its verified standing package before selection.")
        Return
    EndIf
    ScanStartedAt = Utility.GetCurrentRealTime()
    Actor[] candidates = MiscUtil.ScanCellNPCs(Game.GetPlayer(), 2000.0, None, False)
    If !ContinueRun(expectedRun)
        Return
    EndIf
    ScanFinishedAt = Utility.GetCurrentRealTime()
    Actor target = None
    Int i = 0
    While i < candidates.Length && !target
        If Library.FindPerformer(candidates[i]) == "sven"
            target = candidates[i]
        EndIf
        i += 1
    EndWhile
    If !ContinueRun(expectedRun)
        Return
    EndIf
    MatchingFinishedAt = Utility.GetCurrentRealTime()
    RecordFixtureDiagnostics(target, candidates.Length, "focused_scan")
    If !ContinueRun(expectedRun)
        Return
    EndIf
    DiagnosticsFinishedAt = Utility.GetCurrentRealTime()
    If !target || Library.Owner("sven") != "hold_music" || !Controller.Eligible(target)
        Finish("failed", "Sven must be loaded, eligible, and owned by Hold Music.")
        Return
    EndIf
    If !ContinueRun(expectedRun)
        Return
    EndIf
    SelectionStartedAt = Utility.GetCurrentRealTime()
    String region = Library.Region("sven")
    If !ContinueRun(expectedRun)
        Return
    EndIf
    Int chosen = Library.ChooseSlot("sven", region, "instrumental")
    If !ContinueRun(expectedRun)
        Return
    EndIf
    SelectedSlot = chosen
    SelectionFinishedAt = Utility.GetCurrentRealTime()
    If region == "" || SelectedSlot < 1 || SelectedSlot > 24
        Finish("failed", "No compatible unlocked fixture recording.")
        Return
    EndIf
    If Controller.SlotSounds.Length != 24 || !Controller.SlotSounds[SelectedSlot - 1]
        Finish("failed", "Selected slot has no bound Sound form.")
        Return
    EndIf
    FixtureDuration = Library.Duration()
    If FixtureDuration <= 0.0 || FixtureDuration > 30.0
        Finish("failed", "Lab fixture duration must be positive and at most 30 seconds.")
        Return
    EndIf
    String identity = RecordingIdentity(SelectedSlot)
    If !ContinueRun(expectedRun)
        Return
    EndIf
    SelectedIdentity = identity
    If SelectedIdentity == ""
        Finish("failed", "Lab fixture requires an explicit projected recording identity.")
        Return
    EndIf
    If FixtureHoldRequested && !ObserveStandingFixture()
        Finish("failed", "Controlled fixture lost its standing package before start.")
        Return
    EndIf
    If !ContinueRun(expectedRun)
        Return
    EndIf
    SelectionObserved = True
    FocusedStartInFlight = True
    Controller.StartPerformance(target, "sven", region, SelectedSlot)
    If !ContinueRun(expectedRun)
        ; Cleanup cannot atomically cancel the production start stack. Its
        ; terminal result records this pending stop; compensate only after
        ; the start returns, without rewriting that terminal evidence.
        FocusedStartInFlight = False
        AdvanceCleanup()
        Return
    EndIf
    FocusedStartInFlight = False
    CollectEvidence()
    If !ContinueRun(expectedRun)
        Return
    EndIf
    If !StartObserved
        Finish("failed", "No fresh production performance_start after direct start.")
        Return
    EndIf
    If Utility.GetCurrentRealTime() >= PlaybackDeadline
        Finish("failed", "Focused playback evidence was first observed after its fixed deadline.")
        Return
    EndIf
    If AutomatedFixture && Scenario == "focused_interrupt" && !InterruptRequested
        ; The full evidence save took over five seconds in the engine. Issue
        ; the request before that persistence, after a bounded two-second
        ; playback observation, so an eight-second fixture is not missed.
        Float untilRequest = StartTraceAt + 2.0 - Utility.GetCurrentRealTime()
        If untilRequest > 0.0 && untilRequest <= 2.0
            Utility.Wait(untilRequest)
        EndIf
        If !ContinueRun(expectedRun)
            Return
        EndIf
        If Utility.GetCurrentRealTime() >= StartTraceAt + FixtureDuration
            InterruptWindowMissed = True
            Finish("failed", "Fixture ended before the early interruption request could be issued.")
            Return
        EndIf
        Interrupt()
        If !ContinueRun(expectedRun)
            Return
        EndIf
    EndIf
    If !SaveResult("running", "")
        Finish("failed", "Could not save evidence after focused start.")
        Return
    EndIf
    If ContinueRun(expectedRun)
        RegisterForSingleUpdate(0.25)
    EndIf
EndFunction

Function RecordFixtureDiagnostics(Actor scanned, Int scannedCount, String phase)
    ; Integer flags keep the failure diagnostics usable even if JSON boolean
    ; serialization itself is the problem under investigation.
    Actor reference = Game.GetFormFromFile(0x00013491, "Skyrim.esm") as Actor
    String path = ".fixture_diagnostics"
    JsonUtil.SetPathStringValue(ResultFile, path + ".phase", phase)
    JsonUtil.SetPathIntValue(ResultFile, path + ".scan_count", scannedCount)
    JsonUtil.SetPathIntValue(ResultFile, path + ".scanned_sven_flag", (scanned != None) as Int)
    JsonUtil.SetPathIntValue(ResultFile, path + ".reference_present_flag", (reference != None) as Int)
    JsonUtil.SetPathStringValue(ResultFile, path + ".owner", Library.Owner("sven"))
    JsonUtil.SetPathStringValue(ResultFile, path + ".region", Library.Region("sven"))
    If reference
        JsonUtil.SetPathIntValue(ResultFile, path + ".actor_form_id", reference.GetFormID())
        JsonUtil.SetPathStringValue(ResultFile, path + ".registry_id", Library.FindPerformer(reference))
        JsonUtil.SetPathIntValue(ResultFile, path + ".loaded_flag", reference.Is3DLoaded() as Int)
        JsonUtil.SetPathIntValue(ResultFile, path + ".dead_flag", reference.IsDead() as Int)
        JsonUtil.SetPathIntValue(ResultFile, path + ".combat_flag", reference.IsInCombat() as Int)
        JsonUtil.SetPathIntValue(ResultFile, path + ".dialogue_flag", reference.IsInDialogueWithPlayer() as Int)
        JsonUtil.SetPathIntValue(ResultFile, path + ".follower_flag", reference.IsInFaction(Controller.CurrentFollowerFaction) as Int)
        JsonUtil.SetPathIntValue(ResultFile, path + ".sit_state", reference.GetSitState())
        JsonUtil.SetPathIntValue(ResultFile, path + ".sleep_state", reference.GetSleepState())
        JsonUtil.SetPathIntValue(ResultFile, path + ".same_cell_flag", (reference.GetParentCell() == Game.GetPlayer().GetParentCell()) as Int)
        JsonUtil.SetPathIntValue(ResultFile, path + ".eligible_flag", Controller.Eligible(reference) as Int)
        JsonUtil.SetPathFloatValue(ResultFile, path + ".distance_to_player", reference.GetDistance(Game.GetPlayer()))
    EndIf
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
    If BeginRunInFlight || BaselineWorkInFlight || AdmissionTransitionInFlight || FixtureTransitionInFlight || FixtureMovementUnresolved
        Return False
    EndIf
    BeginRunInFlight = True
    BeginCancellationRequested = False
    Bool beganRun = BeginRunWork(name)
    BeginRunInFlight = False
    If Finishing
        AdvanceCleanup()
    EndIf
    Return beganRun && Active && !Finishing && !BeginCancellationRequested
EndFunction

Bool Function BeginRunWork(String name)
    If Active || Finishing || AdmissionTicket > 0 || AdmissionAcquireInFlight || AdmissionResumeInFlight || AdmissionFault || CleanupAdvancing || GlobalsSaved || GameHourSaved || FixtureHoldIntent || FixtureHoldOwned || FixtureHoldCallInFlight || AutostartPreparing || AutostartIntent || AutostartCallInFlight || AutostartReleaseInFlight || FocusedPreparationInFlight || FocusedStartInFlight || FinishDepth > 0
        Log("HoldMusic LAB: a run is active; Cleanup before beginning another.")
        Return False
    EndIf
    If !Guard()
        Return False
    EndIf
    ReferenceAlias available = Self.GetAlias(0) as ReferenceAlias
    If !available || available.GetReference()
        Log("HoldMusic LAB: fixture alias must exist and be empty before a run.")
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
    TraceBaseline = 0
    TraceCursor = 0
    ReceiptBaseline = 0
    RunId = requestedId
    StartedAtUtc = requestedUtc
    Scenario = name
    ExpectedOutcome = "completed"
    If Scenario == "focused_interrupt"
        ; Match the intended outcome before collecting ANY receipt. A delayed
        ; poll must not first accept completion, then relabel it interruption.
        ExpectedOutcome = "interrupted"
    EndIf
    Began = Utility.GetCurrentRealTime()
    Deadline = Began + 120.0
    PreparationDeadline = 0.0
    PlaybackDeadline = 0.0
    FixtureDuration = 0.0
    If Scenario != "ambient_entry"
        PreparationDeadline = Began + 90.0
        Deadline = PreparationDeadline
    EndIf
    SelectedSlot = 0
    ReceiptIndex = -1
    SelectedIdentity = ""
    EntryObserved = False
    ScanObserved = False
    CandidateObserved = False
    SelectionObserved = False
    StartObserved = False
    StartObservedAt = 0.0
    StartTraceAt = 0.0
    StopObserved = False
    ProductionStopSeen = False
    ReceiptObserved = False
    IdentityObserved = False
    InterruptRequested = False
    InterruptRequestedAt = 0.0
    InterruptWindowMissed = False
    RequestedInterruptGuardObserved = False
    CleanupObserved = False
    EvidenceValid = True
    FailureReason = ""
    AwaitingFocusedEntry = False
    FixtureMoved = False
    WorldSetupRequested = False
    WorldSetupReady = False
    WorldBaselineObserved = False
    SetupDeadline = 0.0
    SetupFinishedAt = 0.0
    OldGameHour = 0.0
    LabGameHour = None
    IntroQuest = None
    IntroScene = None
    ConfiguredGameHour = 0.0
    IntroStageBefore = 0
    IntroStageAfter = 0
    IntroStage10Before = False
    IntroStage10After = False
    IntroRunningBefore = False
    IntroRunningAfter = False
    IntroScenePlayingAfter = False
    FixturePackageAfter = 0
    MainQuestStageBefore = -1
    StoryEntryAttempted = False
    StoryEntryObserved = False
    IntroRunningObserved = False
    IntroNaturalCompletionObserved = False
    IntroCleanupRequested = False
    IntroCleanupAccepted = False
    StoryWaitAttempts = 0
    ExteriorLocationAfter = 0
    FixtureHoldAlias = None
    FixtureHoldPackage = None
    FixtureHeldActor = None
    FixtureHoldRequested = False
    FixtureHoldIntent = False
    FixtureHoldCallInFlight = False
    FixtureHoldOwned = False
    FixtureHoldAcquired = False
    FixtureHoldReleased = False
    FixtureStandingObserved = False
    PackageBeforeHold = 0
    PackageDuringHold = 0
    PackageAfterRelease = 0
    AutostartFaction = None
    AutostartActor = None
    AutostartPreparing = False
    AutostartIntent = False
    AutostartBaselineObserved = False
    AutostartBaselineMember = False
    AutostartBaselineRank = -1
    AutostartWriteIssued = False
    AutostartCallInFlight = False
    AutostartReleaseInFlight = False
    AutostartReady = False
    AutostartAcquired = False
    AutostartReleased = False
    AutostartConflict = False
    AutostartObservedRank = -1
    AutostartPackageBefore = 0
    AutostartDialogueBefore = False
    AutostartSceneBefore = False
    AutostartStarterBefore = False
    ScanStartedAt = 0.0
    ScanFinishedAt = 0.0
    MatchingFinishedAt = 0.0
    DiagnosticsFinishedAt = 0.0
    SelectionStartedAt = 0.0
    SelectionFinishedAt = 0.0
    EvidenceCollectionStartedAt = 0.0
    EvidenceCollectionFinishedAt = 0.0
    EvidenceCollectionMaxSeconds = 0.0
    PreviousResultSaveSeconds = 0.0
    ResultSaveMaxSeconds = 0.0
    AdmissionTicket = 0
    AdmissionAcquireInFlight = False
    AdmissionResumeInFlight = False
    AdmissionFault = False
    AdmissionDrainedObserved = False
    AdmissionRestored = False
    InitialDrainPending = False
    BaselinesReady = False
    AdmissionDeadline = Began + 15.0
    Finishing = False
    CleanupAdvancing = False
    TerminalFrozen = False
    PendingFinishStatus = ""
    PendingFinishReason = ""
    CleanupDeadline = 0.0
    AwaitingAmbientExit = False
    AmbientExitObserved = False
    AmbientEntryAfterResume = False
    JsonUtil.ClearAll(ResultFile)
    If BeginCancellationRequested
        Return False
    EndIf
    Active = True
    ; Establish fresh evidence on disk before enabling/scheduling any test.
    If !SaveResult("running", "")
        Active = False
        Return False
    EndIf
    String expectedRun = RunId
    If !AcquireAdmission(expectedRun) || !ContinueRun(expectedRun)
        If Active && !Finishing
            Finish("failed", "Could not acquire an owned controller admission ticket.")
        EndIf
        Return False
    EndIf
    If !Controller.IsAdmissionDrained(AdmissionTicket)
        InitialDrainPending = True
        RegisterForSingleUpdate(0.25)
        Return False
    EndIf
    Return CompleteInitialDrain(expectedRun)
EndFunction

Bool Function CompleteInitialDrain(String expectedRun)
    If BaselineWorkInFlight
        Return False
    EndIf
    BaselineWorkInFlight = True
    Bool prepared = CompleteInitialDrainWork(expectedRun)
    BaselineWorkInFlight = False
    If Finishing && !BeginRunInFlight
        AdvanceCleanup()
    EndIf
    Return prepared && Active && !Finishing && RunId == expectedRun
EndFunction

Bool Function CompleteInitialDrainWork(String expectedRun)
    If !ContinueRun(expectedRun) || !CleanupAdmissionReady()
        Return False
    EndIf
    AdmissionDrainedObserved = True
    InitialDrainPending = False
    ; Prior cancellation/stop receipts become visible before these baselines.
    TraceBaseline = LastTraceSequence()
    TraceCursor = TraceBaseline
    ReceiptBaseline = JsonUtil.PathCount(Library.ReceiptsFile, ".performances")
    If !ContinueRun(expectedRun)
        Return False
    EndIf
    BaselinesReady = True
    OldEnabled = HM_Enabled.GetValue()
    OldInstrumental = HM_InstrumentalPercent.GetValue()
    OldCap = HM_SessionCap.GetValue()
    OldMinDelay = HM_MinDelaySeconds.GetValue()
    OldMaxDelay = HM_MaxDelaySeconds.GetValue()
    If !ContinueRun(expectedRun)
        Return False
    EndIf
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
    Return ContinueRun(expectedRun)
EndFunction

Event OnUpdate()
    If Finishing
        AdvanceCleanup()
        Return
    EndIf
    If StartupPending
        TryAutorun()
        Return
    EndIf
    If !Active
        Return
    EndIf
    String expectedRun = RunId
    Float now = Utility.GetCurrentRealTime()
    If now < Began
        Finish("failed", "Real-time clock reset; stale saved test state.")
        Return
    EndIf
    If !ContinueRun(expectedRun)
        Return
    EndIf
    If InitialDrainPending
        If now >= AdmissionDeadline
            Finish("failed", "Initial controller work did not drain within its fixed budget.")
        ElseIf Controller.IsAdmissionDrained(AdmissionTicket)
            If CompleteInitialDrain(expectedRun)
                If AutomatedFixture
                    PrepareAutorun()
                ElseIf Scenario == "ambient_entry"
                    If ResumeOwnedAdmission(expectedRun)
                        RegisterForSingleUpdate(0.25)
                    EndIf
                Else
                    StartFocusedPrepared(Game.GetPlayer().GetCurrentLocation())
                EndIf
            EndIf
        Else
            RegisterForSingleUpdate(0.25)
        EndIf
        Return
    EndIf
    If AwaitingAmbientExit
        ContinueAmbientReentry(expectedRun)
        Return
    EndIf
    If AwaitingFocusedEntry
        Location current = Game.GetPlayer().GetCurrentLocation()
        Actor fixtureActor = Game.GetFormFromFile(0x00013491, "Skyrim.esm") as Actor
        If current && current.HasKeyword(LocTypeInn) && fixtureActor && fixtureActor.Is3DLoaded() && Game.GetPlayer().Is3DLoaded() && fixtureActor.GetParentCell() == Game.GetPlayer().GetParentCell() && (!FixtureHoldRequested || ObserveStandingFixture())
            AwaitingFocusedEntry = False
            If Scenario == "ambient_entry"
                PrepareAmbientExit(expectedRun)
            Else
                StartFocusedPrepared(current)
            EndIf
        ElseIf now >= Deadline
            RecordFixtureDiagnostics(None, 0, "waiting_for_loaded_fixture")
            Finish("failed", "Timed out waiting for the scripted inn transition and loaded standing fixture.")
        Else
            RecordFixtureDiagnostics(None, 0, "waiting_for_loaded_fixture")
            If !ContinueRun(expectedRun)
                Return
            EndIf
            If !SaveResult("running", "")
                Finish("failed", "Could not save evidence while waiting for the loaded fixture.")
                Return
            EndIf
            If ContinueRun(expectedRun)
                RegisterForSingleUpdate(0.25)
            EndIf
        EndIf
        Return
    EndIf
    If FixtureHoldRequested && !FixtureStandingObserved
        ObserveStandingFixture()
    EndIf
    ; Once start was observed, issue the two-second interruption before a
    ; potentially expensive JSON scan. Acceptance still requires the fresh
    ; interrupted receipt; a completed/unsolicited stop cannot be relabelled.
    now = Utility.GetCurrentRealTime()
    If Scenario == "focused_interrupt" && StartObserved && !InterruptRequested && now >= StartTraceAt + FixtureDuration
        InterruptWindowMissed = True
    EndIf
    If Scenario == "focused_interrupt" && StartObserved && !InterruptRequested && !ProductionStopSeen && now >= StartTraceAt + 2.0 && now < StartTraceAt + FixtureDuration && now < Deadline
        Interrupt()
        If !ContinueRun(expectedRun)
            Return
        EndIf
    EndIf
    CollectEvidence()
    If !ContinueRun(expectedRun)
        Return
    EndIf
    now = Utility.GetCurrentRealTime()
    If !EvidenceValid
        Finish("failed", FailureReason)
        Return
    EndIf
    If now >= Deadline
        Finish("failed", "Timed out waiting for the expected production trace and receipt.")
        Return
    EndIf
    If Scenario == "focused_interrupt" && ProductionStopSeen && !InterruptRequested
        Finish("failed", "Performance stopped before the lab issued its interruption request.")
        Return
    EndIf
    If Scenario == "focused_interrupt" && StartObserved && !InterruptRequested && now >= StartTraceAt + FixtureDuration
        InterruptWindowMissed = True
        Finish("failed", "Fixture playback window ended before an interruption request.")
        Return
    EndIf
    If Scenario == "focused_interrupt" && StartObserved && !InterruptRequested && now >= StartTraceAt + 2.0
        Interrupt()
        If !Active
            Return
        EndIf
    EndIf
    If ReceiptObserved
        Bool passed = StartObserved && StopObserved && SelectionObserved && CleanupObserved
        passed = passed && (!FixtureHoldRequested || FixtureStandingObserved)
        If Scenario == "ambient_entry"
            passed = passed && EntryObserved && ScanObserved && CandidateObserved
            If FixtureHoldRequested
                passed = passed && AmbientExitObserved && AmbientEntryAfterResume
            EndIf
        ElseIf Scenario == "focused_interrupt"
            passed = passed && InterruptRequested && RequestedInterruptGuardObserved
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
        If ContinueRun(expectedRun)
            RegisterForSingleUpdate(0.25)
        EndIf
    EndIf
EndEvent

Function Interrupt()
    If !Active || !StartObserved || ProductionStopSeen || ReceiptObserved
        Log("HoldMusic LAB: no observed active performance to interrupt.")
        Return
    EndIf
    ; Test the production poller's stop-request branch, not a direct stop call.
    ExpectedOutcome = "interrupted"
    InterruptRequestedAt = Utility.GetCurrentRealTime()
    InterruptRequested = True
    Config.StopRequested = True
    If !SaveResult("running", "")
        Finish("failed", "Could not save evidence for the interruption request.")
    EndIf
EndFunction

Function Cleanup()
    StartupPending = False
    If BeginRunInFlight
        BeginCancellationRequested = True
    EndIf
    If Finishing && TerminalFrozen
        CleanupDeadline = Utility.GetCurrentRealTime() + 15.0
    EndIf
    If Active || Finishing
        Finish("cancelled", "Explicit lab Cleanup.")
    ElseIf AdmissionTicket > 0 || GlobalsSaved || GameHourSaved || FixtureHoldIntent || FixtureHoldOwned || AutostartIntent
        ; Reconciliation may release old ownership but never upgrade its
        ; already published terminal result or silently start another test.
        Finishing = True
        TerminalFrozen = True
        CleanupDeadline = Utility.GetCurrentRealTime() + 15.0
        AdvanceCleanup()
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
    EvidenceCollectionStartedAt = Utility.GetCurrentRealTime()
    CollectEvidenceRows()
    EvidenceCollectionFinishedAt = Utility.GetCurrentRealTime()
    Float elapsed = EvidenceCollectionFinishedAt - EvidenceCollectionStartedAt
    If elapsed > EvidenceCollectionMaxSeconds
        EvidenceCollectionMaxSeconds = elapsed
    EndIf
EndFunction

Function CollectEvidenceRows()
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
                If !StartObserved
                    ; Loading and fixture setup do not count as playback time.
                    StartObservedAt = Utility.GetCurrentRealTime()
                    StartTraceAt = JsonUtil.GetPathFloatValue(Library.TraceFile, path + ".real_seconds", -1.0)
                    If !JsonUtil.IsPathNumber(Library.TraceFile, path + ".real_seconds") || StartTraceAt < Began || StartTraceAt > StartObservedAt + 0.1
                        EvidenceValid = False
                        FailureReason = "Fresh performance_start has no valid production timestamp."
                        Return
                    EndIf
                    If Scenario != "ambient_entry"
                        ; One fixed deadline from the production trace, never
                        ; from a late poll or repeated observation. The bounded
                        ; fixture is <=30 seconds, plus 20 for receipt evidence.
                        PlaybackDeadline = StartTraceAt + FixtureDuration + 20.0
                        Deadline = PlaybackDeadline
                    EndIf
                EndIf
                StartObserved = True
            ElseIf Scenario == "focused_interrupt" && StartObserved && eventName == "performance_interrupt_guard" && StringUtil.Find(detail, "id=sven slot=" + SelectedSlot + " ") == 0
                Float guardTime = JsonUtil.GetPathFloatValue(Library.TraceFile, path + ".real_seconds", -1.0)
                If !InterruptRequested || (JsonUtil.IsPathNumber(Library.TraceFile, path + ".real_seconds") && guardTime < InterruptRequestedAt)
                    EvidenceValid = False
                    FailureReason = "Performance stopped before the lab issued its interruption request."
                    Return
                ElseIf StringUtil.Find(detail, "id=sven slot=" + SelectedSlot + " reason=stop_requested ") == 0 && JsonUtil.IsPathNumber(Library.TraceFile, path + ".real_seconds") && guardTime >= InterruptRequestedAt && guardTime <= Utility.GetCurrentRealTime()
                    RequestedInterruptGuardObserved = True
                Else
                    EvidenceValid = False
                    FailureReason = "Production interruption guard does not match the lab stop request."
                    Return
                EndIf
            ElseIf StartObserved && eventName == "performance_stop" && StringUtil.Find(detail, " id=sven slot=") >= 0 && SlotFromDetail(detail) == SelectedSlot
                ProductionStopSeen = True
                If Scenario == "focused_interrupt" && detail != "outcome=interrupted id=sven slot=" + SelectedSlot
                    EvidenceValid = False
                    FailureReason = "Production stop was not the requested interruption."
                    Return
                EndIf
                If Scenario == "focused_interrupt" && InterruptRequested
                    Float stopTime = JsonUtil.GetPathFloatValue(Library.TraceFile, path + ".real_seconds", -1.0)
                    If !JsonUtil.IsPathNumber(Library.TraceFile, path + ".real_seconds") || stopTime < InterruptRequestedAt
                        EvidenceValid = False
                        FailureReason = "Performance stopped before the lab issued its interruption request, or its timestamp is invalid."
                        Return
                    EndIf
                EndIf
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
            If Scenario == "focused_interrupt" && InterruptRequestedAt >= JsonUtil.GetPathFloatValue(Library.ReceiptsFile, row + ".started_real_seconds", 0.0) + FixtureDuration
                InterruptWindowMissed = True
                EvidenceValid = False
                FailureReason = "Interruption request was outside the receipt's actual production duration."
                Return
            EndIf
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
    If FixtureTransitionInFlight || FixtureMovementUnresolved || !CleanupAdmissionReady()
        Return False
    EndIf
    If GlobalsSaved
        HM_Enabled.SetValue(OldEnabled)
        HM_InstrumentalPercent.SetValue(OldInstrumental)
        HM_SessionCap.SetValue(OldCap)
        HM_MinDelaySeconds.SetValue(OldMinDelay)
        HM_MaxDelaySeconds.SetValue(OldMaxDelay)
        GlobalsSaved = HM_Enabled.GetValue() != OldEnabled || HM_InstrumentalPercent.GetValue() != OldInstrumental || HM_SessionCap.GetValue() != OldCap || HM_MinDelaySeconds.GetValue() != OldMinDelay || HM_MaxDelaySeconds.GetValue() != OldMaxDelay
    EndIf
    If GameHourSaved
        LabGameHour.SetValue(OldGameHour)
        GameHourSaved = !HourNear(LabGameHour.GetValue(), OldGameHour)
    EndIf
    Bool released = ReleaseFixtureHold()
    Bool suppressionReleased = False
    If released
        suppressionReleased = ReleaseAutostartLease()
    EndIf
    Return !GlobalsSaved && !GameHourSaved && released && suppressionReleased
EndFunction

Function Finish(String status, String reason)
    FinishDepth += 1
    FinishWork(status, reason)
    FinishDepth -= 1
EndFunction

Function FinishWork(String status, String reason)
    If !Active && !Finishing
        Return
    EndIf
    FinishEpoch += 1
    Int expectedFinish = FinishEpoch
    Bool firstFinish = !Finishing
    Finishing = True
    InitialDrainPending = False
    AwaitingFocusedEntry = False
    AwaitingAmbientExit = False
    PendingFinishStatus = status
    PendingFinishReason = reason
    If firstFinish
        Float nextDeadline = Utility.GetCurrentRealTime() + 15.0
        If expectedFinish != FinishEpoch
            Return
        EndIf
        CleanupDeadline = nextDeadline
    EndIf
    UnregisterForUpdate()
    AdvanceCleanup()
EndFunction

Bool Function AcquireAdmission(String expectedRun)
    If expectedRun != RunId || AdmissionFault || AdmissionAcquireInFlight || AdmissionResumeInFlight
        Return False
    EndIf
    If AdmissionTicket > 0
        Return True
    EndIf
    AdmissionAcquireInFlight = True
    Int acquired = Controller.SuspendAdmission()
    ; BeginRun is blocked throughout the call. Even a cancelled caller owns
    ; a late positive ticket and must not drop it or borrow a foreign hold.
    If acquired > 0
        AdmissionTicket = acquired
        AdmissionRestored = False
    Else
        AdmissionFault = True
    EndIf
    AdmissionAcquireInFlight = False
    Return acquired > 0 && expectedRun == RunId
EndFunction

Bool Function CleanupAdmissionReady()
    If AdmissionTicket <= 0 || AdmissionFault || AdmissionAcquireInFlight || AdmissionResumeInFlight || FocusedStartInFlight || FixtureMovementUnresolved
        Return False
    EndIf
    Return Controller.IsAdmissionDrained(AdmissionTicket)
EndFunction

Bool Function ResumeOwnedAdmission(String expectedRun, Bool finishingCall = False)
    If AdmissionTransitionInFlight
        Return False
    EndIf
    AdmissionTransitionInFlight = True
    Bool resumed = ResumeOwnedAdmissionWork(expectedRun, finishingCall)
    AdmissionTransitionInFlight = False
    If Finishing && !CleanupAdvancing
        AdvanceCleanup()
    EndIf
    Return resumed && expectedRun == RunId && (finishingCall || (Active && !Finishing))
EndFunction

Bool Function ResumeOwnedAdmissionWork(String expectedRun, Bool finishingCall = False)
    If expectedRun != RunId || AdmissionAcquireInFlight || AdmissionResumeInFlight || AdmissionFault
        Return False
    EndIf
    If AdmissionTicket <= 0
        Return !Finishing && !finishingCall
    EndIf
    Int expectedFinish = FinishEpoch
    Bool ready = CleanupAdmissionReady()
    If expectedRun != RunId || FinishEpoch != expectedFinish || (!finishingCall && Finishing)
        Return False
    EndIf
    If !ready
        If !Finishing
            Finish("failed", "Controller admission was not drained before resume.")
        EndIf
        Return False
    EndIf
    AdmissionResumeInFlight = True
    Int consumed = AdmissionTicket
    Bool resumed = Controller.ResumeAdmission(consumed)
    If resumed
        AdmissionTicket = 0
        AdmissionRestored = True
    EndIf
    AdmissionResumeInFlight = False
    ; The callee's atomic resume does not make its scripted-call boundary
    ; atomic. A late success after cancellation needs a NEW owned hold.
    If expectedRun != RunId || FinishEpoch != expectedFinish || (!finishingCall && Finishing)
        If resumed
            AcquireAdmission(expectedRun)
        EndIf
        Return False
    EndIf
    If !resumed && !Finishing
        Finish("failed", "Owned controller admission could not be resumed.")
    EndIf
    If resumed && !finishingCall && !ContinueRun(expectedRun)
        Return False
    EndIf
    Return resumed
EndFunction

Function AdvanceCleanup()
    If !Finishing || CleanupAdvancing
        Return
    EndIf
    CleanupAdvancing = True
    FinishDepth += 1
    ; A direct reconciliation can overtake an already queued pending poll.
    ; Own entry first, then remove that stale timer before finalizing/resuming.
    UnregisterForUpdate()
    String expectedRun = RunId
    Int expectedFinish = FinishEpoch
    Bool ready = AcquireAdmission(expectedRun) && !BeginRunInFlight && !BaselineWorkInFlight && !AdmissionTransitionInFlight && !FixtureTransitionInFlight && CleanupAdmissionReady()
    Bool restorationFailed = False
    If ready
        AdmissionDrainedObserved = True
        ready = RestoreGlobals()
        restorationFailed = !ready
    EndIf
    If ready && PendingFinishStatus == "passed"
        If !Guard() || !JsonUtil.Load(RequestFile) || JsonUtil.GetPathStringValue(RequestFile, ".run_id", "") != expectedRun
            PendingFinishStatus = "failed"
            PendingFinishReason = "Lab guard or request changed during cleanup."
        EndIf
    EndIf
    If ready && expectedRun == RunId && expectedFinish == FinishEpoch
        ready = ResumeOwnedAdmission(expectedRun, True)
        restorationFailed = !ready
    EndIf
    If expectedRun != RunId || expectedFinish != FinishEpoch
        CleanupAdvancing = False
        FinishDepth -= 1
        If Finishing
            RegisterForSingleUpdate(0.25)
        EndIf
        Return
    EndIf
    If ready
        Active = False
        Finishing = False
        If !TerminalFrozen
            TerminalFrozen = True
            If !SaveResult(PendingFinishStatus, PendingFinishReason)
                Log("HoldMusic LAB: failed. Final result could not be serialized or saved.")
            EndIf
        EndIf
    ElseIf AdmissionFault || restorationFailed || FixtureMovementUnresolved || Utility.GetCurrentRealTime() >= CleanupDeadline
        Active = False
        UnregisterForUpdate()
        ; Keep the ticket, leases and cleanup state. No automatic retries
        ; after this bound; explicit Cleanup can attempt later reconciliation.
        If !TerminalFrozen
            TerminalFrozen = True
            SaveResult("failed", PendingFinishReason + " Controller drain or owned fixture restoration remains pending; globals/leases must be read back before release.")
        EndIf
    Else
        If PendingFinishStatus != "passed" && !TerminalFrozen
            Active = False
            TerminalFrozen = True
            SaveResult("failed", PendingFinishReason + " Controller/fixture cleanup remains pending.")
        EndIf
        RegisterForSingleUpdate(0.25)
    EndIf
    CleanupAdvancing = False
    FinishDepth -= 1
EndFunction

Function PrepareAmbientExit(String expectedRun)
    If !ContinueRun(expectedRun) || !CleanupAdmissionReady() || !ObserveStandingFixture()
        Finish("failed", "Controlled ambient setup did not retain a drained standing fixture.")
        Return
    EndIf
    ObjectReference outside = Game.GetFormFromFile(0x00096595, "Skyrim.esm") as ObjectReference
    If !outside
        Finish("failed", "Controlled ambient exterior anchor is unavailable.")
        Return
    EndIf
    If !ContinueRun(expectedRun)
        Return
    EndIf
    AwaitingAmbientExit = True
    If MoveAmbientPlayer(outside, expectedRun, False)
        RegisterForSingleUpdate(0.25)
    EndIf
EndFunction

Function ContinueAmbientReentry(String expectedRun)
    If !ContinueRun(expectedRun)
        Return
    EndIf
    Location outside = Game.GetPlayer().GetCurrentLocation()
    If Utility.GetCurrentRealTime() >= Deadline
        Finish("failed", "Controlled ambient exit did not finish within the scenario budget.")
        Return
    EndIf
    If !outside || outside.HasKeyword(LocTypeInn) || !Game.GetPlayer().Is3DLoaded() || !CleanupAdmissionReady()
        RegisterForSingleUpdate(0.25)
        Return
    EndIf
    AmbientExitObserved = True
    ObjectReference anchor = Game.GetFormFromFile(0x0010FCB7, "Skyrim.esm") as ObjectReference
    If !anchor
        Finish("failed", "Controlled ambient inn anchor is unavailable.")
        Return
    EndIf
    AwaitingAmbientExit = False
    ; Only this post-resume engine transition is the ambient test entry.
    If !MoveAmbientPlayer(anchor, expectedRun, True)
        Return
    EndIf
    AmbientEntryAfterResume = True
    RegisterForSingleUpdate(0.25)
EndFunction

Bool Function MoveAmbientPlayer(ObjectReference anchor, String expectedRun, Bool resumeBeforeMove)
    If FixtureTransitionInFlight || FixtureMovementUnresolved
        Return False
    EndIf
    FixtureTransitionInFlight = True
    Bool moved = False
    Actor player = Game.GetPlayer()
    If !player && ContinueRun(expectedRun)
        Finish("failed", "Controlled ambient player reference is unavailable.")
    EndIf
    If player && ContinueRun(expectedRun)
        Bool canMove = True
        If resumeBeforeMove
            canMove = ResumeOwnedAdmission(expectedRun)
        EndIf
        If canMove && ContinueRun(expectedRun)
            ; A cancelled submitted teleport may dispatch its location event
            ; after native return. Keep the hold/leases in that case rather
            ; than claim an engine-event queue acknowledgment we do not have.
            FixtureMovementUnresolved = True
            player.MoveTo(anchor, 0.0, 0.0, 0.0, True)
            moved = ContinueRun(expectedRun)
            If moved
                FixtureMovementUnresolved = False
            EndIf
        EndIf
    EndIf
    FixtureTransitionInFlight = False
    If Finishing
        AdvanceCleanup()
    EndIf
    Return moved && Active && !Finishing && expectedRun == RunId
EndFunction

Bool Function SaveResult(String status, String reason)
    Float started = Utility.GetCurrentRealTime()
    Bool saved = SaveResultRows(status, reason)
    PreviousResultSaveSeconds = Utility.GetCurrentRealTime() - started
    If PreviousResultSaveSeconds > ResultSaveMaxSeconds
        ResultSaveMaxSeconds = PreviousResultSaveSeconds
    EndIf
    Return saved
EndFunction

Bool Function SaveResultRows(String status, String reason)
    If status == "running" && !Active
        Return False
    EndIf
    BooleanSerializationErrors = 0
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
    JsonUtil.SetPathFloatValue(ResultFile, ".performance_start_observed_real_seconds", StartObservedAt)
    JsonUtil.SetPathFloatValue(ResultFile, ".performance_start_trace_real_seconds", StartTraceAt)
    JsonUtil.SetPathFloatValue(ResultFile, ".focused_preparation_deadline_real_seconds", PreparationDeadline)
    JsonUtil.SetPathFloatValue(ResultFile, ".focused_playback_deadline_real_seconds", PlaybackDeadline)
    JsonUtil.SetPathFloatValue(ResultFile, ".interruption_request_real_seconds", InterruptRequestedAt)
    SaveBool(".interrupt_window_missed", InterruptWindowMissed)
    JsonUtil.SetPathFloatValue(ResultFile, ".observed_real_seconds", Utility.GetCurrentRealTime())
    JsonUtil.SetPathIntValue(ResultFile, ".trace_baseline", TraceBaseline)
    JsonUtil.SetPathIntValue(ResultFile, ".trace_cursor", TraceCursor)
    JsonUtil.SetPathIntValue(ResultFile, ".receipt_baseline", ReceiptBaseline)
    SaveBool(".admission.baselines_ready", BaselinesReady)
    JsonUtil.SetPathIntValue(ResultFile, ".admission.ticket", AdmissionTicket)
    SaveBool(".admission.acquire_in_flight", AdmissionAcquireInFlight)
    SaveBool(".admission.resume_in_flight", AdmissionResumeInFlight)
    SaveBool(".admission.fault", AdmissionFault)
    SaveBool(".admission.drained_observed", AdmissionDrainedObserved)
    SaveBool(".admission.resumed", AdmissionRestored)
    SaveBool(".admission.cleanup_pending", Finishing)
    SaveBool(".admission.initial_drain_pending", InitialDrainPending)
    SaveBool(".admission.begin_in_flight", BeginRunInFlight)
    SaveBool(".admission.baseline_work_in_flight", BaselineWorkInFlight)
    SaveBool(".admission.transition_in_flight", AdmissionTransitionInFlight)
    SaveBool(".admission.fixture_transition_in_flight", FixtureTransitionInFlight)
    SaveBool(".admission.fixture_movement_unresolved", FixtureMovementUnresolved)
    JsonUtil.SetPathStringValue(ResultFile, ".admission.pending_finish_reason", PendingFinishReason)
    JsonUtil.SetPathFloatValue(ResultFile, ".admission.initial_deadline", AdmissionDeadline)
    JsonUtil.SetPathFloatValue(ResultFile, ".admission.cleanup_deadline", CleanupDeadline)
    JsonUtil.SetPathStringValue(ResultFile, ".admission.scope", "hold_music_owned_work")
    SaveBool(".admission.all_engine_work_drained", False)
    SaveBool(".ambient_fixture_exit_observed", AmbientExitObserved)
    SaveBool(".ambient_entry_after_resume", AmbientEntryAfterResume)
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
    SaveBool(".focused_start_in_flight", FocusedStartInFlight)
    SaveBool(".focused_start_cleanup_pending", FocusedStartInFlight && !Active)
    SaveBool(".globals_restored", !GlobalsSaved && !GameHourSaved && !Active && !BeginRunInFlight && !BaselineWorkInFlight && !FixtureTransitionInFlight && !FixtureMovementUnresolved)
    SaveBool(".controlled_actor_ai", FixtureHoldAcquired)
    SaveBool(".normal_actor_ai_behavior_verified", False)
    SaveBool(".fixture_ai.requested", FixtureHoldRequested)
    SaveBool(".fixture_ai.acquisition_intent", FixtureHoldIntent)
    SaveBool(".fixture_ai.acquisition_in_flight", FixtureHoldCallInFlight)
    SaveBool(".fixture_ai.acquired", FixtureHoldAcquired)
    SaveBool(".fixture_ai.standing_observed", FixtureStandingObserved)
    SaveBool(".fixture_ai.released", FixtureHoldReleased)
    JsonUtil.SetPathIntValue(ResultFile, ".fixture_ai.package_before", PackageBeforeHold)
    JsonUtil.SetPathIntValue(ResultFile, ".fixture_ai.package_during", PackageDuringHold)
    JsonUtil.SetPathIntValue(ResultFile, ".fixture_ai.package_after_release", PackageAfterRelease)
    SaveBool(".vanilla_autostart.requested", FixtureHoldRequested)
    SaveBool(".vanilla_autostart.baseline_observed", AutostartBaselineObserved)
    SaveBool(".vanilla_autostart.baseline_member", AutostartBaselineMember)
    JsonUtil.SetPathIntValue(ResultFile, ".vanilla_autostart.baseline_rank", AutostartBaselineRank)
    SaveBool(".vanilla_autostart.intent", AutostartIntent)
    SaveBool(".vanilla_autostart.write_issued", AutostartWriteIssued)
    SaveBool(".vanilla_autostart.mutation_in_flight", AutostartCallInFlight || AutostartReleaseInFlight)
    SaveBool(".vanilla_autostart.verified", AutostartAcquired)
    SaveBool(".vanilla_autostart.released", AutostartReleased)
    SaveBool(".vanilla_autostart.conflict", AutostartConflict)
    JsonUtil.SetPathIntValue(ResultFile, ".vanilla_autostart.observed_rank", AutostartObservedRank)
    JsonUtil.SetPathIntValue(ResultFile, ".vanilla_autostart.package_before", AutostartPackageBefore)
    SaveBool(".vanilla_autostart.dialogue_before", AutostartDialogueBefore)
    SaveBool(".vanilla_autostart.scene_before", AutostartSceneBefore)
    SaveBool(".vanilla_autostart.starter_running_before", AutostartStarterBefore)
    SaveBool(".vanilla_autostart.pending_work_drained_verified", False)
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.focused_scan_started", ScanStartedAt)
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.focused_scan_finished", ScanFinishedAt)
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.focused_matching_finished", MatchingFinishedAt)
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.focused_diagnostics_finished", DiagnosticsFinishedAt)
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.focused_selection_started", SelectionStartedAt)
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.focused_selection_finished", SelectionFinishedAt)
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.fixture_duration_seconds", FixtureDuration)
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.evidence_collection_started", EvidenceCollectionStartedAt)
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.evidence_collection_finished", EvidenceCollectionFinishedAt)
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.evidence_collection_max_seconds", EvidenceCollectionMaxSeconds)
    ; The current save cannot report its own completed duration without an
    ; extra write. Publish the previous completed save and maximum so far.
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.previous_result_save_seconds", PreviousResultSaveSeconds)
    JsonUtil.SetPathFloatValue(ResultFile, ".timing.previous_result_save_max_seconds", ResultSaveMaxSeconds)
    SaveBool(".disposable_world_setup", WorldSetupRequested)
    If WorldSetupRequested
        SaveBool(".world_setup.baseline_observed", WorldBaselineObserved)
        SaveBool(".world_setup.ready", WorldSetupReady)
        JsonUtil.SetPathFloatValue(ResultFile, ".world_setup.setup_deadline_real_seconds", SetupDeadline)
        JsonUtil.SetPathFloatValue(ResultFile, ".world_setup.setup_finished_real_seconds", SetupFinishedAt)
        JsonUtil.SetPathFloatValue(ResultFile, ".world_setup.scenario_deadline_real_seconds", Deadline)
        JsonUtil.SetPathFloatValue(ResultFile, ".world_setup.game_hour_before", OldGameHour)
        JsonUtil.SetPathFloatValue(ResultFile, ".world_setup.game_hour_configured", ConfiguredGameHour)
        If LabGameHour
            JsonUtil.SetPathFloatValue(ResultFile, ".world_setup.game_hour_current", LabGameHour.GetValue())
        EndIf
        SaveBool(".world_setup.game_hour_restored", !GameHourSaved && !Active)
        JsonUtil.SetPathIntValue(ResultFile, ".world_setup.intro_stage_before", IntroStageBefore)
        JsonUtil.SetPathIntValue(ResultFile, ".world_setup.intro_stage_after", IntroStageAfter)
        SaveBool(".world_setup.intro_stage10_before", IntroStage10Before)
        SaveBool(".world_setup.intro_stage10_after", IntroStage10After)
        SaveBool(".world_setup.intro_running_before", IntroRunningBefore)
        SaveBool(".world_setup.intro_running_after", IntroRunningAfter)
        SaveBool(".world_setup.intro_scene_playing_after", IntroScenePlayingAfter)
        JsonUtil.SetPathIntValue(ResultFile, ".world_setup.package_after_evaluate", FixturePackageAfter)
        JsonUtil.SetPathIntValue(ResultFile, ".world_setup.mq102_stage_before_read_only", MainQuestStageBefore)
        SaveBool(".world_setup.story_entry_attempted", StoryEntryAttempted)
        SaveBool(".world_setup.story_entry_observed", StoryEntryObserved)
        SaveBool(".world_setup.intro_running_observed", IntroRunningObserved)
        SaveBool(".world_setup.intro_natural_completion_observed", IntroNaturalCompletionObserved)
        SaveBool(".world_setup.intro_cleanup_requested", IntroCleanupRequested)
        SaveBool(".world_setup.intro_cleanup_accepted", IntroCleanupAccepted)
        JsonUtil.SetPathIntValue(ResultFile, ".world_setup.story_wait_attempts", StoryWaitAttempts)
        JsonUtil.SetPathIntValue(ResultFile, ".world_setup.exterior_location_after", ExteriorLocationAfter)
        SaveBool(".world_setup.quest_history_restored", False)
        SaveBool(".world_setup.normal_quest_playthrough_verified", False)
    EndIf
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
    SaveBool(".assertions.requested_interruption_guard", RequestedInterruptGuardObserved)
    SaveBool(".assertions.cleanup_trace_and_receipt", CleanupObserved)
    SaveBool(".assertions.evidence_valid", EvidenceValid)
    JsonUtil.SetPathIntValue(ResultFile, ".boolean_serialization_errors", BooleanSerializationErrors)
    If BooleanSerializationErrors > 0
        JsonUtil.SetPathStringValue(ResultFile, ".status", "failed")
        JsonUtil.SetPathStringValue(ResultFile, ".reason", "Native JSON boolean serialization failed.")
        Log("HoldMusic LAB: native JSON boolean serialization failed.")
    EndIf
    Bool saved = JsonUtil.Save(ResultFile, False)
    If !saved
        Log("HoldMusic LAB: failed to save result evidence.")
    EndIf
    Return saved && BooleanSerializationErrors == 0
EndFunction

Function Log(String message)
    Debug.Trace(message, 0)
EndFunction

Function SaveBool(String path, Bool value)
    ; BSFixedString interning can reuse the spelling of bare True/False from
    ; another script. Whitespace is part of these literal intern keys and is
    ; legal JSON padding. Never assemble them from an already-interned token.
    String raw = " false "
    If value
        raw = " true "
    EndIf
    Bool parsed = JsonUtil.SetRawPathValue(ResultFile, path, raw)
    If !parsed || !JsonUtil.IsPathBool(ResultFile, path) || JsonUtil.GetPathBoolValue(ResultFile, path, !value) != value
        BooleanSerializationErrors += 1
    EndIf
EndFunction
