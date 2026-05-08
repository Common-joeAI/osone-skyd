FROM nvidia/cuda:12.4.1-devel-ubuntu22.04

RUN apt-get update && apt-get install -y \
    build-essential cmake git curl python3

# Build llama.cpp with CUDA support
RUN git clone https://github.com/ggerganov/llama.cpp /llama.cpp
WORKDIR /llama.cpp
RUN cmake -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release && \
    cmake --build build --config Release -j$(nproc) --target llama-server

EXPOSE 8080

# Model mounted from Unraid: /mnt/user/models/llama3.2.gguf -> /models/llama3.2.gguf
ENTRYPOINT ["/llama.cpp/build/bin/llama-server", \
    "--model", "/models/llama3.2.gguf", \
    "--host", "0.0.0.0", \
    "--port", "8080", \
    "--n-gpu-layers", "99", \
    "--ctx-size", "8192", \
    "--threads", "8", \
    "--batch-size", "512", \
    "--parallel", "4", \
    "--mlock", \
    "--log-disable"]
