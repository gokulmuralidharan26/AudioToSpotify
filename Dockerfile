FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY converter.py app.py cli.py ./
ENV PORT=8080
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:$PORT --timeout 300 --workers 2 app:app"]
