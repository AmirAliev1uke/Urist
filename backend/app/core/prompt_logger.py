"""Логирование промтов и ответов LLM в отдельный файл.

Пишет в logs/prompts.log в читаемом формате с разделителями между запросами.
Это позволяет анализировать: что реально уходит в модель и что она возвращает.

Файл хранится вне основного лога приложения (loguru), чтобы его было удобно
читать отдельно. Лог-файлы не пишем в stdout — только в файл.
"""
import json
import threading
from datetime import datetime
from pathlib import Path

from app.config import get_settings

settings = get_settings()

# Каталог логов внутри контейнера (примонтирован как volume в docker-compose)
LOG_DIR = Path(settings.prompt_log_dir)
LOG_FILE = LOG_DIR / "prompts.log"

# Блокировка, чтобы параллельные запросы не перемешивали записи
_lock = threading.Lock()


def log_prompt(
    *,
    provider: str,
    system_prompt: str,
    user_prompt: str,
    context_chunks: list[dict] | None = None,
    response: str | None = None,
    error: str | None = None,
    file_name: str | None = None,
    extra: dict | None = None,
) -> None:
    """Записать промт и ответ модели в файл logs/prompts.log.

    Аргументы:
        provider: имя провайдера ('gigachat', 'openai', ...)
        system_prompt: системная инструкция
        user_prompt: пользовательский промт (с документом и контекстом)
        context_chunks: найденные в pgvector нормы (title, article_ref, similarity)
        response: сырой ответ модели (если был)
        error: текст ошибки (если запрос упал)
        file_name: имя анализируемого файла
        extra: доп. метаданные (модель, температура, токены)
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Контекстные чанки компактно
    context_lines = []
    if context_chunks:
        for i, chunk in enumerate(context_chunks, start=1):
            title = chunk.get("title", "?")
            ref = chunk.get("article_ref") or ""
            sim = chunk.get("similarity", 0)
            context_lines.append(f"  [{i}] {title} | {ref} | sim={sim:.3f}")
    context_block = "\n".join(context_lines) if context_lines else "  (пусто)"

    # Доп. метаданные
    extra_str = ""
    if extra:
        extra_str = "\n".join(f"  {k}: {v}" for k, v in extra.items())

    record = f"""
{'=' * 80}
[{timestamp}] PROVIDER: {provider}  |  FILE: {file_name or '—'}
{'=' * 80}

--- СИСТЕМНЫЙ ПРОМТ ({len(system_prompt)} символов) ---
{system_prompt}

--- ПОЛЬЗОВАТЕЛЬСКИЙ ПРОМТ ({len(user_prompt)} символов) ---
{user_prompt}

--- КОНТЕКСТ (найдено норм: {len(context_chunks or [])}) ---
{context_block}
"""
    if extra_str:
        record += f"\n--- ПАРАМЕТРЫ ЗАПРОСА ---\n{extra_str}\n"

    if error:
        record += f"\n--- ❌ ОШИБКА ---\n{error}\n"
    elif response is not None:
        record += f"\n--- ОТВЕТ МОДЕЛИ ({len(response)} символов) ---\n{response}\n"
    else:
        record += "\n--- ОТВЕТ МОДЕЛИ ---\n(не получен)\n"

    record += f"{'=' * 80}\n\n"

    with _lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(record)


def log_prompt_jsonl(
    *,
    provider: str,
    messages: list[dict],
    response: str | None = None,
    error: str | None = None,
    extra: dict | None = None,
) -> None:
    """Альтернативный формат: одна строка JSON на запрос (для машинной обработки).

    Удобно, если потом захочется анализировать логи скриптами.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now().isoformat(),
        "provider": provider,
        "messages": messages,
    }
    if response is not None:
        record["response"] = response
    if error:
        record["error"] = error
    if extra:
        record["extra"] = extra

    with _lock:
        with open(LOG_DIR / "prompts.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
