# Plugin Signing & Verification

Sapphire uses ed25519 signatures to verify plugin integrity.

## Verification States

| State | Badge | Behavior |
|-------|-------|----------|
| **Signed** | Green "Signed" | Always loads |
| **Unsigned** | Yellow "Unsigned" | Blocked unless "Allow Unsigned Plugins" is on |
| **Tampered** | Red "Tampered" | Always blocked — no override |

## How It Works

Each signed plugin has a `plugin.sig` file containing:
- SHA256 hashes of every signable file (`.py`, `.json`, `.js`, `.css`, `.html`, `.md`)
- An ed25519 signature over the hash manifest

On scan, the loader verifies:
1. Signature matches the baked-in public key
2. Every file's hash matches the manifest
3. No unrecognized files were added after signing

## Sideloading (Unsigned Plugins)

`ALLOW_UNSIGNED_PLUGINS` defaults to **off**. Enable it in Settings > Plugins with the toggle. A danger dialog warns about the risks.

When enabled, unsigned plugins load with a warning. Tampered plugins are always blocked regardless of this setting.

## Signing Your Own Plugins

For plugin developers distributing through channels other than the official store:

1. Generate an ed25519 keypair
2. Hash all signable files in your plugin
3. Sign the hash manifest with your private key
4. Ship the `plugin.sig` alongside your plugin

Users install your public key to verify. The official Sapphire public key is baked into `core/plugin_verify.py`.
