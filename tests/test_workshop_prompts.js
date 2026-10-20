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
script += 'globalThis.testApi = {buildPrompt,generationInput,arrangementSupport,ARRANGEMENTS,state,lyricsCatalog,profiles,validate,draftsFor,takePromptStatus,comparisonState,matchesComparisonFilter,comparisonTakeIds,sharedTextPairs,sampleCode,reviewIsUncertain,workshop};})();';
const sandbox = {location:{protocol:'http:'},localStorage:{getItem:()=>null},sessionStorage:{getItem:()=>null}};
vm.runInNewContext(script, sandbox);
const {buildPrompt,generationInput,arrangementSupport,ARRANGEMENTS,state,lyricsCatalog,profiles,validate,draftsFor} = sandbox.testApi;
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
    if (arrangement.startsWith('lute')) {
     assert(input.musicPrompt.includes('No bowed strings.'),'Plucked-family prompts explicitly exclude bowed strings');
     assert(input.musicPrompt.includes(profile.workshop.plucked),'Name the specific mapped instrument');
     assert(!input.musicPrompt.includes('plucked plucked'),'Do not duplicate the plucked-family label');
    }
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
const admitted = profiles.filter(p=>p.audition.stage!=='deferred');
assert.equal(admitted.length,12);
assert.equal(admitted.filter(p=>p.audition.stage==='baseline').length,11);
assert.deepEqual(Array.from(admitted.filter(p=>p.audition.stage==='comparison').map(p=>p.id)),['reach_sean_nos']);
for(const profile of profiles){
 const keys=Object.keys(ARRANGEMENTS).filter(key=>arrangementSupport(profile,key,'prompt-a').valid);
 assert.deepEqual(Array.from(keys),profile.audition.stage==='deferred'?[]:[profile.audition.arrangement]);
}
for(const id of ['winterhold','hjaalmarch']){
 const p=profiles.find(p=>p.id===id),key=p.audition.arrangement;
 const input=generationInput(key,buildPrompt(p,key,'prompt-a').prompt,id,'prompt-a');
 assert(input.valid,input.reason);
 assert.equal(input.song,null);
 assert(!input.preview.includes('Original words'));
 assert(!/Write English lyrics|Lyrics:/.test(input.preview));
 assert.equal(generationInput(key,'A tune.\nLyrics:\nWords',id,'prompt-a').valid,false);
 if(id==='winterhold')assert(input.preview.endsWith('Wordless vocables only; no lyrics, sentences or spoken words.'));
 else assert(!input.preview.includes('Voice:'));
}
const reach=profiles.find(p=>p.id==='reach'),air=profiles.find(p=>p.id==='reach_sean_nos');
assert(reach.reference.includes('puirt-à-beul'));
assert(air.reference.includes('sean-nós'));
assert(buildPrompt(reach,'lute_voice','prompt-a').prompt.includes('duple reel'));
assert(!buildPrompt(reach,'lute_voice','prompt-a').prompt.includes('free-rhythm'));
const lyrical=generationInput('lute_voice',buildPrompt(reach,'lute_voice','prompt-a').prompt,reach.id,'prompt-a');
assert.equal(lyrical.song.lyrics,'[Verse]\nOriginal words');
assert(lyrical.preview.endsWith('[Verse]\nOriginal words'));
state.workspace.lyricsId='';
const backup=validate({format:'hold-music-auditions',version:1,records:{reach:{status:'revise',notes:'Keep the earlier air.',prompts:{lute_voice:'My historical air'}}},workspace:{left:'orc_resonant_names',right:'bosmer_leaping_tales',arrangement:'lute_voice',tab:'finalists'}});
state.records=backup.records;
assert.equal(state.records.reach.prompts.lute_voice,'My historical air');
assert.equal(draftsFor(reach),undefined,'An earlier edit cannot override the baseline');
draftsFor(reach,true).lute_voice='A revised reel';
assert.equal(draftsFor(reach).lute_voice,'A revised reel');
assert.equal(state.records.reach.prompts.lute_voice,'My historical air','New editing preserves the original');
const roundtrip=validate({format:'hold-music-auditions',version:1,records:state.records});
assert.equal(roundtrip.records.reach.promptSets[data.baseline.revision].lute_voice,'A revised reel');
assert.equal(roundtrip.records.reach.prompts.lute_voice,'My historical air');
assert.equal(backup.workspace.tab,'baseline','Older collection names migrate');
const custom=generationInput('lute_voice','x'.repeat(1500),reach.id,'prompt-a');
assert(custom.valid&&custom.musicPrompt.includes('x'.repeat(1500)),'Never silently truncate custom edits');
const {takePromptStatus,comparisonState,matchesComparisonFilter,workshop}=sandbox.testApi;
delete draftsFor(reach).lute_voice;
const originalDirection=buildPrompt(reach,'lute_voice','prompt-a').prompt;
const currentTake={id:'fixture-a',profile_id:'reach',arrangement:'lute_voice',direction_draft:originalDirection,prompt:originalDirection,prompt_status:{state:'current',label:'Current prompt'}};
assert.equal(takePromptStatus(currentTake).state,'current');
draftsFor(reach,true).lute_voice='Changed musical direction';
assert.equal(takePromptStatus(currentTake).state,'obsolete','Prompt edits must visibly invalidate earlier takes');
workshop.takes=[currentTake];
const comparison={state:'reviewed',take_ids:['fixture-a']};
assert.equal(comparisonState(comparison),'obsolete','A prior review does not approve a newer direction');
assert(matchesComparisonFilter(comparison,'waiting'));
assert(!matchesComparisonFilter(comparison,'reviewed'));
delete draftsFor(reach).lute_voice;
assert.equal(takePromptStatus(currentTake).state,'current','Resetting the draft restores a matching take');
assert.equal(comparisonState(comparison),'reviewed');
assert.equal(takePromptStatus({...currentTake,direction_draft:undefined,prompt_status:undefined}).state,'unknown','Do not invent version evidence for old takes');
assert(matchesComparisonFilter({state:'revisit',take_ids:[]},'pending'),'Unsure decisions remain in the listening queue');
const {comparisonTakeIds,sharedTextPairs,sampleCode,reviewIsUncertain}=sandbox.testApi;
const expanded={kind:'neighbor',state:'reviewed',take_ids:['a1','b1'],evidence_take_ids:['a1','a2','b1','b2'],groups:[
 {samples:[{take_id:'a1',replicate:1,lyric_id:'workroom'},{take_id:'a2',replicate:2,lyric_id:'cart'}]},
 {samples:[{take_id:'b1',replicate:1,lyric_id:'workroom'},{take_id:'b2',replicate:2,lyric_id:'cart'}]}
]};
assert.deepEqual(comparisonTakeIds(expanded),['a1','a2','b1','b2']);
assert.deepEqual(Array.from(sharedTextPairs(expanded)),['A1 with B1','A2 with B2']);
assert.equal(sampleCode(expanded,'b2'),'B2');
assert.deepEqual(Array.from(sharedTextPairs({...expanded,groups:[expanded.groups[0],{samples:[{replicate:1,vocal_mode:'wordless'},{replicate:2,vocal_mode:'wordless'}]}]})),[],'Wordless takes do not get a shared-lyrics claim');
workshop.takes=expanded.evidence_take_ids.map(id=>({...currentTake,id,prompt_status:{state:id==='a2'?'obsolete':'current'}}));
assert.equal(comparisonState(expanded),'obsolete','Second takes outside the original judge pair must invalidate a stale review');
assert(reviewIsUncertain({outcome:'distinct',consistency:{a:'uncertain',b:'consistent'}}),'Uncertain repetition stays in the queue despite distinct styles');
assert(!reviewIsUncertain({outcome:'distinct',consistency:{a:'consistent',b:'inconsistent'}}),'A definite inconsistency is still a completed listening decision');
console.log(`Prompt contracts passed: ${checked} valid combinations; maximum ${max}/1000 characters (${longest}).`);
