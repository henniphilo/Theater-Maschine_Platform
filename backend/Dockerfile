FROM python:3.11-slim

WORKDIR /app

COPY backend/pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

COPY backend/app /app/app
COPY backend/tests /app/tests
COPY backend/.env.example /app/.env.example
COPY data /app/data

ENV DIRECTOR_DATA_DIR=data

EXPOSE 8000
CMD ["sh", "-c", "python -m app.db.init_db && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
