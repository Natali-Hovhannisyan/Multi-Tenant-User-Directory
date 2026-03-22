FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIPENV_VENV_IN_PROJECT=1

WORKDIR /app

RUN pip install --no-cache-dir pipenv

COPY Pipfile ./
RUN pipenv install --dev --system

COPY . .

CMD ["python", "-m", "src.multi_tenant_directory.main"]
