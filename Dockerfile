FROM python:3.12-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application
COPY . .

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8000

ENV DATABASE_URL=sqlite:///data/atpp.db

CMD ["python", "-m", "web.server"]
