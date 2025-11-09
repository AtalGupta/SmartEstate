from typing import Iterable, List, Optional


class Embeddings:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def _lazy_load(self):
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        except Exception:
            self._model = None

    def embed(self, texts: Iterable[str]) -> Optional[List[List[float]]]:
        self._lazy_load()
        texts = [t for t in texts if t is not None]
        if not texts:
            return None
        if self._model is None:
            return None
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

