FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_ENDPOINT=https://hf-mirror.com \
    MECABRC=/opt/conda/lib/python3.11/site-packages/unidic_lite/dicdir/mecabrc

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg git \
    && rm -rf /var/lib/apt/lists/*
COPY services/speech/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "from pathlib import Path; import unidic, unidic_lite; Path(unidic.DICDIR).symlink_to(unidic_lite.DICDIR, target_is_directory=True)" \
    && python -c "import MeCab; MeCab.Tagger()"
COPY services/speech/melo_cleaner.py /opt/conda/lib/python3.11/site-packages/melo/text/cleaner.py
COPY services/speech/melo_text_init.py /opt/conda/lib/python3.11/site-packages/melo/text/__init__.py
COPY services/speech/patch_melo.py ./patch_melo.py
RUN python ./patch_melo.py
COPY services/__init__.py ./services/__init__.py
COPY services/speech ./services/speech

EXPOSE 8103
CMD ["uvicorn", "services.speech.app:app", "--host", "0.0.0.0", "--port", "8103"]
