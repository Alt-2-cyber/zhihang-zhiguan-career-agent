FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_ENDPOINT=https://hf-mirror.com

WORKDIR /app
COPY services/embedding/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt
COPY services/__init__.py ./services/__init__.py
COPY services/embedding ./services/embedding

EXPOSE 8101
CMD ["uvicorn", "services.embedding.app:app", "--host", "0.0.0.0", "--port", "8101"]
