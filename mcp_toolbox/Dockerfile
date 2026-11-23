ARG BUILD_FROM
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py publisher.py ./
COPY tools/ ./tools/
CMD ["python", "-u", "/app/server.py"]
