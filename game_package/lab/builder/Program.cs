using System.Buffers.Binary;
using System.Globalization;
using System.Text.Json;
using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Skyrim;

if (args.Length is < 1 or > 2)
    throw new ArgumentException("HM_LabPluginBuilder <package-directory> [<data-directory>]");

var output = Path.GetFullPath(args[0]);
var data = args.Length == 2 ? Path.GetFullPath(args[1]) : FindDataDirectory();
var formsPath = Path.Combine(data, "forms.json");
using var forms = JsonDocument.Parse(File.ReadAllText(formsPath));

var key = ModKey.FromFileName("HM_Lab.esp");
var vanilla = ModKey.FromFileName("Skyrim.esm");
var holdMusic = ModKey.FromFileName("HoldMusic.esp");
var questKey = new FormKey(key, 0x800);
var holdMusicQuest = new FormKey(holdMusic, 0x800);
// Verified in the SE lab's Skyrim.esm: Travel NearSelf, radius zero, no own idle.
var fixturePackage = new FormKey(vanilla, 0x10FB3F);
var requiredMasters = new[] { vanilla, holdMusic };
var expectedProperties = new Dictionary<string, FormKey>
{
    ["Library"] = holdMusicQuest,
    ["Config"] = holdMusicQuest,
    ["HoldMusicQuest"] = holdMusicQuest,
    ["HM_Enabled"] = new(holdMusic, 0x801),
    ["HM_InstrumentalPercent"] = new(holdMusic, 0x802),
    ["HM_SessionCap"] = new(holdMusic, 0x803),
    ["HM_MinDelaySeconds"] = new(holdMusic, 0x804),
    ["HM_MaxDelaySeconds"] = new(holdMusic, 0x805),
    ["LocTypeInn"] = Vanilla("LocTypeInn", "KYWD"),
};

// All production records are referenced, never overridden by this test plugin.
// Keep this a normal ESP so the quest has an ordinary console FormID.
var mod = new SkyrimMod(key, SkyrimRelease.SkyrimSE) { IsSmallMaster = false };
mod.ModHeader.Author = "Hold Music LAB";
mod.ModHeader.Description = "Opt-in Hold Music lab harness. Disposable test saves only.";
foreach (var master in requiredMasters)
    mod.ModHeader.MasterReferences.Add(new MasterReference { Master = master });

var quest = new Quest(questKey, SkyrimRelease.SkyrimSE)
{
    EditorID = "HM_LabQuest",
    Name = "Hold Music LAB",
    Flags = Quest.Flag.StartGameEnabled | Quest.Flag.RunOnce,
    Priority = 90,
    QuestFormVersion = 65,
    NextAliasID = 1,
    VirtualMachineAdapter = new QuestAdapter
    {
        Version = 5,
        ObjectFormat = 2,
        ExtraBindDataVersion = 2,
    },
};
// Empty until the opted-in harness explicitly acquires an actor. Clearing the
// alias removes this package without changing the actor's base package list.
var fixtureAlias = new QuestAlias
{
    ID = 0,
    Name = "FixtureActor",
    Type = QuestAlias.TypeEnum.Reference,
    Flags = QuestAlias.Flag.Optional,
};
fixtureAlias.PackageData.Add(new FormLink<IPackageGetter>(fixturePackage));
quest.Aliases.Add(fixtureAlias);
var harness = new ScriptEntry { Name = "HM_LabHarness" };
foreach (var (name, form) in expectedProperties)
{
    var property = new ScriptObjectProperty
    {
        Name = name,
        Flags = ScriptProperty.Flag.Edited,
    };
    property.Object.SetTo(form);
    harness.Properties.Add(property);
}
quest.VirtualMachineAdapter.Scripts.Add(harness);
mod.Quests.Add(quest);
mod.ModHeader.Stats.NextFormID = 0x801;

Directory.CreateDirectory(output);
var pluginPath = Path.Combine(output, key.FileName.String);
mod.WriteToBinary(pluginPath);

// Validate the serialized plugin, including cross-plugin VMAD references.
using var loaded = SkyrimMod.CreateFromBinaryOverlay(pluginPath, SkyrimRelease.SkyrimSE);
Require(!loaded.IsSmallMaster, "HM_Lab.esp must not be ESL flagged");
Require(!loaded.ModHeader.Flags.HasFlag(SkyrimModHeader.HeaderFlag.Master),
    "HM_Lab.esp must not be ESM flagged");
Require(loaded.ModHeader.MasterReferences.Select(x => x.Master).SequenceEqual(requiredMasters),
    "Masters must be Skyrim.esm, HoldMusic.esp, in that order");
Require(loaded.EnumerateMajorRecords().Count() == 1 && loaded.Quests.Count == 1,
    "HM_Lab.esp must contain exactly one quest and no other records");
Require(loaded.ModHeader.Stats.NextFormID == 0x801, "Unexpected NextFormID");
var actualQuest = loaded.Quests.Single();
Require(actualQuest.FormKey == questKey && actualQuest.EditorID == "HM_LabQuest",
    "Lab quest identity changed during serialization");
Require(actualQuest.Flags == (Quest.Flag.StartGameEnabled | Quest.Flag.RunOnce),
    "Lab quest start/run flags did not round-trip");
