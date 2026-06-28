FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt

# Install the package
COPY pyproject.toml ./
COPY lifetxt/ ./lifetxt/
RUN pip install --no-cache-dir -e .

# Copy demo data
COPY examples/ ./examples/

# Runtime config
ENV HOST=0.0.0.0
ENV PORT=8000
ENV DEMO_FILE=examples/tasks_life.txt

EXPOSE 8000

CMD lifetxt serve "${DEMO_FILE}" \
    --host "${HOST}" \
    --port "${PORT}" \
    --read-only
