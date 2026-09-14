FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY db_writer.py .
RUN useradd -m appuser
USER appuser
CMD ["python", "db_writer.py"]