FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (cached layer — only rebuilds when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

# Bind to 127.0.0.1 — only nginx can reach the API
CMD ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--workers", "2"]