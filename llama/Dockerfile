# Use pre-built llama.cpp server with CUDA — pinned to latest known good tag
# Full tag list: https://github.com/ggerganov/llama.cpp/pkgs/container/llama.cpp
FROM ghcr.io/ggerganov/llama.cpp:server-cuda-b4719

# Model mounted from Unraid: /mnt/user/osone/models/llama3.2.gguf -> /models/llama3.2.gguf
CMD ["-m", "/models/llama3.2.gguf", \
    "--host", "0.0.0.0", \
    "--port", "8080", \
    "--n-gpu-layers", "99", \
    "--ctx-size", "8192", \
    "--threads", "8", \
    "--batch-size", "512", \
    "--parallel", "4", \
    "--log-disable"]
