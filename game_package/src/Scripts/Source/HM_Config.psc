Scriptname HM_Config extends MCM_ConfigBase

GlobalVariable Property HM_Enabled Auto
GlobalVariable Property HM_InstrumentalPercent Auto
GlobalVariable Property HM_SessionCap Auto
Bool Property StopRequested = False Auto
String Property WorldId = "" Auto

Event OnConfigInit()
    ModName = "HoldMusic"
    ApplySettings()
EndEvent

Event OnGameReload()
    Parent.OnGameReload()
    ApplySettings()
EndEvent

Event OnSettingChange(String setting)
    ApplySettings()
EndEvent

Function ApplySettings()
    HM_Enabled.SetValue(GetModSettingBool("bEnabled:General") as Float)
    Int chance = GetModSettingInt("iInstrumentalPercent:General")
    Int cap = GetModSettingInt("iSessionCap:General")
    If chance >= 0 && chance <= 100
        HM_InstrumentalPercent.SetValue(chance)
    EndIf
    If cap >= 0 && cap <= 24
        HM_SessionCap.SetValue(cap)
    EndIf
    WorldId = GetModSettingString("sWorldId:General")
EndFunction

Function StopPerformance()
    StopRequested = True
EndFunction
