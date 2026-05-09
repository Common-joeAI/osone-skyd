# Use the official pre-built llama.cpp image with CUDA support
# No compilation needed — libcuda.so is only available at runtime anyway
FROM ghcr.io/ggerganov/llama.cpp:server-cuda

# Model is mounted from Unraid at /models/llama3.2.gguf
CMD ["-m", "/models/llama3.2.gguf", \
    "--host", "0.0.0.0", \
    "--port", "8080", \
    "--n-gpu-layers", "99", \
    "--ctx-size", "8192", \
    "--threads", "8", \
    "--batch-size", "512", \
    "--parallel", "4", \
    "--log-disable"]
