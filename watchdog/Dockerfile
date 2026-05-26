FROM python:3.11-slim
RUN apt-get update && apt-get install -y curl && pip install requests psutil
WORKDIR /app
COPY skyd_watchdog.py .
CMD ["python3", "-u", "skyd_watchdog.py"]
