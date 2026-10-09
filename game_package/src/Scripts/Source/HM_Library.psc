Scriptname HM_Library extends Quest

; Paths are relative to Data/SKSE/Plugins/StorageUtilData, not Data.
String Property LibraryFile = "HoldMusic/library.json" Auto
String Property ReceiptsFile = "HoldMusic/receipts.json" Auto
String Property RegistryFile = "../HoldMusic/registry.json" Auto
Bool[] Locked
String ActiveComposition = ""
Float ActiveDuration
String SaveId = ""

Function ResetSession()
    Locked = new Bool[24]
EndFunction

String Function FindPerformer(Actor candidate)
    If !candidate || !JsonUtil.Load(RegistryFile)
        Return ""
    EndIf
    Int i = 0
    Int count = JsonUtil.PathCount(RegistryFile, ".performers")
    While i < count
        String path = ".performers[" + i + "]"
        Bool match = False
        If JsonUtil.IsPathObject(RegistryFile, path + ".form")
            String plugin = JsonUtil.GetPathStringValue(RegistryFile, path + ".form.plugin", "")
            Int fid = JsonUtil.GetPathIntValue(RegistryFile, path + ".form.id", 0)
            Form base = Game.GetFormFromFile(fid, plugin)
            If base && candidate.GetActorBase().GetFormID() == base.GetFormID()
                match = True
            EndIf
        ElseIf JsonUtil.PathMembers(RegistryFile, path).Find("form") >= 0 && !JsonUtil.IsPathString(RegistryFile, path + ".form") && !JsonUtil.IsPathNumber(RegistryFile, path + ".form") && !JsonUtil.IsPathBool(RegistryFile, path + ".form") && !JsonUtil.IsPathArray(RegistryFile, path + ".form")
            ; Explicit JSON null only. Missing/malformed forms never fall back.
            match = candidate.GetActorBase().GetName() == JsonUtil.GetPathStringValue(RegistryFile, path + ".name", "")
        EndIf
        If match
            Return JsonUtil.GetPathStringValue(RegistryFile, path + ".id", "")
        EndIf
        i += 1
    EndWhile
    Return ""
EndFunction

String Function Region(String performerId)
    Int i = 0
    While i < JsonUtil.PathCount(RegistryFile, ".performers")
        String path = ".performers[" + i + "]"
        If JsonUtil.GetPathStringValue(RegistryFile, path + ".id", "") == performerId
            Return JsonUtil.GetPathStringValue(RegistryFile, path + ".region", "")
        EndIf
        i += 1
    EndWhile
    Return ""
EndFunction

Int Function LastReceipt(String composition)
    Int i = JsonUtil.PathCount(ReceiptsFile, ".performances") - 1
    While i >= 0
        If JsonUtil.GetPathStringValue(ReceiptsFile, ".performances[" + i + "].composition_id", "") == composition
            Return i
        EndIf
        i -= 1
    EndWhile
    Return -1
EndFunction

Int Function ChooseSlot(String performerId, String region, String preferMode)
    If !Locked
        ResetSession()
    EndIf
    If !JsonUtil.Load(LibraryFile) || !JsonUtil.IsGood(LibraryFile)
        Return 0
    EndIf
    JsonUtil.Load(ReceiptsFile)
    Int bestSlot = 0
    Int bestRank = 2147483647
    Int bestMode = 2
    Int i = 0
    While i < JsonUtil.PathCount(LibraryFile, ".recordings")
        String path = ".recordings[" + i + "]"
        Int slot = JsonUtil.GetPathIntValue(LibraryFile, path + ".slot", 0)
        If slot >= 1 && slot <= 24
            If !Locked[slot - 1] && JsonUtil.GetPathStringValue(LibraryFile, path + ".performer_id", "") == performerId && JsonUtil.GetPathStringValue(LibraryFile, path + ".region", "") == region
                String composition = JsonUtil.GetPathStringValue(LibraryFile, path + ".composition_id", "")
                Float duration = JsonUtil.GetPathFloatValue(LibraryFile, path + ".duration_seconds", 0.0)
                String mode = JsonUtil.GetPathStringValue(LibraryFile, path + ".mode", "")
                If composition != "" && duration > 0.0 && (mode == "vocal" || mode == "wordless" || mode == "instrumental")
                    Int rank = LastReceipt(composition)
                    Int modeRank = 1
                    If mode == preferMode || (mode == "wordless" && preferMode == "vocal")
                        modeRank = 0
                    EndIf
                    ; Unperformed, then oldest receipt; requested mode breaks ties.
                    If rank < bestRank || (rank == bestRank && modeRank < bestMode)
                        bestSlot = slot
                        bestRank = rank
                        bestMode = modeRank
                        ActiveComposition = composition
                        ActiveDuration = duration
                    EndIf
                EndIf
            EndIf
        EndIf
        i += 1
    EndWhile
    Return bestSlot
EndFunction

Function LockSlot(Int slot)
    Locked[slot - 1] = True
EndFunction

Float Function Duration()
    Return ActiveDuration
EndFunction

Function AppendReceipt(Int slot, String performerId, String region, Float started, String outcome, String worldId)
    If SaveId == ""
        ; Stable per quest/save lineage, not the name of an ESS file.
        SaveId = Game.GetPlayer().GetFormID() + ":" + Game.GetPlayer().GetActorBase().GetName() + ":" + Utility.GetCurrentGameTime()
    EndIf
    JsonUtil.Load(ReceiptsFile)
    Int i = JsonUtil.PathCount(ReceiptsFile, ".performances")
    String path = ".performances[" + i + "]"
    JsonUtil.SetPathIntValue(ReceiptsFile, ".version", 1)
    JsonUtil.SetPathStringValue(ReceiptsFile, path + ".id", slot + ":" + i)
    JsonUtil.SetPathIntValue(ReceiptsFile, path + ".slot", slot)
    JsonUtil.SetPathStringValue(ReceiptsFile, path + ".performer_id", performerId)
    JsonUtil.SetPathStringValue(ReceiptsFile, path + ".region", region)
    JsonUtil.SetPathStringValue(ReceiptsFile, path + ".composition_id", ActiveComposition)
    JsonUtil.SetPathStringValue(ReceiptsFile, path + ".save_id", SaveId)
    JsonUtil.SetPathStringValue(ReceiptsFile, path + ".world_id", worldId)
    JsonUtil.SetPathFloatValue(ReceiptsFile, path + ".at_hours", Utility.GetCurrentGameTime() * 24.0)
    JsonUtil.SetPathFloatValue(ReceiptsFile, path + ".started_real_seconds", started)
    JsonUtil.SetPathStringValue(ReceiptsFile, path + ".outcome", outcome)
    If !JsonUtil.Save(ReceiptsFile, False)
        Debug.Trace("HoldMusic: receipt save failed", 0)
    EndIf
EndFunction
