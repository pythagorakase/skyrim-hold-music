"""Offline build on halcyon. All writes stay below C:\\MGO\\hm-scratch\\t1b."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from build_registry import build_registry

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(r'C:\MGO\hm-scratch\t1b')
INSTALL = Path(r'C:\MGO\Skyrim MGO 4.0 RC4.1')
PROFILE = INSTALL / 'profiles/MGO EXP - SkyrimNet b26 + SeverActions 4.2'
AUDIT = Path(r'C:\MGO\codex-investigations\20261006-ostimnet-spouse-guard')
COMPILER = Path(r'C:\MGO\character-work\tools\caprica-0.3.0\Caprica.exe')
FLAGS = Path(r'C:\MGO\character-work\flatrim-test\script-source\TESV_Papyrus_Flags.flg')
DECOMPILER = Path(r'C:\MGO\codex-investigations\20261002-companions-hostility\decompiler\Champollion.exe')
BUILD = ROOT / 'build'
PACKAGE = BUILD / 'package'


def main():
    if os.name != 'nt' or not ROOT.is_relative_to(SCRATCH):
        raise SystemExit('Build only from C:\\MGO\\hm-scratch\\t1b\\game_package on halcyon')
    # Check the checked-in derivation before any build writes.
    build_registry(check=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    for name, sub in {'TEMP':'tmp','TMP':'tmp','DOTNET_CLI_HOME':'dotnet-home','NUGET_PACKAGES':'nuget','NUGET_HTTP_CACHE_PATH':'nuget-http','NUGET_PLUGINS_CACHE_PATH':'nuget-plugins','MSBUILDUSEREXTENSIONSPATH':'msbuild','APPDATA':'appdata','LOCALAPPDATA':'localappdata'}.items():
        folder = SCRATCH / sub
        folder.mkdir(exist_ok=True)
        env[name] = str(folder)
    env.update(DOTNET_CLI_TELEMETRY_OPTOUT='1', DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1', DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE='1', DOTNET_NOLOGO='1', PYTHONDONTWRITEBYTECODE='1')
    transcript = []

    def run(args, name):
        result = subprocess.run(list(map(str,args)), cwd=BUILD, env=env, capture_output=True, text=True, errors='replace')
        content = result.stdout + result.stderr
        (BUILD / name).write_text(content, encoding='utf-8')
        return result, content

    def say(message):
        print(message, flush=True)
        transcript.append(message)
        (BUILD/'build.log').write_text('\n'.join(transcript)+'\n', encoding='utf-8')

    # Reuse cached exact dependencies; no tool installation or external restore.
    assets = json.loads(Path(r'C:\MGO\ModernMarriage\tools\PluginBuilder\obj\project.assets.json').read_text(encoding='utf-8-sig'))
    cache = Path(next(iter(assets['packageFolders'])))
    for name, detail in assets['libraries'].items():
        if detail['type'] != 'package':
            continue
        source = cache / detail['path']
        dest = Path(env['NUGET_PACKAGES']) / detail['path']
        if not dest.exists():
            shutil.copytree(source, dest)
    nuget_config = ROOT/'tools/PluginBuilder/NuGet.Config'
    nuget_config.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n')
    imports = BUILD/'imports'
    imports.mkdir(exist_ok=True)
    for source in (AUDIT/'compile-imports').glob('*.psc'):
        shutil.copy2(source,imports/source.name)
    sources = {}
    binaries = {p.stem.lower():p for p in (AUDIT/'vanilla-pex').rglob('*.pex')}
    for line in reversed((PROFILE/'modlist.txt').read_text(encoding='utf-8-sig').splitlines()):
        if not line.startswith('+') or line.endswith('_separator'):
            continue
        folder = INSTALL/'mods'/line[1:]
        for p in folder.rglob('*.psc'):
            sources[p.stem.lower()] = p
        for p in (folder/'Scripts').glob('*.pex'):
            binaries[p.stem.lower()] = p
    # Seed the required native APIs from winning installed sources or PEX.
    dependencies = {}
    def resolve(key):
        if key in sources:
            src=sources[key]
            shutil.copy2(src,imports/src.name)
        elif key in binaries:
            src=binaries[key]
            result,content=run([DECOMPILER,src,'-p',imports,'--no-debug-line'],f'dependency-{key}.log')
            if result.returncode: raise RuntimeError(content)
        else: raise RuntimeError('No installed source/PEX for '+key)
        dependencies[key]={'source':str(src),'sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
    for key in ('jsonutil','storageutil','miscutil','mcm_configbase','actor','game','form','sound','utility'):
        resolve(key)
    output=PACKAGE/'Scripts'
    output.mkdir(parents=True,exist_ok=True)
    for source in sorted((ROOT/'src/Scripts/Source').glob('*.psc')):
        resolved=set()
        args=[COMPILER,source,'--game=skyrim','--ignorecwd','--allow-unknown-events=true','--skyrim-allow-unknown-events-on-non-native-class=true','-i',str(source.parent)+';'+str(imports),'-f',FLAGS,'-o',output,'--dump-asm']
        for attempt in range(70):
            result,content=run(args,f'compile-{source.stem}.log')
            if result.returncode==0:
                asm=output/(source.stem+'.pas')
                (BUILD/'caprica-asm').mkdir(exist_ok=True)
                if asm.exists(): shutil.move(str(asm),str(BUILD/'caprica-asm'/asm.name))
                say('Compiled: '+source.stem)
                break
            missing=re.search(r"Unable to resolve type '([^']+)'",content)
            if not missing or missing[1].lower() in resolved:
                say(content); raise RuntimeError('Compilation failed: '+source.stem)
            key=missing[1].lower(); resolved.add(key); resolve(key)
        else: raise RuntimeError('Dependency resolution exhausted')
    shutil.copytree(ROOT/'src',PACKAGE,dirs_exist_ok=True)
    result,content=run(['dotnet','run','--project',ROOT/'tools/PluginBuilder/PluginBuilder.csproj','--configuration','Release','--',PACKAGE,ROOT/'data'],'plugin-validation.json')
    say(content.strip())
    if result.returncode: raise RuntimeError('Plugin build failed')
    asm=BUILD/'disassembly'; asm.mkdir(exist_ok=True)
    for p in output.glob('*.pex'):
        result,content=run([DECOMPILER,p,'-a',asm,'--no-debug-line'],f'disassemble-{p.stem}.log')
        if result.returncode: raise RuntimeError(content)
        say('Disassembled: '+p.name)
    (BUILD/'dependencies.json').write_text(json.dumps(dependencies,indent=2)+'\n')
    hashes={p.relative_to(PACKAGE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(PACKAGE.rglob('*')) if p.is_file()}
    (BUILD/'package-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    say(f'Build ready: {PACKAGE}; {len(hashes)} hashed files. Nothing installed or launched.')

if __name__ == '__main__':
    main()
