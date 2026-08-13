FROM python:3.11-slim

WORKDIR /app

# System deps needed by opencv/torch at runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code, the untouched ml/ folder it wraps, and alembic migrations
COPY backend ./backend
COPY ml ./ml
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN mkdir -p uploads results

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
