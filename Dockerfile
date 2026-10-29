FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --uid 10001 --create-home app \
    && mkdir /evidence && chown app:app /evidence
COPY backend/ backend/
COPY database/ database/
COPY data/ data/
COPY assets/ assets/
COPY css/ css/
COPY js/ js/
COPY scripts/ scripts/
COPY tests/ tests/
COPY deploy/ deploy/
COPY *.html pytest.ini ./
COPY Dockerfile compose.laptop.yaml .dockerignore ./
USER app
EXPOSE 5055
CMD ["waitress-serve", "--host=0.0.0.0", "--port=5055", "--threads=6", "--call", "backend.app:create_app"]

FROM runtime AS evaluation
USER root
RUN pip install --no-cache-dir pytest==8.4.2
USER app
CMD ["python", "scripts/run_database_evaluation.py", "--full-suite", "--output", "/evidence/database-evaluation.json"]
