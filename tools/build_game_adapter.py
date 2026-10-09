"""Synchronize shared recipes and assemble a content-validation fixture. No game writes."""
import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def build(validation_root=None):
    package = ROOT / 'game_adapter/hold_music_adapter'
    for source, name in ((ROOT/'hold_music/regional.py', 'regional.py'),
                         (ROOT/'dashboard/palette-data.json', 'palette-data.json'),
                         (ROOT/'game_adapter/data/locations.json', 'locations.json')):
        shutil.copy2(source, package/name)
    if validation_root:
        validation_root = Path(validation_root)
        shutil.copytree(ROOT/'game_adapter/content/SKSE/Plugins/SkyrimNet/external/local.hold-music',
                        validation_root, dirs_exist_ok=True)
        prompts = validation_root/'prompts'
        prompts.mkdir(parents=True, exist_ok=True)
        shutil.copy2(package/'bard_song_lyrics.prompt', prompts/'bard_song_lyrics.prompt')
    print('Hold Music game package synchronized from canonical recipes and location registry.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation-root', type=Path)
    build(parser.parse_args().validation_root)
