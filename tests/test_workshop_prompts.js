/* Offline prompt contracts: no browser, provider requests or credentials. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const data = JSON.parse(fs.readFileSync(path.join(root, 'dashboard/palette-data.json'), 'utf8'));
const template = fs.readFileSync(path.join(root, 'dashboard/index.template.html'), 'utf8');
let script = template.split('<script>')[1].split('</script>')[0].replace('__PALETTE_DATA__', JSON.stringify(data));
// Load the actual prompt functions without registering UI handlers or starting fetches.
script = script.split("document.querySelectorAll('[data-tab]').forEach(button=>{button.addEventListener")[0];
script += 'globalThis.testApi = {buildPrompt,generationInput,arrangementSupport,ARRANGEMENTS,state,lyricsCatalog,profiles,validate};})();';
const sandbox = {location:{protocol:'http:'},localStorage:{getItem:()=>null},sessionStorage:{getItem:()=>null}};
vm.runInNewContext(script, sandbox);
const {buildPrompt,generationInput,arrangementSupport,ARRANGEMENTS,state,lyricsCatalog,profiles,validate} = sandbox.testApi;
let checked = 0, max = 0, longest;
for (const profile of profiles) {
 for (const [arrangement,a] of Object.entries(ARRANGEMENTS)) {
  for (const race of Object.keys(data.auditionRaces)) {
   state.workspace.leftRace = race;
   const support = arrangementSupport(profile,arrangement,'prompt-a');
   if (!support.valid) {
    assert(support.reason, 'Omissions need a visible reason');
    assert.equal(generationInput(arrangement,'A custom direction',profile.id,'prompt-a').valid,false,'Edits cannot bypass omitted arrangements');
    continue;
   }
   const built = buildPrompt(profile,arrangement,'prompt-a');
   assert(built.valid, `${profile.id}/${arrangement}: ${built.note}`);
   for (const region of Object.keys(data.auditionRegions)) {
    state.workspace.targetRegion = region;
    state.workspace.lyricsId = '';
    const input = generationInput(arrangement,built.prompt,profile.id,'prompt-a');
    assert(input.valid, input.reason);
    const length = Array.from(input.musicPrompt).length;
    assert(length<=1000,`${profile.id}/${arrangement} is ${length} music characters`);
    assert(input.musicPrompt.includes(arrangement==='drum'&&profile.drum_reference?profile.drum_reference:profile.reference),'Keep the explicit real-world reference');
    assert(input.musicPrompt.includes(data.auditionRaces[race]),'Keep the actual performer race');
    const place = region==='skyrim'?'Skyrim, unnamed venue':region==='cyrodiil'?'Cyrodiil, unnamed venue':data.auditionRegions[region];
    assert(input.musicPrompt.includes(place),'Keep the actual target region');
    if (!a.sings) assert(!/Vocal tone:|Voice:|Write lyrics/.test(input.preview),'Instrumentals must not ask for a singer');
    if (length>max) {max=length;longest=`${profile.id}/${arrangement}/${race}/${region}`;}
    checked++;
   }
  }
 }
}
state.workspace.leftRace = 'profile';
state.workspace.targetRegion = 'profile';
state.workspace.lyricsId = 'fixture';
lyricsCatalog.loaded=true;
lyricsCatalog.songs=[{id:'fixture',lyrics:'[Verse]\nOriginal words',sha256:'fixture-hash'}];
for (const id of ['khajiit','argonian']) {
 const profile = profiles.find(p=>p.id===id);
 assert.deepEqual(Array.from(profile.workshop.allowed),id==='khajiit'?['lute','flute','drum']:['lute','flute']);
 const built = buildPrompt(profile,'lute','prompt-a');
 const input = generationInput('lute',built.prompt,id,'prompt-a');
 assert(!input.preview.includes('Original words'),'Selected lyrics must stay out of instrumentals');
 assert.equal(input.song,null);
 assert(input.musicPrompt.includes(profile.workshop.plucked));
 assert(!input.musicPrompt.includes('Lute:'),'Use the recipe’s actual plucked instrument');
}
const khajiit=profiles.find(p=>p.id==='khajiit');
const tabla=generationInput('drum',buildPrompt(khajiit,'drum','prompt-a').prompt,khajiit.id,'prompt-a');
assert(tabla.valid&&tabla.musicPrompt.includes('Hindustani tabla solo'));
assert(tabla.musicPrompt.includes('16-beat teental (4+4+4+4)'));
assert(tabla.musicPrompt.includes('bayan')&&tabla.musicPrompt.includes('dayan')&&tabla.musicPrompt.includes('tihai'));
assert(!/raga|sitar|drone|Voice:|Vocal tone:|Original words|Write lyrics/i.test(tabla.preview),'Tabla is a complete percussion solo, with no melodic or vocal parts');
assert.equal(tabla.song,null,'Do not attach the selected lyrics to tabla');
state.workspace.lyricsId='';
assert.equal(generationInput('lute','A tune.\nLyrics:\nSing these words','khajiit','prompt-a').valid,false,'Inline words cannot bypass instrumental-only casting');
const nord=profiles.find(p=>p.id==='nord');
const sung=buildPrompt(nord,'lute_voice','prompt-a');
const instrumental=buildPrompt(nord,'lute','prompt-a');
assert(sung.prompt.includes('Voice:'));
assert(!instrumental.prompt.includes('Voice:'));
assert(instrumental.prompt.includes('refrain'),'A solo instrumental carries the melody');
const orc=profiles.find(p=>p.id==='orc_resonant_names');
assert(orc.name.includes('throat singing'));
assert(buildPrompt(orc,'voice','prompt-a').prompt.includes('moving whistle-like upper-overtone melody'));
assert(data.ideas.some(p=>p.name==='Resonant Name-Songs'&&p.finalistId===orc.id),'Keep old idea-bank links');
assert.deepEqual(Array.from(profiles.filter(p=>p.workshop.allowed.includes('drum')).map(p=>p.id)).sort(),['bosmer_leaping_tales','khajiit','orc_seven_step','redguard','rift']);
const backup=validate({format:'hold-music-auditions',version:1,records:{khajiit:{status:'revise',notes:'Keep the first vocal take for comparison.',prompts:{lute_voice:'My historical vocal direction',lute:'My historical lute direction'}}}});
assert.equal(backup.records.khajiit.prompts.lute_voice,'My historical vocal direction','Preserve saved edits even when their arrangement is no longer offered');
assert.equal(backup.records.khajiit.prompts.lute,'My historical lute direction','Keep historical plucked-family keys readable');
const custom=generationInput('lute','x'.repeat(1500),nord.id,'prompt-a');
assert(custom.valid&&custom.musicPrompt.includes('x'.repeat(1500)),'Never silently truncate custom edits');
console.log(`Prompt contracts passed: ${checked} valid combinations; maximum ${max}/1000 characters (${longest}).`);
