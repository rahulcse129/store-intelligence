FROM python:3.9-slim

# Install system dependencies for OpenCV and PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements or install them directly to avoid extra files
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    ultralytics \
    fastapi \
    uvicorn \
    sqlalchemy \
    psycopg2-binary \
    alembic \
    streamlit \
    requests \
    pandas \
    numpy \
    pydantic \
    pydantic-settings \
    pytest \
    pytest-cov \
    httpx \
    plotly \
    scipy \
    filterpy

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8000 8501

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
