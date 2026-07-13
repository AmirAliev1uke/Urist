"""Клиент Qdrant: синглтон с инициализацией коллекции.

Создаёт коллекцию legal_chunks при старте с квантизацией (экономия памяти)
и payload-индексами для быстрой фильтрации по году, типу суда и т.д.
"""
import threading

from loguru import logger

from app.config import get_settings

settings = get_settings()


class QdrantSingleton:
    """Синглтон Qdrant-клиента с ленивой инициализацией."""

    _instance: "QdrantSingleton | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "QdrantSingleton":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._client = None  # type: ignore[attr-defined]
        return cls._instance

    @property
    def client(self):
        """Ленивая инициализация клиента + коллекции."""
        if self._client is None:  # type: ignore[attr-defined]
            with self._lock:
                if self._client is None:  # type: ignore[attr-defined]
                    self._client = self._init_client()  # type: ignore[attr-defined]
        return self._client  # type: ignore[attr-defined]

    def _init_client(self):
        """Создать клиент и убедиться, что коллекция существует."""
        from qdrant_client import QdrantClient
        from qdrant_client.http.models import (
            Distance,
            PayloadSchemaType,
            ScalarQuantization,
            ScalarQuantizationConfig,
            ScalarType,
            VectorParams,
        )

        logger.info("Подключение к Qdrant: {}", settings.qdrant_url)
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=30,
        )

        self._ensure_collection(client)
        return client

    def _ensure_collection(self, client) -> None:
        """Создать коллекцию с квантизацией и индексами, если её нет."""
        from qdrant_client.http.models import (
            Distance,
            PayloadSchemaType,
            ScalarQuantization,
            ScalarQuantizationConfig,
            ScalarType,
            VectorParams,
        )

        collection = settings.qdrant_collection
        existing = client.get_collections().collections
        names = [c.name for c in existing]

        if collection in names:
            logger.info("Коллекция Qdrant '{}' уже существует", collection)
            self._ensure_payload_indexes(client, collection)
            return

        logger.info("Создание коллекции '{}' (dim={})...", collection, settings.embedding_dim)
        client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=settings.embedding_dim,
                distance=Distance.COSINE,
            ),
            # Квантизация: храним векторы как int8 — экономия памяти в 4 раза
            # при минимальной потере точности. Для миллионов чанков это критично.
            quantization_config=ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                )
            ),
        )
        self._ensure_payload_indexes(client, collection)
        logger.info("Коллекция '{}' создана с квантизацией int8", collection)

    def _ensure_payload_indexes(self, client, collection: str) -> None:
        """Создать индексы по payload-полям для быстрой фильтрации."""
        from qdrant_client.http.models import PayloadSchemaType

        # Поля, по которым будет фильтрация при поиске
        indexes = [
            ("document_id", PayloadSchemaType.INTEGER),
            ("doc_type", PayloadSchemaType.KEYWORD),
            ("year", PayloadSchemaType.INTEGER),
            ("court_level", PayloadSchemaType.KEYWORD),
        ]

        for field, schema in indexes:
            try:
                client.create_payload_index(
                    collection_name=collection,
                    field_name=field,
                    field_schema=schema,
                )
                logger.debug("Индекс payload.{} создан", field)
            except Exception as exc:  # noqa: BLE001
                # Индекс мог уже существовать — это нормально
                if "already" not in str(exc).lower():
                    logger.debug("Индекс {}: {}", field, exc)


def get_qdrant() -> QdrantSingleton:
    """Фабрика для DI в FastAPI."""
    return QdrantSingleton()
