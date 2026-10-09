using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins.Assets;
using Mutagen.Bethesda.Skyrim.Assets;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;
using System.Text.Json;

if (args.Length != 2) throw new ArgumentException("PluginBuilder <package-directory> <data-directory>");
var output = Path.GetFullPath(args[0]);
Directory.CreateDirectory(output);
var key = ModKey.FromFileName("HoldMusic.esp");
var vanilla = ModKey.FromFileName("Skyrim.esm");
var mod = new SkyrimMod(key, SkyrimRelease.SkyrimSE) { IsSmallMaster = true };
mod.ModHeader.Author = "Codex (GPT-6)";
mod.ModHeader.Description = "Hold Music T1 offline package; not game-validated.";
mod.ModHeader.MasterReferences.Add(new MasterReference { Master = vanilla });
mod.ModHeader.MasterReferences.Add(new MasterReference { Master = ModKey.FromFileName("SkyUI_SE.esp") });
mod.ModHeader.MasterReferences.Add(new MasterReference { Master = ModKey.FromFileName("MCMHelper.esp") });
var forms = JsonDocument.Parse(File.ReadAllText(Path.Combine(args[1], "forms.json")));
FormKey Vanilla(string name) {
    var f = forms.RootElement.GetProperty("forms").EnumerateArray().Single(x => x.GetProperty("edid").GetString() == name && x.GetProperty("plugin").GetString()!.Equals("Skyrim.esm", StringComparison.OrdinalIgnoreCase));
    return new FormKey(vanilla, Convert.ToUInt32(f.GetProperty("id").GetString()![2..], 16));
}
ScriptObjectProperty Obj(string name, FormKey form) {
    var p = new ScriptObjectProperty { Name = name, Flags = ScriptProperty.Flag.Edited };
    p.Object.SetTo(form); return p;
}
var quest = new Quest(new FormKey(key, 0x800), SkyrimRelease.SkyrimSE) {
    EditorID = "HM_Quest", Name = "Hold Music",
    Flags = Quest.Flag.StartGameEnabled | Quest.Flag.RunOnce,
    Priority = 0, QuestFormVersion = 65, NextAliasID = 1,
    VirtualMachineAdapter = new QuestAdapter { Version = 5, ObjectFormat = 2, ExtraBindDataVersion = 2 }
};
var config = new ScriptEntry { Name = "HM_Config" };
config.Properties.Add(new ScriptStringProperty { Name = "ModName", Data = "HoldMusic", Flags = ScriptProperty.Flag.Edited });
quest.VirtualMachineAdapter.Scripts.Add(config);
quest.VirtualMachineAdapter.Scripts.Add(new ScriptEntry { Name = "HM_Library" });
var alias = new QuestAlias { ID = 0, Name = "PlayerAlias", Type = QuestAlias.TypeEnum.Reference, Flags = QuestAlias.Flag.AllowReserved };
alias.ForcedReference.SetTo(new FormKey(vanilla, 0x14));
quest.Aliases.Add(alias);
var binding = new QuestFragmentAlias { Version = 5, ObjectFormat = 2 };
binding.Property.Object.SetTo(quest.FormKey);
binding.Property.Alias = 0;
var controller = new ScriptEntry { Name = "HM_Controller" };
binding.Scripts.Add(controller);
binding.Scripts.Add(new ScriptEntry { Name = "SKI_PlayerLoadGameAlias" });
quest.VirtualMachineAdapter.Aliases.Add(binding);
mod.Quests.Add(quest);
controller.Properties.Add(Obj("Library", quest.FormKey));
controller.Properties.Add(Obj("Config", quest.FormKey));
foreach (var name in new[] { "LocTypeInn", "CurrentFollowerFaction", "IdleLuteStart", "IdleStop" })
    controller.Properties.Add(Obj(name, Vanilla(name)));
