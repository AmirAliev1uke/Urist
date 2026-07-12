FROM python:3.12-slim

# Системные библиотеки для компиляции зависимостей и работы PDF/Torch
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.hf_cache

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Установка зависимостей отдельным слоем (кешируется)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Предзагрузка embedding-модели при сборке (чтобы не качать при каждом запуске)
RUN python -c "from app.core.embeddings import Embedder; Embedder().warmup()" || \
    echo "Предзагрузка модели пропущена — будет загружена при первом запуске"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
