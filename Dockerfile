FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PORT=8080 \
    DB_PATH=/app/legal_agent_index.db \
    DB_MEM_PATH=/app/legal_agent_memory.db

COPY . /app/

EXPOSE 8080

CMD ["python3", "app.py"]
