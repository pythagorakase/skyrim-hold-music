# Pinned SkyrimNet startup model downloads: offline audit

This is static evidence from the clean beta26-rc4 archive. No DLL was executed, no network request was made, and no live log, private configuration, installed model, or database content was read. These findings do not establish a no-egress runtime.

## Finding

Disabling general AI, memory background processing, and STT does not surround the pinned build's embedding and VAD verification queues with a conditional branch. No exposed embedding/VAD initialization or automatic-download switch was found in the inspected clean Memory schema/loader or the shipped UI corpus. This is a bounded negative finding, not proof that no configuration mechanism exists anywhere in the binary.

There is a useful, directly established alternative: the native downloader can reuse an existing file whose SHA-256 matches its pinned catalog. That branch returns success before the transfer routine. It may create/update a `.verified` sidecar. Existing files and their real destinations have not been inventoried in this audit.

## Exact source identity

- Archive: `local/se-lab-downloads/skyrimnet-beta26-rc4.zip`, SHA-256 `6b1646d52d10f71b938d09b55bb766b57af517ece11ea174b646d0a1a51fbcef`.
- Member: `SKSE/Plugins/SkyrimNet.dll`, SHA-256 `2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a`, image base `0x180000000`.
- Shipped UI map: `SKSE/Plugins/SkyrimNet/assets/web-new/main.c12d8cff.js.map`, SHA-256 `2dab71be5240d800e265e24410cdb947612a2d8fd7fbedba37a3abc2929545a9`.

Addresses below refer to this exact DLL. Adjacent `.txt` files retain static disassemblies; they are evidence, not executable patches.

## Native startup and download path

| Evidence | Established behavior |
| --- | --- |
| `OnPostLoad`, `0x1801c5800–0x1801c6b3e`; `1801c5800.txt` | Queues `ModelVerifyEmbedding` at `0x1801c644c` and `ModelVerifyVad` at `0x1801c6775`. Neither queue has a general-AI, memory-background, or STT-backend gate in this path. |
| Embedding task, `0x1801bd170–0x1801bd336`; `1801bd170.txt` | Builds the two pinned requests via `0x1801be370` at `0x1801bd23c`, then starts the batch at `0x1801bd24c` through `0x180f8c660`. |
| VAD task, `0x1801bd510–0x1801bd93b`; `1801bd510.txt` | Builds the fixed `silero-vad/silero_vad.onnx` catalog request and calls `StartDownload` at `0x1801bd750`. No STT-backend condition occurs in the task. |
| Memory initialize, `0x180d5fb80–0x180d60607`; `180d5fb80.txt` | After resolving configuration, calls `SetupEmbeddingService` at `0x180d600da` without an enable gate. |
| Embedding setup, entry `0x180d63c80`; `180d63c80.txt` | Calls `DownloadModelFiles` at `0x180d63cad` before initializing the embedding service. |
| Memory schema `0x180859f40–0x18085c364`, loader `0x18085c370–0x18085cda2` | `enable_background_processing` controls background memory processing/generation. The inspected fields provide no embedding-init/download-disable setting. |
| Catalog builder `0x180f8b3a0–0x180f8b916`; `180f8b3a0.txt` | Looks up a pinned catalog entry and copies its URL, expected hash and size into a download request. |

The Whisper verification queue is gated on an STT configuration object being available, rather than a visible backend comparison in `OnPostLoad`. Its downstream task was not followed far enough to claim whether `backend=none` prevents a Whisper download. Do not extend the embedding/VAD finding to Whisper without that follow-up.

## Verified existing-file branch

`existing-file-branch-static-disassembly.txt`, SHA-256 `9c478e7b7bb78fcd911b7e06b99aa8a5b20db82e9ce1fea98598ed8f43f7a7bc`, independently reviewed:

1. Job handler `0x1810141b0` selects `EnsureFile` when the expected-hash string is nonempty (`0x181014210`, call `0x1810142a8`).
2. `EnsureFile` at `0x18101f1a0` checks the existing destination and invokes the local hash routine at `0x18101f33a`.
3. It compares digest length and bytes at `0x18101f753–0x18101f764`.
4. A match writes a `.verified` sidecar, logs successful SHA verification, constructs success at `0x18101f7e2`, and returns through `0x18101fc43`. It bypasses `RunTransfer` at `0x18101fa43`.
5. Missing/mismatching files can reach transfer. A read/hash failure returns failure. A separate sidecar shortcut checks the expected hash and saved file metadata; therefore not every later startup necessarily rehashes the full file.

This supports exact offline reuse when the files already exist. It does not justify placeholders, disabling verification, editing the expected hashes, fabricating verification sidecars, or claiming other network paths are blocked.

