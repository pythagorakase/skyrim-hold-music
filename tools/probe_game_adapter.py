"""Read-only MO2 VFS probe; saves a report and requests no music."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'game_adapter/hold_music_adapter'))
from engine import get_scalar, read_text
from service import health

record = json.loads((ROOT/'local/installation.json').read_text(encoding='utf-8'))
root = Path(record['root'])
data = root/'mods'/record['data_mod']/'SKSE/Plugins/SkyrimNet'
virtual = Path(record['game_data'])/'SKSE/Plugins/SkyrimNet'
result = {'ok': False}
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--disabled', action='store_true')
parser.add_argument('--validator', type=Path)
args = parser.parse_args()
disabled = args.disabled
try:
    config = read_text(virtual/'config/BardSinging.yaml')
    result['provider'] = get_scalar(config, ('bard_singing', 'provider'))
    result['source_config_unchanged'] = hashlib.sha256((data/'config/BardSinging.yaml').read_bytes()).hexdigest() == record['source_config_sha256']
    content = virtual/'external/local.hold-music'
    # Python 3.12 stat/is_file can miss MO2 virtual files; test native reads.
    try:
        manifest = json.loads(read_text(content/'manifest.json'))
        result['content_visible'] = manifest['id'] == 'local.hold-music'
        result['content_version'] = manifest['version']
    except OSError:
        result['content_visible'] = False
    try:
        read_text(virtual/'external/local.solo-lute/manifest.json')
        result['old_content_visible'] = True
    except OSError:
        result['old_content_visible'] = False
    try:
        prompt = read_text(content/'prompts/bard_song_lyrics.prompt')
        result['context_prompt_visible'] = True
    except OSError:
        result['context_prompt_visible'] = False
    if result['context_prompt_visible']:
        expected = (ROOT/'game_adapter/hold_music_adapter/bard_song_lyrics.prompt').read_bytes()
        result['prompt_matches_package'] = (content/'prompts/bard_song_lyrics.prompt').read_bytes() == expected
        result['prompt_enumerated'] = 'bard_song_lyrics.prompt' in {p.name for p in (content/'prompts').iterdir()}
        result['content_enumerated'] = 'local.hold-music' in {p.name for p in (virtual/'external').iterdir()}
        fixture = ROOT/'local/vfs-content'
        for relative in ('manifest.json', 'settings/HoldMusic.yaml', 'prompts/bard_song_lyrics.prompt'):
            destination = fixture/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((content/relative).read_bytes())
        if args.validator:
            validation = ROOT/'local/vfs-native-validation.json'
            run = subprocess.run([str(args.validator), str(content), '--context', str(ROOT/'local/render-context.json'),
                                  '--report', str(validation), '--render-out', str(ROOT/'local/vfs-rendered')],
                                 capture_output=True, timeout=30)
            result['native_content_validated'] = run.returncode == 0
            if validation.exists():
                report = json.loads(validation.read_text(encoding='utf-8'))
                result['native_content_validated'] = (run.returncode == 0 and report['ok'] and report['files'] == 2)
                result['native_validation'] = report
    if result['provider'] == 'acestep_local':
        url = get_scalar(config, ('bard_singing', 'acestep_local', 'base_url'))
        result['loopback_route'] = url.startswith('http://127.0.0.1:') and '/hold-music/' in url
        result['adapter'] = health(url)
    if disabled:
        result['ok'] = result['provider'] == 'openrouter' and result['source_config_unchanged'] and not result['content_visible'] and not result['context_prompt_visible']
    else:
        result['ok'] = (result['provider'] == 'acestep_local' and result['source_config_unchanged']
            and result['content_visible'] and not result['old_content_visible']
            and result['prompt_matches_package'] and result['prompt_enumerated'] and result['content_enumerated']
            and result.get('loopback_route', False))
        if args.validator:
            result['ok'] = result['ok'] and result.get('native_content_validated', False)
except Exception as exc:
    result['error_type'] = type(exc).__name__
(ROOT/('local/vfs-disabled.json' if disabled else 'local/vfs-probe.json')).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
sys.exit(0 if result['ok'] else 1)
