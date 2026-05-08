FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl git procps net-tools iproute2

RUN pip install psutil httpx gitpython requests

WORKDIR /skyd
COPY skyd.py .

VOLUME ["/usr/local/skyd/lang", "/var/log"]

CMD ["python3", "-u", "skyd.py"]
