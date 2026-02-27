# core/plugin_verify.py — Plugin signature verification
#
# Verifies plugin.sig files against baked-in public key.
# Each plugin.sig contains a manifest of SHA256 hashes + ed25519 signature.

import json
import hashlib
import logging
from pathlib import Path
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)

# Baked-in public key — corresponds to the private key used for signing
SIGNING_PUBLIC_KEY = bytes.fromhex("b4e188e374c7ddc83544cda23f4818693441bc197068a41e745d54ddf1b3b1d3")

# File extensions to verify (must match what sign_plugin.py hashes)
SIGNABLE_EXTENSIONS = {".py", ".json", ".js", ".css", ".html", ".md"}


def _build_signable_payload(manifest_data: dict) -> bytes:
    """Build the canonical bytes that were signed.

    Deterministic JSON of everything except the signature field itself.
    """
    payload = {k: v for k, v in manifest_data.items() if k != "signature"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash_file(path: Path) -> str:
    """SHA256 hex digest of a file."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return f"sha256:{h.hexdigest()}"


def verify_plugin(plugin_dir: Path) -> Tuple[bool, str]:
    """Verify a plugin's signature and file integrity.

    Returns:
        (passed, message) — passed=True if signature and all hashes match.
        If no plugin.sig exists, returns (False, "unsigned").
    """
    sig_path = plugin_dir / "plugin.sig"

    if not sig_path.exists():
        return False, "unsigned"

    # Load the signature file
    try:
        sig_data = json.loads(sig_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"corrupt plugin.sig: {e}"

    signature_b64 = sig_data.get("signature")
    if not signature_b64:
        return False, "plugin.sig missing signature field"

    files_manifest = sig_data.get("files")
    if not files_manifest:
        return False, "plugin.sig missing files manifest"

    # Verify ed25519 signature
    try:
        import base64
        signature_bytes = base64.b64decode(signature_b64)
        public_key = Ed25519PublicKey.from_public_bytes(SIGNING_PUBLIC_KEY)
        payload = _build_signable_payload(sig_data)
        public_key.verify(signature_bytes, payload)
    except InvalidSignature:
        return False, "signature verification FAILED — possible tampering"
    except Exception as e:
        return False, f"signature check error: {e}"

    # Verify each file hash
    resolved_root = plugin_dir.resolve()
    for rel_path, expected_hash in files_manifest.items():
        file_path = plugin_dir / rel_path
        # Block path traversal (../ escaping plugin directory)
        if not str(file_path.resolve()).startswith(str(resolved_root) + "/") and file_path.resolve() != resolved_root:
            return False, f"path traversal attempt: {rel_path}"
        if not file_path.exists():
            return False, f"missing file: {rel_path}"
        actual_hash = _hash_file(file_path)
        if actual_hash != expected_hash:
            return False, f"hash mismatch: {rel_path} (file modified after signing)"

    # Check for new files not in manifest (could be injected)
    for f in plugin_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.name == "plugin.sig":
            continue
        if f.suffix not in SIGNABLE_EXTENSIONS:
            continue
        # Skip __pycache__
        if "__pycache__" in f.parts:
            continue
        rel = str(f.relative_to(plugin_dir))
        if rel not in files_manifest:
            return False, f"unrecognized file not in manifest: {rel}"

    return True, "verified"