Require(actualQuest.Priority == 90 && actualQuest.Aliases.Count == 1
    && actualQuest.NextAliasID == 1, "Unexpected fixture alias count or quest priority");
var actualAlias = actualQuest.Aliases.Single();
Require(actualAlias.ID == 0 && actualAlias.Name == "FixtureActor"
    && actualAlias.Type == QuestAlias.TypeEnum.Reference
    && actualAlias.Flags == QuestAlias.Flag.Optional
    && actualAlias.ForcedReference.FormKey == FormKey.Null,
    "Fixture alias must be optional and initially empty");
Require(actualAlias.PackageData.Count == 1
    && actualAlias.PackageData.Single().FormKey == fixturePackage,
    "Fixture alias must reference only DefaultBardStayAtCurrentLocation");
var adapter = actualQuest.VirtualMachineAdapter
    ?? throw new InvalidDataException("Lab quest VMAD is missing");
Require(adapter.Version == 5 && adapter.ObjectFormat == 2
    && adapter.ExtraBindDataVersion == 2 && adapter.Aliases.Count == 0,
    "Unexpected lab quest VMAD layout");
Require(adapter.Scripts.Count == 1 && adapter.Scripts.Single().Name == "HM_LabHarness",
    "Lab quest must attach only HM_LabHarness");
var actualProperties = adapter.Scripts.Single().Properties;
Require(actualProperties.Count == expectedProperties.Count, "Unexpected harness property count");
Require(actualProperties.Select(x => x.Name).Distinct().Count() == expectedProperties.Count,
    "Duplicate harness property names");
foreach (var (name, form) in expectedProperties)
{
    var property = actualProperties.SingleOrDefault(x => x.Name == name)
        as IScriptObjectPropertyGetter;
    Require(property is not null && property.Object.FormKey == form
        && property.Alias == -1 && property.Flags == ScriptProperty.Flag.Edited,
        $"Harness property {name} failed its form/alias/flag round-trip");
}

var seqPath = Path.Combine(output, "SEQ", "HM_Lab.seq");
Directory.CreateDirectory(Path.GetDirectoryName(seqPath)!);
uint questFileId = ((uint)loaded.ModHeader.MasterReferences.Count << 24) | questKey.ID;
var seq = new byte[sizeof(uint)];
BinaryPrimitives.WriteUInt32LittleEndian(seq, questFileId);
File.WriteAllBytes(seqPath, seq);
Require(File.ReadAllBytes(seqPath).AsSpan().SequenceEqual(seq), "Lab SEQ write verification failed");

Console.WriteLine(JsonSerializer.Serialize(new
{
    path = pluginPath,
    bytes = new FileInfo(pluginPath).Length,
    esl = loaded.IsSmallMaster,
    quests = loaded.Quests.Count,
    editorId = actualQuest.EditorID,
    questFileId = $"{questFileId:X8}",
    nextFormId = $"{loaded.ModHeader.Stats.NextFormID:X8}",
    priority = actualQuest.Priority,
    fixtureAlias = new
    {
        id = actualAlias.ID,
        name = actualAlias.Name,
        flags = actualAlias.Flags.ToString(),
        package = fixturePackage.ToString(),
    },
    masters = loaded.ModHeader.MasterReferences.Select(x => x.Master.ToString()),
    script = harness.Name,
    properties = expectedProperties.ToDictionary(x => x.Key, x => x.Value.ToString()),
    seqPath,
    formsPath,
    validation = "Mutagen serialize/read round-trip passed; all lab bindings and SEQ verified",
}, new JsonSerializerOptions { WriteIndented = true }));

FormKey Vanilla(string editorId, string type)
{
    var matches = forms.RootElement.GetProperty("forms").EnumerateArray().Where(x =>
        x.GetProperty("edid").GetString() == editorId
        && string.Equals(x.GetProperty("plugin").GetString(), "Skyrim.esm",
            StringComparison.OrdinalIgnoreCase)
        && x.GetProperty("type").GetString() == type).ToArray();
    Require(matches.Length == 1, $"Expected exactly one Skyrim.esm {type} {editorId} in forms.json");
    var text = matches[0].GetProperty("id").GetString()
        ?? throw new InvalidDataException($"Missing form ID for {editorId}");
    Require(text.StartsWith("0x", StringComparison.OrdinalIgnoreCase),
        $"Form ID for {editorId} must be hexadecimal with a 0x prefix");
    var id = uint.Parse(text[2..], NumberStyles.HexNumber, CultureInfo.InvariantCulture);
    Require(id is > 0 and <= 0xFFFFFF, $"Form ID for {editorId} must be a local ID");
    return new FormKey(vanilla, id);
}

static void Require(bool condition, string message)
{
    if (!condition) throw new InvalidDataException(message);
}

static string FindDataDirectory()
{
    foreach (var start in new[] { Directory.GetCurrentDirectory(), AppContext.BaseDirectory })
        for (var dir = new DirectoryInfo(start); dir is not null; dir = dir.Parent)
            foreach (var relative in new[] { "data", Path.Combine("game_package", "data") })
            {
                var candidate = Path.Combine(dir.FullName, relative);
                if (File.Exists(Path.Combine(candidate, "forms.json"))) return candidate;
            }
    throw new DirectoryNotFoundException(
        "Cannot find game_package/data/forms.json; pass <data-directory> explicitly.");
}
