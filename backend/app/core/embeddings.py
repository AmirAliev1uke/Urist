"""Локальные embeddings на базе sentence-transformers.

Модель paraphrase-multilingual-MiniLM-L12-v2:
  - 384 измерения, ~118 МБ
  - Хорошо работает с русским юридическим текстом
  - Загружается один раз и переиспользуется (синглтон)
"""
import threading

from loguru import logger

from app.config import get_settings

settings = get_settings()


class Embedder:
    """Синглтон-обёртка над sentence-transformers с ленивой загрузкой модели."""

    _instance: "Embedder | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "Embedder":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._model = None  # type: ignore[attr-defined]
        return cls._instance

    @property
    def model(self):
        """Ленивая загрузка модели при первом обращении."""
        if self._model is None:  # type: ignore[attr-defined]
            with self._lock:
                if self._model is None:  # type: ignore[attr-defined]
                    logger.info(
                        "Загрузка embedding-модели {}...", settings.embedding_model
                    )
                    # Импорт здесь — чтобы не тащить тяжёлые зависимости при импорте модуля
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(  # type: ignore[attr-defined]
                        settings.embedding_model,
                        device="cpu",
                    )
                    logger.info(
                        "Embedding-модель загружена (dim={})",
                        self._model.get_sentence_embedding_dimension(),  # type: ignore[attr-defined]
                    )
        return self._model  # type: ignore[attr-defined]

    def warmup(self) -> None:
        """Предзагрузить модель (используется при сборке Docker-образа)."""
        _ = self.model

    def embed_text(self, text: str) -> list[float]:
        """Получить вектор одного текста."""
        if not text.strip():
            # Нулевой вектор для пустого ввода — pgvector справится
            return [0.0] * settings.embedding_dim
        vec = self.model.encode(
            text, normalize_embeddings=True, convert_to_numpy=True
        )
        return vec.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Получить векторы списка текстов (эффективнее, чем по одному)."""
        if not texts:
            return []
        vecs = self.model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, batch_size=32
        )
        return [v.tolist() for v in vecs]


def get_embedder() -> Embedder:
    """Фабрика для DI в FastAPI."""
    return Embedder()
