Scriptname HM_Library extends Quest

; Paths are relative to Data/SKSE/Plugins/StorageUtilData, not Data.
String Property LibraryFile = "HoldMusic/library.json" Auto
String Property ReceiptsFile = "HoldMusic/receipts.json" Auto
String Property RegistryFile = "../HoldMusic/registry.json" Auto
String Property TraceFile = "HoldMusic/trace.json" Auto
Int TraceSequence = 0
Bool TraceSaveWarned = False
Bool[] Locked
String ActiveComposition = ""
Float ActiveDuration
String SaveId = ""
; Captured at selection, never reconstructed from a later library revision.
String[] ActiveIdentity
String ActiveIdentityKey = ""

Function ResetSession()
    Locked = new Bool[24]
    TraceSaveWarned = False
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

String Function Owner(String performerId)
    Int i = 0
    While i < JsonUtil.PathCount(RegistryFile, ".performers")
        String path = ".performers[" + i + "]"
        If JsonUtil.GetPathStringValue(RegistryFile, path + ".id", "") == performerId
            Return JsonUtil.GetPathStringValue(RegistryFile, path + ".owner", "")
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

String[] Function IdentityKeys()
    String[] keys = new String[10]
    keys[0] = "performer_id"
    keys[1] = "region"
    keys[2] = "recipe_id"
    keys[3] = "recipe_revision"
    keys[4] = "model_id"
    keys[5] = "instrument_family"
    keys[6] = "instrument_name"
    keys[7] = "arrangement"
    keys[8] = "mode"
    keys[9] = "voice"
    Return keys
EndFunction

Bool Function NonblankText(String path)
    If !JsonUtil.IsPathString(LibraryFile, path)
        Return False
    EndIf
    String value = JsonUtil.GetPathStringValue(LibraryFile, path, "")
    ; Caprica/Skyrim Papyrus has no carriage-return escape. Control-character
    ; code 13 has no letter case for BSFixedString interning to collapse.
    String carriageReturn = StringUtil.AsChar(13)
    Int i = 0
    While i < StringUtil.GetLength(value)
        String character = StringUtil.GetNthChar(value, i)
        If character != " " && character != "\t" && character != carriageReturn && character != "\n"
            Return True
        EndIf
        i += 1
    EndWhile
    Return False
EndFunction

Bool Function SupportedIdentity(String path, String[] keys)
    If !JsonUtil.IsPathObject(LibraryFile, path)
        Return False
    EndIf
    Int i = 0
    While i < keys.Length
        If !NonblankText(path + "." + keys[i])
            Return False
        EndIf
        i += 1
    EndWhile
    If !ValidIdentityKey(path + ".identity_key")
        Return False
    EndIf
    If JsonUtil.GetPathStringValue(LibraryFile, path + ".instrument_family", "") != "plucked_string"
        Return False
    EndIf
    String mode = JsonUtil.GetPathStringValue(LibraryFile, path + ".mode", "")
    String arrangement = JsonUtil.GetPathStringValue(LibraryFile, path + ".arrangement", "")
    String voice = JsonUtil.GetPathStringValue(LibraryFile, path + ".voice", "")
    If mode == "instrumental"
        Return arrangement == "solo_lute" && voice == "none"
    EndIf
    Return (mode == "vocal" || mode == "wordless") && arrangement == "solo_lute_and_voice" && (voice == "male" || voice == "female")
EndFunction

; Papyrus interns strings without case fidelity. A trusted Python projection
; binds all ten readable strings to this hex SHA256; do not claim that Papyrus
; can independently rehash/verify raw JSON text against this supplied key.
Bool Function ValidIdentityKey(String path)
    If !JsonUtil.IsPathString(LibraryFile, path)
        Return False
    EndIf
    String key = JsonUtil.GetPathStringValue(LibraryFile, path, "")
    If StringUtil.GetLength(key) != 64
        Return False
    EndIf
    Int i = 0
    While i < 64
        If StringUtil.Find("0123456789abcdef", StringUtil.GetNthChar(key, i), 0) < 0
            Return False
        EndIf
        i += 1
    EndWhile
    Return True
EndFunction

; -1 is legacy/no contract; -2 is malformed or ambiguous metadata.
Int Function SelectionContract(String performerId, String region, String[] keys)
    If JsonUtil.PathMembers(LibraryFile, ".").Find("runtime_selection") < 0
        Return -1
    EndIf
    String rootPath = ".runtime_selection"
    If !JsonUtil.IsPathObject(LibraryFile, rootPath) || JsonUtil.PathCount(LibraryFile, rootPath) != 2 || !JsonUtil.IsPathNumber(LibraryFile, rootPath + ".version") || JsonUtil.GetPathFloatValue(LibraryFile, rootPath + ".version", 0.0) != 1.0 || !JsonUtil.IsPathArray(LibraryFile, rootPath + ".contracts") || JsonUtil.PathCount(LibraryFile, rootPath + ".contracts") < 1
        Return -2
    EndIf
    Int match = -1
    Int i = 0
    While i < JsonUtil.PathCount(LibraryFile, rootPath + ".contracts")
        String path = rootPath + ".contracts[" + i + "]"
        If !SupportedIdentity(path, keys) || JsonUtil.PathCount(LibraryFile, path) != 11
            Return -2
        EndIf
        String id = JsonUtil.GetPathStringValue(LibraryFile, path + ".performer_id", "")
        Int j = 0
        While j < i
            If JsonUtil.GetPathStringValue(LibraryFile, rootPath + ".contracts[" + j + "].performer_id", "") == id
                Return -2
            EndIf
            j += 1
        EndWhile
        If id == performerId
            If JsonUtil.GetPathStringValue(LibraryFile, path + ".region", "") != region
                Return -2
            EndIf
            match = i
        EndIf
        i += 1
    EndWhile
    Return match
