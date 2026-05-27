FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl git procps net-tools iproute2 \
    gcc g++ build-essential ca-certificates gnupg lsb-release \
    fluidsynth fluid-soundfont-gm ffmpeg

# Install Docker CLI (so skyd can talk to the host socket)
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
    https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y docker-ce-cli

RUN pip install json-repair psutil httpx gitpython requests libcst music21 mido pretty_midi

WORKDIR /skyd
COPY skyd.py .
COPY wolf_spider.py .
COPY media_janitor.py .
COPY media_personality.py .
COPY skyd_watchdog.py .
COPY plex_cc_trainer.py .
COPY run_cc_scan.py .
COPY clean_corpus.py .
COPY skyd_music.py .
COPY skyd_daw.py .
COPY skyd_self_model.py .
COPY skyd_enhancements.py .
COPY skyd_sandbox.py .

RUN mkdir -p /usr/local/skyd/asm /usr/local/skyd/lang

CMD ["python3", "-u", "skyd.py"]
