FROM python:3.11.11-slim-bookworm

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/dualsign-ml
ENV PYTHONPATH=/opt/dualsign-ml
COPY ml/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
      torch==2.8.0 \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY ml/ ./

CMD ["sh", "-c", "ruff check . && ruff format --check . && pytest -q"]
