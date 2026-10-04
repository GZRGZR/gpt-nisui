FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY gemini_bridge.py server.py ./
EXPOSE 9019
CMD ["python", "server.py"]
