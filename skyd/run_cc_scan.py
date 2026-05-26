#!/usr/bin/env python3
import sys, logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
from plex_cc_trainer import run_cc_trainer
result = run_cc_trainer()
import json
open("/var/log/skyd_cc_done.json","w").write(json.dumps(result or {}))
print("DONE:", result)
