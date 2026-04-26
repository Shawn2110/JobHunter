FROM python:3.12-slim

# Layer caching: install build tools once, reuse across deps.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy manifest first so dep install caches independently of app changes.
COPY pyproject.toml ./

# Install runtime deps. The editable install needs the package source, so
# we touch a placeholder and replace it when the real source lands below.
RUN mkdir -p app && touch app/__init__.py && pip install --no-cache-dir -e .

# Copy the actual source.
COPY . .

EXPOSE 8000

# Healthcheck is configured at the compose layer; keep the image tool-free.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
