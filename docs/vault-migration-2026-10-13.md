# Home-vault migration to the project vault

**Migrated:** 2026-10-13
**Project vault:** `/Users/pythagor/hold_music`
**Former location:** `/Users/pythagor/Obsidian/Home/Skyrim/hold_music`

The project is now the working Obsidian vault and repository. Canonical target styles and prompt fragments remain in [the regional spec](bard-regional-music-spec.md); listening research is [a companion document](skyrim-hold-music-listening-notes.md). Generated dashboards and game-package palettes are rebuilt from these sources.

| Former note | Project working copy | Consolidation |
|---|---|---|
| `bard-regional-music-spec.md` | [Regional spec](bard-regional-music-spec.md) | Retained the newer repository spec, including instrument adaptations, vocal release gates, optional lyrics, compact prompts and candidate revisions. |
| `bard-musical-traditions-exploration.md` | [Idea bank](bard-musical-traditions-exploration.md) | Retained the repository copy; differences were portable dashboard/review links. |
| `bard-roster-and-biography-audit.md` | [Roster audit](bard-roster-and-biography-audit.md) | Retained the portable repository audit and biography filenames. The original installation-specific Windows links remain in the archived source. |
| `skyrim-hold-music-listening-notes.md` | [Listening notes](skyrim-hold-music-listening-notes.md) | Imported the latest Home-vault text, preserving playlists and discussion; added working-copy and candidate-status notes. |

The four former notes retain their filenames as navigation notes linking into the new vault. This preserves existing Home-vault note references without retaining four competing working documents. Their original contents were copied and verified by SHA-256 before replacement.

## Original archive

The local archive is outside both working vaults:

`/Users/pythagor/.local/share/hold-music/vault-migration/2026-10-13/`

- `home-vault-originals/` contains all four unmodified source files.
- `manifest.json` records source paths, sizes and SHA-256 hashes.
- `project-before/` preserves selected project files before consolidation.

This local archive is not committed to the repository. Halcyon vault setup and deployment remain separate work. No active musical recipe or candidate adoption was changed by this migration. Browser-edited prompts and existing takes remain unchanged.

Rebuild all local generated palette views with `python3 tools/rebuild_palette.py`. The editorial date comes from the spec's ISO `Reconciled` field; an explicit `--date` overrides it. Obsidian's `.obsidian/` settings remain local and are ignored by Git.

Prepared by Codex, running GPT-6.