var defaults = new (uint Id, string Name, float Value)[] {
    (0x801,"HM_Enabled",1), (0x802,"HM_InstrumentalPercent",50),
    (0x803,"HM_SessionCap",3), (0x804,"HM_MinDelaySeconds",15), (0x805,"HM_MaxDelaySeconds",60)
};
foreach (var (id,name,value) in defaults) {
    var f = new FormKey(key,id);
    mod.Globals.Add(new GlobalFloat(f,SkyrimRelease.SkyrimSE) { EditorID=name, Data=value });
    controller.Properties.Add(Obj(name,f));
    if (id <= 0x803) config.Properties.Add(Obj(name,f));
}
var sounds = new ScriptObjectListProperty { Name = "SlotSounds", Flags = ScriptProperty.Flag.Edited };
var slots = JsonDocument.Parse(File.ReadAllText(Path.Combine(args[1], "slots.json")));
foreach (var slot in slots.RootElement.EnumerateArray()) {
    var descriptor = new SoundDescriptor(new FormKey(key,Convert.ToUInt32(slot.GetProperty("descriptor_id").GetString()![2..],16)),SkyrimRelease.SkyrimSE) {
        EditorID = slot.GetProperty("descriptor").GetString(),
        Type = SoundDescriptor.DescriptorType.Standard,
        LoopAndRumble = new SoundLoopAndRumble { Loop = SoundDescriptor.LoopType.None },
        Priority = 128, StaticAttenuation = 0
    };
    // Vanilla bard category fades in dialogue and pauses in menus; routed to SFX.
    descriptor.Category.SetTo(Vanilla("AudioCategoryPausedDuringMenuFade"));
    descriptor.OutputModel.SetTo(Vanilla("SOMMono02000_verb"));
    descriptor.SoundFiles.Add(new AssetLink<SkyrimSoundAssetType>(slot.GetProperty("file").GetString()!));
    mod.SoundDescriptors.Add(descriptor);
    var marker = new SoundMarker(new FormKey(key,Convert.ToUInt32(slot.GetProperty("marker_id").GetString()![2..],16)),SkyrimRelease.SkyrimSE) { EditorID = slot.GetProperty("marker").GetString() };
    marker.SoundDescriptor.SetTo(descriptor.FormKey);
    mod.SoundMarkers.Add(marker);
    var value = new ScriptObjectProperty(); value.Object.SetTo(marker.FormKey);
    sounds.Objects.Add(value);
}
controller.Properties.Add(sounds);
mod.ModHeader.Stats.NextFormID = 0x858;
var path = Path.Combine(output,"HoldMusic.esp");
mod.WriteToBinary(path);
using var loaded = SkyrimMod.CreateFromBinaryOverlay(path,SkyrimRelease.SkyrimSE);
if (!loaded.IsSmallMaster || loaded.Quests.Count!=1 || loaded.Globals.Count!=5 || loaded.SoundDescriptors.Count!=24 || loaded.SoundMarkers.Count!=24) throw new Exception("Record counts/ESL failed");
var q=loaded.Quests.Single();
if (q.Aliases.Single().ForcedReference.FormKey.ID != 0x14 || q.VirtualMachineAdapter!.Aliases.Single().Property.Object.FormKey != q.FormKey) throw new Exception("Alias binding failed");
var ctrl=q.VirtualMachineAdapter.Aliases.Single().Scripts.Single(x=>x.Name=="HM_Controller");
var bound=(IScriptObjectListPropertyGetter)ctrl.Properties.Single(x=>x.Name=="SlotSounds");
if (bound.Objects.Count!=24) throw new Exception("Sound array binding failed");
for(int i=0;i<24;i++) {
    var marker=loaded.SoundMarkers.Single(x=>x.FormKey.ID==0x840+i);
    var descriptor=loaded.SoundDescriptors.Single(x=>x.FormKey.ID==0x820+i);
    if(bound.Objects[i].Object.FormKey!=marker.FormKey || marker.SoundDescriptor.FormKey!=descriptor.FormKey || descriptor.LoopAndRumble!.Loop!=SoundDescriptor.LoopType.None || descriptor.SoundFiles.Count!=1) throw new Exception("Sound binding failed");
}
foreach(var (id,name,value) in defaults)
    if(loaded.Globals.Single(x=>x.FormKey.ID==id) is not IGlobalFloatGetter g || g.Data!=value || g.EditorID!=name) throw new Exception("Global validation failed");
Directory.CreateDirectory(Path.Combine(output,"SEQ"));
uint questFileId=((uint)loaded.ModHeader.MasterReferences.Count<<24)|0x800;
File.WriteAllBytes(Path.Combine(output,"SEQ","HoldMusic.seq"),BitConverter.GetBytes(questFileId));
Console.WriteLine(JsonSerializer.Serialize(new { path, bytes=new FileInfo(path).Length, esl=loaded.IsSmallMaster, quests=1, globals=5, descriptors=24, markers=24, questFileId=$"{questFileId:X8}", masters=loaded.ModHeader.MasterReferences.Select(x=>x.Master.ToString()), validation="Mutagen serialize/read round-trip passed" },new JsonSerializerOptions { WriteIndented=true }));
