FROM python:3.12-slim
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --only-binary :all: -r requirements.txt
COPY db-writer.py .
RUN useradd -m appuser
USER appuser
CMD ["python", "db-writer.py"]