## Pinned model inputs

The catalog table is at `0x181a59100`, with 231 entries of 56 bytes. `pinned-catalog.json` retains the exact clean catalog URLs, SHA-256 values, sizes and entry addresses. URLs were extracted only; none was requested.

| Destination basename | Catalog key | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `all-MiniLM-L6-v2.onnx` | `embedding/model.onnx` | 90,445,823 | `994a58868f7abacacbf2192aa0aae8f56da8c4505dbde2740c861b24426ede6b` |
| `all-MiniLM-L6-v2-tokenizer.json` | `embedding/tokenizer.json` | 711,661 | `da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0` |
| `silero_vad.onnx` | `silero-vad/silero_vad.onnx` | 2,327,524 | `2623a2953f6ff3d2c1e61740c6cdb7168133479b267dfef114a4a3cc5bdd788f` |

The model-directory getter `0x1801c05c0` resolves the registered path override at offset `0x60`, or otherwise the mod directory plus `models`, and ensures that directory exists. No supported user-facing override key was identified. This is a logical native path, not a verified physical MO2 write target. The archive's 371 `models/` files are eSpeak-NG data and do not supply these three files.

## Shipped UI corroboration and limits

Paths here are embedded source-map sources under `webpack://skyrimnet-dashboard-browser/../shared/`:

- `pages/settings/GeneralSection.jsx:47–53`: the general AI toggle; `:71–77`: a distinct base-content update setting.
- `pages/settings/MemorySection.jsx:49,55–63`: background memory processing; `:309–317` and `:331–360`: embedding weight and vector-index controls, not initialization/download controls.
- `pages/VoiceSTT.sections.jsx:14–20,68–70`: disabled STT uses `none`.
- `components/tutorial/steps/TTSSelect.jsx:24–26,39–53`: TTS opt-out uses `noop`.
- `hooks/useWhisperDownload.js:52–60`: an explicit manual Whisper-download action. This action was not invoked.

The UI search covered 79 source maps, 843 distinct non-vendor source bodies, and 12 clean configuration/document candidates. The generic native `model_path` reference investigated at `0x18024de70` belongs to Piper voice mapping, not embedding. Piper preloading, base-content updates, Whisper selection and the embedding/VAD queues are separate behaviors; no one toggle was established as a universal startup-download control.

## Small next step after the fifth run is closed and retained

1. Read the archived fifth log with the sanitized summary helper to establish what this particular run actually initialized/downloaded. Do not infer fifth-run activity from the fourth-run log or from a static reachable path.
2. Perform a read-only inventory of the three exact model basenames and their sidecars within the explicitly retained fifth-tier roots and the already reviewed lab path set. Record paths, sizes and hashes; do not inspect arbitrary user/model stores or private database contents. Establish the logical-to-physical MO2 destination before proposing reuse.
3. If exact catalog-matching bytes are present, propose a separately reviewed, lab-owned seed/copy with provenance for the next fresh tier. Account for native `.verified` sidecar writes and any genuinely mutable model bookkeeping explicitly. They are not covered by the current three-cookie-file runtime-storage exception; do not broaden that exception or suppress immutable-asset changes.
4. If the matching bytes are absent, state that a future authorized download or a separate external network restriction would be needed. Do not auto-fetch models, change credentials, patch the DLL, or enable AI as part of this audit.
5. Keep QASmoke world readiness separate: disabled Hold Music MCM/control/request state prevents unintended lab scenarios, but does not disable SkyrimNet's unconditional embedding/VAD verification. Even successful local reuse of these three models would not certify absence of other egress.

No implementation or installation is proposed in this checkpoint. The immediate deliverable is a source-backed constraint and a small, verifiable offline-reuse plan.

## Subsequent retained-file verification

After fifth-run closure and verified whole-tier retention, the three exact
catalog files were found under the retained MO2 instance's
`overwrite/SKSE/Plugins/SkyrimNet/models/`. Each size and SHA-256 matches the
table above and the retained inventory. The old verification sidecars remain
in that checkpoint and were not copied into a new seed.

A separate local archive containing only these three public files was staged:
`local/se-lab-startup-model-cache-20261021/startup-models.zip`, 93,485,572 bytes,
SHA-256 `1979b976999bab8b3e66acb290786b978f0ae9e2964611e92f9288e4f0fa62fc`.
Its receipt binds the original catalog and retention receipt, source paths,
sizes and hashes. Archive membership, CRC and extracted hashes were verified.
No model download or installation occurred during this staging operation.
Using this seed and observing native sidecar destinations remain separate
installation/runtime steps.
