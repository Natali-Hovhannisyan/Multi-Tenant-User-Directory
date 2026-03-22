FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \n    PYTHONUNBUFFERED=1 \n    PIP_NO_CACHE_DIR=1 \n    PIPENV_VENV_IN_PROJECT=1

WORKDIR /app

RUN pip install --no-cache-dir pipenv

COPY Pipfile ./
RUN pipenv install --dev

COPY . .

CMD ["python", "-m", "src.multi_tenant_directory.main"]
