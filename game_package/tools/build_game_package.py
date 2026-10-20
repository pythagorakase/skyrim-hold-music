"""Offline package build with explicit stack/toolchain inputs and an isolated workspace."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True

from build_registry import build_registry
from build_config import parse_args, sha256

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))
from hold_music.runtime_capability import (
    REPORT_FILENAME, capture_inputs, receipt_capability, validate_capability,
)


def main(argv=None):
    config, build = parse_args(argv)
    # Check the checked-in derivation before any build writes.
    build_registry(check=True)
    plan = config.plan(ROOT)
    if not build:
        print(json.dumps(plan, indent=2))
        return 0
    if os.name != 'nt':
        raise ValueError('Compilation requires the installed Windows toolchain; planning is portable')
    SCRATCH = config.workspace
    INSTALL = config.mo2_root
    PROFILE = config.profile_dir
    COMPILER = config.compiler
    FLAGS = config.flags
    DECOMPILER = config.decompiler
    BUILD = config.build_dir
    PACKAGE = BUILD / 'package'
    SCRATCH.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / 'build-plan.json').write_text(json.dumps(plan, indent=2)+'\n', encoding='utf-8')
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
    for source, relative in config.dependency_packages():
        shutil.copytree(source, Path(env['NUGET_PACKAGES']) / relative)
    # Copy only authored builder inputs so dotnet bin/obj never touches the checkout.
    plugin_builder = SCRATCH / 'plugin-builder'
    plugin_builder.mkdir()
    for name in ('Program.cs', 'PluginBuilder.csproj'):
        shutil.copy2(ROOT / 'tools/PluginBuilder' / name, plugin_builder / name)
    nuget_config = plugin_builder / 'NuGet.Config'
    nuget_config.write_text('<configuration><packageSources><clear /></packageSources></configuration>\n',
                            encoding='utf-8')
    imports = BUILD/'imports'
    imports.mkdir(exist_ok=True)
    for source in config.vanilla_imports.glob('*.psc'):
        shutil.copy2(source,imports/source.name)
    sources = {}
    binaries = {p.stem.lower():p for p in config.vanilla_pex.rglob('*.pex')}
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
    seeded_imports = {
        source.name: {'source': str(source), 'sha256': sha256(source)}
        for source in config.vanilla_imports.glob('*.psc')
    }
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
        args=[COMPILER,source,'--game=skyrim','--ignorecwd','--allow-unknown-events=true','--skyrim-allow-unknown-events-on-non-native-class=true','-i',str(source.parent)+';'+str(ROOT/'imports')+';'+str(imports),'-f',FLAGS,'-o',output,'--dump-asm']
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
    project = plugin_builder / 'PluginBuilder.csproj'
    result,content=run([config.dotnet,'restore',project,'--configfile',nuget_config,
                       '-p:NuGetAudit=false'],'plugin-restore.log')
    if result.returncode: raise RuntimeError('Offline dependency restore failed: '+content)
    result,content=run([config.dotnet,'run','--project',project,'--no-restore',
                       '--configuration','Release','--',PACKAGE,ROOT/'data'],'plugin-validation.json')
    say(content.strip())
    if result.returncode: raise RuntimeError('Plugin build failed')
    asm=BUILD/'disassembly'; asm.mkdir(exist_ok=True)
    for p in output.glob('*.pex'):
        result,content=run([DECOMPILER,p,'-a',asm,'--no-debug-line'],f'disassemble-{p.stem}.log')
        if result.returncode: raise RuntimeError(content)
        say('Disassembled: '+p.name)
    (BUILD/'dependencies.json').write_text(json.dumps(dependencies,indent=2)+'\n')
    if any(p.stem.lower() == 'bardsongsscript' for p in PACKAGE.rglob('*') if p.is_file()):
        raise RuntimeError('Compile-time BardSongsScript stub must never be packaged')
    hashes={p.relative_to(PACKAGE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(PACKAGE.rglob('*')) if p.is_file()}
    (BUILD/'package-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
    # Execute fixtures in a fresh interpreter against this exact isolated build.
    # The verifier measures sources, PEX, disassembly and test helpers before
    # and after the run; a failed or skipped required test aborts the build.
    capture_inputs(BUILD, ROOT, plan)
    env['HOLD_MUSIC_TEST_BUILD'] = str(BUILD.resolve())
    result, content = run([
        sys.executable, '-X', 'utf8', '-B', ROOT/'tools/verify_runtime_selection.py',
        '--build-dir', BUILD, '--source-root', ROOT, '--decompiler', DECOMPILER,
    ], 'runtime-selection-verification.log')
    if result.returncode:
        raise RuntimeError('Candidate runtime verification failed: ' + content)
    say(content.strip())
    current_sources = {
        p.relative_to(ROOT).as_posix(): sha256(p)
        for folder in ('src', 'data', 'imports')
        for p in sorted((ROOT / folder).rglob('*')) if p.is_file()
    }
    if current_sources != plan['source_files']:
        raise RuntimeError('Source files changed during build')
    for label, item in plan['inputs'].items():
        if sha256(Path(item['path'])) != item['sha256']:
            raise RuntimeError('Input changed during build: '+label)
    receipt = dict(schema_version=1, status='built_offline', plan=plan,
                   dependencies=dependencies, seeded_imports=seeded_imports,
                   compiled_imports={p.name: sha256(p) for p in sorted(imports.glob('*.psc'))},
                   package_hashes=hashes,
                   installed=False, runtime_verified=False)
    receipt['runtime_selection_capability'] = receipt_capability(
        (BUILD / REPORT_FILENAME).read_bytes())
    # Recheck all bound inputs immediately before publishing a success receipt.
    validate_capability(receipt, BUILD, ROOT)
    (BUILD/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    say(f'Build ready: {PACKAGE}; {len(hashes)} hashed files. Nothing installed or launched.')
    return 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        raise SystemExit(str(exc))
