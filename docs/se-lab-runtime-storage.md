# Runtime session-storage accounting

This module is a runtime-only exception for three newly generated PrismaUI session
files in the isolated SE lab. It does not change installation or first-boot
preflight, delete or adopt previous session data, or modify the current launcher.
Integration must be explicitly added to a new launch contract. An old failed run
must retain its original outcome.

The pinned PrismaUI 1.5.1 source constructs Ultralight configuration without
setting its cache path, and creates views with the default session. Ultralight
1.4 documents that session as persistent and named `default`. The external
PrismaUI API offers no cache-directory setting. This explains why session files
are plausible; it does not independently identify their writer. Changing CWD is
unsuitable because PrismaUI also resolves its assets and DLLs from that location.

Sources: [pinned initialization and view creation](https://github.com/PrismaUI-SKSE/framework/blob/aaef0713a6b4c775a654c427871f0fe53b75fcb6/src/PrismaUI/Core.cpp#L128),
[public API](https://github.com/PrismaUI-SKSE/framework/blob/aaef0713a6b4c775a654c427871f0fe53b75fcb6/src/PrismaUI_API.h#L35),
[Ultralight 1.4 session contract](https://ultralig.ht/api/cpp/1_4_0/classultralight_1_1_renderer.html),
[PrismaUI base path](https://github.com/PrismaUI-SKSE/framework/blob/aaef0713a6b4c775a654c427871f0fe53b75fcb6/src/Utils/DllLoader.h#L14).

## API and integration boundary

`prepare_runtime_storage(root, protected_baseline)` accepts the existing strict
`tier._protected(root)` snapshot and returns a small versioned contract. Both
fresh scans must exactly match that baseline, and `Game/default` must be absent,
including an empty directory. Preserve old session state separately through an
explicit reviewed operation before preparing a new launch; this module never
opens the three session paths or moves, copies, hashes, or deletes session data.

Retain the exact contract in the new launch intent. Bind its policy and immutable
projection hashes with the normal launch inputs. A caller must not fabricate it
after launch or reinterpret an earlier run as having opted in.

`observe_runtime_storage(root, protected_baseline, contract)` returns:

- `binding`: stable policy, root, original raw baseline digest, and immutable
  projection digest. Include this in downstream smoke/routing/MCP review tokens.
- `protected_paths_unchanged`: full observed metadata equality, which remains
  false when generated storage changes the original tree.
- `original_assets_unchanged`: every original file's metadata, manifest hash,
  lab/Game/MO2 root identities, and protected directory metadata match.
- `storage_within_contract`: storage names and file types satisfy the narrow
  policy at both observations. This alone cannot authorize a request.
- `observation`: private metadata for the three files and runtime directory at
  the first and last walk. Keep it outside token bindings because SQLite may
  create, replace, remove, or grow its sidecars between requests.
- `blockers`: fixed categories without exception text or private contents.

Require `status == "within_contract"`, `original_assets_unchanged is True`, and
`storage_within_contract is True` for runtime operations. Missing or modified
contracts raise; unsafe or incomplete observations return blocked results.

The only permitted files are:

```text
Game/default/cookie.jar.db
Game/default/cookie.jar.db-shm
Game/default/cookie.jar.db-wal
```

The module checks ordinary files and directories, exact case, case collisions,
symlinks/junctions, and hardlinks. Any additional entry inside `default`, even an
empty directory or another SQLite sidecar, blocks. All additions outside these
paths within the protected `Game`/`MO2` trees remain protected. The lab root itself
retains its identity, not a whole-root inventory guarantee. The `Game` directory retains its identity and complete
non-storage child inventory; its mtime is normalized to the baseline only while
the permitted `default` directory exists, because creating that directory changes
it. A timestamp change with no storage directory still blocks. Every other baseline directory retains
its full metadata guard. `default` did not exist in the baseline, so its changing
metadata is reported separately, not treated as an original asset.

The specialized walker does not run the old strict `_protected()` and filter
afterward: that routine can reject a changing WAL before filtering. Instead,
two walks compare the immutable projection while independently validating each
storage observation. Only the baseline manifest is opened and hashed, after
checking its retained metadata and the actual opened handle's identity before
reading any bytes; a renamed/replaced file is rejected without reading its
contents. Large
game assets retain the existing metadata drift guard, not a new content-hash
guarantee. These are point-in-time observations, not filesystem access control,
an atomic snapshot, writer attribution, or proof that no transient extra file
ever existed.

For future integration, add this module to the launch implementation hashes.
Replace only smoke's runtime protected-state equality check with this shared
classifier; leave exact run/process/module/listener checks intact. Routing and
MCP discovery already call smoke's context validator. Their stable bindings must
include the contract binding and exclude volatile observations and the full-tree
equality flag. Recheck at the existing pre/post observation boundaries. This
does not permit paid generation, enable AI, or establish zero egress.

Run the dedicated fixture suite without touching the installed lab:

```powershell
python -X utf8 -B -m unittest tests.test_se_lab_runtime_storage
```
