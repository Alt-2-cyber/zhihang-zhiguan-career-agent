FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_ENDPOINT=https://hf-mirror.com \
    HF_HOME=/models/huggingface \
    YOLO_CONFIG_DIR=/models/ultralytics

WORKDIR /app
RUN sed -i -e 's|http://security.ubuntu.com/ubuntu/|https://mirrors.aliyun.com/ubuntu/|g' -e 's|http://archive.ubuntu.com/ubuntu/|https://mirrors.aliyun.com/ubuntu/|g' /etc/apt/sources.list \
    && apt-get -o Acquire::Retries=5 update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY services/emotion/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY services/__init__.py ./services/__init__.py
COPY services/emotion ./services/emotion

EXPOSE 8104
CMD ["uvicorn", "services.emotion.app:app", "--host", "0.0.0.0", "--port", "8104"]
