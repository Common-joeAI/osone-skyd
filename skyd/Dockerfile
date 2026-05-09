FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl git procps net-tools iproute2

RUN pip install psutil httpx gitpython requests

WORKDIR /skyd
COPY skyd.py .
COPY wolf_spider.py .

# SkyLang rules and logs mounted from Unraid
VOLUME ["/usr/local/skyd/lang", "/var/log"]

# Create required dirs
RUN mkdir -p /usr/local/skyd/asm /usr/local/skyd/lang

CMD ["python3", "-u", "skyd.py"]