EndFunction

Bool Function HasVersionedRecording(String performerId)
    Int i = 0
    While i < JsonUtil.PathCount(LibraryFile, ".recordings")
        String path = ".recordings[" + i + "]"
        If JsonUtil.GetPathStringValue(LibraryFile, path + ".performer_id", "") == performerId
            String[] members = JsonUtil.PathMembers(LibraryFile, path)
            ; Presence matters: explicit null/partial identities are not legacy.
            If members.Find("recipe_revision") >= 0 || members.Find("instrument_family") >= 0 || members.Find("instrument_name") >= 0 || members.Find("identity_key") >= 0
                Return True
            EndIf
        EndIf
        i += 1
    EndWhile
    Return False
EndFunction

Bool Function MatchesIdentity(String path, String contract, String[] keys)
    If !SupportedIdentity(path, keys) || !JsonUtil.IsPathBool(LibraryFile, path + ".playable") || !JsonUtil.GetPathBoolValue(LibraryFile, path + ".playable", False)
        Return False
    EndIf
    Int i = 0
    While i < keys.Length
        If JsonUtil.GetPathStringValue(LibraryFile, path + "." + keys[i], "") != JsonUtil.GetPathStringValue(LibraryFile, contract + "." + keys[i], "")
            Return False
        EndIf
        i += 1
    EndWhile
    Return JsonUtil.GetPathStringValue(LibraryFile, path + ".identity_key", "") == JsonUtil.GetPathStringValue(LibraryFile, contract + ".identity_key", "")
EndFunction

Int Function ChooseSlot(String performerId, String region, String preferMode)
    If !Locked
        ResetSession()
    EndIf
    If !JsonUtil.Load(LibraryFile) || !JsonUtil.IsGood(LibraryFile)
        Return 0
    EndIf
    ActiveIdentity = None
    ActiveIdentityKey = ""
    String[] keys = IdentityKeys()
    Int contractIndex = SelectionContract(performerId, region, keys)
    If contractIndex == -2 || (contractIndex < 0 && HasVersionedRecording(performerId))
        Return 0
    EndIf
    String contract = ".runtime_selection.contracts[" + contractIndex + "]"
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
                If composition != "" && duration > 0.0 && (mode == "vocal" || mode == "wordless" || mode == "instrumental") && (contractIndex < 0 || MatchesIdentity(path, contract, keys))
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
                        If contractIndex >= 0
                            ActiveIdentityKey = JsonUtil.GetPathStringValue(LibraryFile, path + ".identity_key", "")
                            ActiveIdentity = new String[10]
                            Int k = 0
                            While k < keys.Length
                                ActiveIdentity[k] = JsonUtil.GetPathStringValue(LibraryFile, path + "." + keys[k], "")
                                k += 1
                            EndWhile
                        EndIf
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
    If i < 0
        i = 0
    EndIf
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
    If ActiveIdentity
        String[] keys = IdentityKeys()
        JsonUtil.SetPathIntValue(ReceiptsFile, path + ".runtime_identity.version", 1)
        JsonUtil.SetPathStringValue(ReceiptsFile, path + ".runtime_identity.identity_key", ActiveIdentityKey)
        Int k = 0
        While k < keys.Length
            JsonUtil.SetPathStringValue(ReceiptsFile, path + ".runtime_identity." + keys[k], ActiveIdentity[k])
            k += 1
        EndWhile
    EndIf
    If !JsonUtil.Save(ReceiptsFile, False)
        Trace("receipt_failed", "id=" + performerId + " slot=" + slot)
    EndIf
EndFunction

; eventName avoids Papyrus's reserved Event keyword.
Function Trace(String eventName, String detail)
    JsonUtil.Load(TraceFile)
    Int count = JsonUtil.PathCount(TraceFile, ".entries")
    ; Save loads can restore an older script counter than the external file.
    If count > 0
        Int previous = JsonUtil.GetPathIntValue(TraceFile, ".entries[" + (count - 1) + "].seq", 0)
        If previous > TraceSequence
            TraceSequence = previous
        EndIf
    EndIf
    If count >= 300
        JsonUtil.ClearPath(TraceFile, ".entries")
        JsonUtil.SetRawPathValue(TraceFile, ".entries", "[]")
        AppendTraceEntry("trace_rolled", "dropped=300")
    EndIf
    AppendTraceEntry(eventName, detail)
EndFunction

Function AppendTraceEntry(String eventName, String detail)
    Int i = JsonUtil.PathCount(TraceFile, ".entries")
    If i < 0
        i = 0
    EndIf
    String path = ".entries[" + i + "]"
    TraceSequence += 1
    JsonUtil.SetPathIntValue(TraceFile, ".version", 1)
    JsonUtil.SetPathIntValue(TraceFile, path + ".seq", TraceSequence)
    JsonUtil.SetPathFloatValue(TraceFile, path + ".real_seconds", Utility.GetCurrentRealTime())
    JsonUtil.SetPathFloatValue(TraceFile, path + ".game_hours", Utility.GetCurrentGameTime() * 24.0)
    JsonUtil.SetPathStringValue(TraceFile, path + ".event", eventName)
    JsonUtil.SetPathStringValue(TraceFile, path + ".detail", detail)
    If !JsonUtil.Save(TraceFile, False) && !TraceSaveWarned
        TraceSaveWarned = True
        Debug.Trace("HoldMusic: trace save failed", 0)
    EndIf
EndFunction
