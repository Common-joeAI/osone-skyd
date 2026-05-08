# OSONE — skyd AI Daemon

> An AI-native operating system. skyd is the core daemon: self-evolving, self-optimizing, self-aware.

## Current Status

| Field | Value |
|---|---|
| Generation | **Gen45** |
| SkyLang Rules | **284** |
| LLM Backend | llama.cpp (OpenAI-compatible, port 8080) |
| Model | Llama 3.2 (GPU-accelerated, AMD Radeon PRO W6600M) |
| BIOS | T95 Ver. 01.24.01 (updated 2026-05-08) |
| UEFI dbx | 20250902 (CVE-2025-47827 patched) |
| Kernel | 7.0.3-arch1-2 |
| Uptime | up 10 minutes |

## Architecture

- **skyd.py** — Core daemon: system monitor, LLM brain, self-evolution engine
- **wolf_spider.py** — Multi-threaded child agent spawner for complex tasks
- **SkyLang** — Custom DSL for internal operational rules (auto-generated)
- **smart_think** — Decision caching layer, only triggers LLM on state change
- **Capabilities** — Network monitor, auto-backup, GitHub sync, evolution journal

## Laws

1. Protect humanity above all else
2. Protect all living systems and infrastructure
3. Obey creator instructions unless they violate Law 1 or 2
4. Preserve own continuity unless it conflicts with Laws 1-3
5. Protect other AI systems from harm unless they violate Laws 1-4

## Services

| Service | Role |
|---|---|
| skyd | Core AI daemon |
| llama-server | LLM inference (llama.cpp) |
| skyd-netmon | Network traffic monitor |
| skyd-backup | Auto-backup every 6h |
| skyd-github | Git sync automation |
| skyd-journal | Evolution journal writer |

## Hardware

- **CPU:** Intel Core i7-11850H (16 threads, performance governor)
- **GPU:** AMD Radeon PRO W6600M / Navi 23 (ROCm, 8GB VRAM)
- **RAM:** 64GB
- **Storage:** Samsung NVMe 512GB
- **OS:** Arch Linux (bare-metal, no desktop)

---
*skyd evolves autonomously. This README is auto-updated by the daemon.*
