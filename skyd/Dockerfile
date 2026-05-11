FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl git procps net-tools iproute2 \
    gcc g++ build-essential

RUN pip install psutil httpx gitpython requests

WORKDIR /skyd
COPY skyd.py .
COPY wolf_spider.py .
COPY media_janitor.py .

RUN mkdir -p /usr/local/skyd/asm /usr/local/skyd/lang

CMD ["python3", "-u", "skyd.py"]
