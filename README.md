# ⚖️ Legal AI Assistant

AI-ассистент для юристов России: анализ документов на основе норм права РФ
(ГК РФ, НК РФ, судебная практика) с использованием **RAG** (Retrieval-Augmented
Generation) и **векторной базы данных pgvector**.

## Что умеет

- 📥 **Загрузка источников права (PDF)** → автоматическое чанкование, векторизация и
  сохранение в PostgreSQL + pgvector.
- 🔍 **Векторный поиск** релевантных норм по загруженному документу.
- 🤖 **Анализ документа** через ИИ: рекомендации, риски, подсветка важных моментов,
  ссылки на конкретные статьи.
- 🌐 **Веб-интерфейс** (React): загрузка drag&drop, просмотр с подсветкой,
  структурированный отчёт.

## Архитектура

```
React (Vite)  →  FastAPI (Python)  →  PostgreSQL + pgvector
                        ↓                       ↑
                  LLM (stub/                sentence-transformers
                  GigaChat/OpenAI)          (локальные embeddings)
```

**Два потока данных:**
- **Поток A (база знаний):** PDF → парсинг → чанкование → embedding → pgvector.
- **Поток B (анализ):** PDF юриста → embedding → поиск норм в pgvector → промпт → LLM → отчёт.

## Быстрый старт

### Требования
- Docker + Docker Compose
- (Опционально) API-ключ LLM-провайдера

### Запуск

```bash
# 1. Скопировать конфигурацию
cp .env.example .env

# 2. Запустить все сервисы (БД + бэкенд + фронтенд)
docker compose up --build
```

После запуска:
- **Фронтенд:** http://localhost:5173
- **Бэкенд (API + Swagger docs):** http://localhost:8000/docs
- **БД:** localhost:5432

> ⏱ Первый запуск ~5–10 минут: собираются образы и скачивается
> embedding-модель (~118 МБ). При последующих запусках — быстрее.

### Использование

1. **Наполните базу знаний** — вкладка «База знаний» → загрузите PDF
   (например, ГК РФ, НК РФ, постановления Пленумов).
2. **Проанализируйте документ** — вкладка «Анализ документа» → перетащите PDF
   договора/иска → получите отчёт с рекомендациями и ссылками на нормы.

## Выбор ИИ-провайдера

По умолчанию работает **stub** (заглушка) — возвращает мок-ответ без вызова
внешнего API. Это позволяет разрабатывать и тестировать сервис сразу.

Чтобы подключить реальный ИИ, отредактируйте `.env`:

| Провайдер | `LLM_PROVIDER` | Доп. переменные | Где взять ключ |
|-----------|----------------|-----------------|----------------|
| Заглушка (по умолч.) | `stub` | — | не нужен |
| OpenAI GPT-4o | `openai` | `OPENAI_API_KEY`, `OPENAI_MODEL` | platform.openai.com/api-keys |
| GigaChat (Сбер) | `gigachat` | `GIGACHAT_API_KEY` | developers.sber.ru |
| YandexGPT | `yandex` | `YANDEX_API_KEY`, `YANDEX_FOLDER_ID` | cloud.yandex.ru |

После изменения `.env` перезапустите: `docker compose restart backend`.

### Рекомендации по провайдеру для РФ
- **GigaChat / YandexGPT** — доступны из РФ, оплата российскими картами, хорошо
  понимают русский юридический язык.
- **OpenAI GPT-4o** — лучшее качество, но нужен VPN и иностранная карта.

## API эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| `POST` | `/api/knowledge/upload` | Загрузить PDF в базу знаний (ГК РФ, НК РФ, практика) |
| `GET` | `/api/knowledge/documents` | Список источников |
| `DELETE` | `/api/knowledge/documents/{id}` | Удалить источник |
| `POST` | `/api/analyze` | Загрузить документ юриста для анализа |
| `GET` | `/api/analyze/{id}` | Получить результат анализа |
| `GET` | `/health` | Проверка сервиса |
| `GET` | `/health/db` | Проверка БД и pgvector |
| `GET` | `/config` | Текущая конфигурация |

Полная интерактивная документация: http://localhost:8000/docs

## Структура проекта

```
legal-ai-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI приложение
│   │   ├── config.py               # Настройки из .env
│   │   ├── api/                    # REST эндпоинты
│   │   │   ├── knowledge.py        #   база знаний (Поток A)
│   │   │   ├── analysis.py         #   анализ (Поток B)
│   │   │   └── health.py
│   │   ├── core/
│   │   │   ├── llm/                # Слой абстракции над ИИ
│   │   │   │   ├── base.py         #   интерфейс
│   │   │   │   ├── stub.py         #   заглушка (по умолчанию)
│   │   │   │   ├── openai_client.py#   OpenAI GPT
│   │   │   │   └── factory.py      #   выбор провайдера
│   │   │   ├── embeddings.py       # Локальные embeddings
│   │   │   ├── pdf_parser.py       # Извлечение текста из PDF
│   │   │   ├── chunker.py          # Чанкование по статьям
│   │   │   └── rag.py              # Оркестрация RAG
│   │   ├── db/
│   │   │   ├── database.py         # Async SQLAlchemy
│   │   │   ├── models.py           # ORM-модели
│   │   │   └── vector_store.py     # Операции с pgvector
│   │   ├── schemas/                # Pydantic-схемы
│   │   └── migrations/init.sql     # Схема БД + pgvector
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.tsx                 # Главная страница
│       ├── api/client.ts           # HTTP-клиент
│       ├── components/             # UI-компоненты
│       └── types/                  # TypeScript-типы
├── docker-compose.yml
└── .env.example
```

## Технологии

| Слой | Технология |
|------|-----------|
| Backend | FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| БД | PostgreSQL 16 + pgvector (HNSW индекс) |
| Embeddings | sentence-transformers `paraphrase-multilingual-MiniLM-L12-v2` (локально, 384 dim) |
| PDF | PyMuPDF (fitz) |
| Frontend | React 18, Vite, TypeScript, TanStack Query, react-dropzone |
| Контейнеры | Docker Compose |

## Что можно улучшить дальше

- [ ] Очереди задач (Celery/RQ) для длинных анализов
- [ ] Аутентификация пользователей
- [ ] OCR для отсканированных PDF
- [ ] Экспорт отчётов в DOCX/PDF
- [ ] История анализов с поиском
- [ ] Дообучение embeddings на юридическом корпусе

## Разработка

```bash
# Бэкенд с hot-reload уже настроен в docker-compose
# Для локального запуска вне Docker:
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Фронтенд локально:
cd frontend
npm install
npm run dev
```
