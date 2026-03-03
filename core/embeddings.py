# core/embeddings.py
# Pluggable embedding provider — local ONNX or remote API (same Nomic model)

import logging
import numpy as np
import config

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = 'nomic-ai/nomic-embed-text-v1.5'
EMBEDDING_ONNX_FILE = 'onnx/model_quantized.onnx'


class LocalEmbedder:
    """Lazy-loaded nomic-embed-text-v1.5 via ONNX runtime."""

    def __init__(self):
        self.session = None
        self.tokenizer = None
        self.input_names = None

    def _load(self):
        if self.session is not None:
            return
        try:
            import onnxruntime as ort
            from transformers import AutoTokenizer
            from huggingface_hub import hf_hub_download

            try:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    EMBEDDING_MODEL, trust_remote_code=True, local_files_only=True)
                model_path = hf_hub_download(
                    EMBEDDING_MODEL, EMBEDDING_ONNX_FILE, local_files_only=True)
            except Exception:
                logger.info(f"Downloading embedding model: {EMBEDDING_MODEL}")
                self.tokenizer = AutoTokenizer.from_pretrained(
                    EMBEDDING_MODEL, trust_remote_code=True)
                model_path = hf_hub_download(EMBEDDING_MODEL, EMBEDDING_ONNX_FILE)

            self.session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
            self.input_names = [i.name for i in self.session.get_inputs()]
            logger.info(f"Embedding model loaded: {EMBEDDING_MODEL} (quantized ONNX)")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.session = None

    def embed(self, texts, prefix='search_document'):
        self._load()
        if self.session is None:
            return None
        try:
            prefixed = [f'{prefix}: {t}' for t in texts]
            encoded = self.tokenizer(prefixed, return_tensors='np', padding=True,
                                     truncation=True, max_length=512)
            inputs = {k: v for k, v in encoded.items() if k in self.input_names}
            if 'token_type_ids' not in inputs:
                inputs['token_type_ids'] = np.zeros_like(inputs['input_ids'])

            outputs = self.session.run(None, inputs)
            embeddings = outputs[0]
            mask = encoded['attention_mask']
            masked = embeddings * mask[:, :, np.newaxis]
            pooled = masked.sum(axis=1) / mask.sum(axis=1, keepdims=True)
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            return (pooled / norms).astype(np.float32)
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return None

    @property
    def available(self):
        self._load()
        return self.session is not None


class RemoteEmbedder:
    """OpenAI-compatible embedding API client (for Nomic via TEI, etc.)."""

    def embed(self, texts, prefix='search_document'):
        url = getattr(config, 'EMBEDDING_API_URL', '')
        if not url:
            return None
        try:
            import httpx
            key = getattr(config, 'EMBEDDING_API_KEY', '')
            headers = {}
            if key:
                headers['Authorization'] = f'Bearer {key}'

            prefixed = [f'{prefix}: {t}' for t in texts]
            resp = httpx.post(url, json={'input': prefixed, 'model': EMBEDDING_MODEL},
                              headers=headers, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()['data']
            vecs = np.array([d['embedding'] for d in data], dtype=np.float32)
            # L2-normalize (safe regardless of server behavior)
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            norms[norms == 0] = 1
            return (vecs / norms).astype(np.float32)
        except Exception as e:
            logger.error(f"Remote embedding failed: {e}")
            return None

    @property
    def available(self):
        return bool(getattr(config, 'EMBEDDING_API_URL', ''))


class NullEmbedder:
    """Disabled — consumers fall back to FTS5/LIKE search."""

    def embed(self, texts, prefix='search_document'):
        return None

    @property
    def available(self):
        return False


# ─── Singleton + hot-swap ────────────────────────────────────────────────────

_embedder = None


def _create_embedder(provider_name=None):
    name = provider_name or getattr(config, 'EMBEDDING_PROVIDER', 'local')
    if name == 'api':
        return RemoteEmbedder()
    if name == 'local':
        return LocalEmbedder()
    return NullEmbedder()


def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = _create_embedder()
    return _embedder


def switch_embedding_provider(provider_name):
    global _embedder
    logger.info(f"Switching embedding provider to: {provider_name}")
    _embedder = _create_embedder(provider_name)
