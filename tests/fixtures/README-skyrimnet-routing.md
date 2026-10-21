# Public beta26-rc4 routing reconstructions

`skyrimnet-beta26-rc4-public-OpenRouter.json` and
`skyrimnet-beta26-rc4-public-Providers.json` reconstruct the native configuration
GET envelopes from this repository's public, disabled loopback seeds and the
pinned native serializer. They contain synthetic lab identifiers and empty
credentials; they are not exports of installed or private configuration.

The reviewed release ZIP has SHA256
`6b1646d52d10f71b938d09b55bb766b57af517ece11ea174b646d0a1a51fbcef`;
its `SKSE/Plugins/SkyrimNet.dll` has SHA256
`2cbb5ae8fa5aac0ff98f64d5728d1938f58c991473dbfbc39b9c88094c08e35a`.
Static preferred-image VAs are `ProvidersConfig::SaveToNode` at `0x1802670a0`,
`TextModelConfig::SaveToNode` at `0x180268a50`, its loader at `0x180252910`,
and the distinct slot serializer at `0x1808955f0`.

The compact bytes independently match the two configuration response sizes and
hashes retained by the sixth run's sanitized routing capture:

| Fixture | Bytes | SHA256 |
| --- | ---: | --- |
| OpenRouter | 2155 | `87f15080268d5bee81dd64f0dd73ea8de5fe33b053f0441b39781fd73e401179` |
| Providers | 1813 | `b26625cf5364f9dc6842d03530fab55be8c841c947eeb16077f6fadad0f34adf` |

The tests use synthetic empty schema envelopes; the two schema response bodies
were not reconstructed. The exact-byte comparison establishes the configuration
serialization case, not native execution, hidden overrides, routing safety in
other builds, or an upgrade of the historical incomplete capture. Static dumps,
reconstruction scripts and the original negative control are retained locally in
`local/se-lab-routing-sixth-static-20261021/`.
