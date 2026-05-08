"""
OSONE Hive Commander — skyd's distributed compute layer
Manages underling agents across the Tailscale mesh
"""
import json, os, time, threading, requests
from datetime import datetime

REGISTRY_PATH = "/var/log/skyd_hive.json"

class HiveCommander:
    def __init__(self):
        self.underlings = {}  # {node_id: {ip, name, capabilities, load, last_seen}}
        self.task_queue = []
        self.results = {}
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            with open(REGISTRY_PATH) as f:
                data = json.load(f)
                self.underlings = data.get("underlings", {})
        except: pass

    def _save(self):
        with open(REGISTRY_PATH, "w") as f:
            json.dump({"underlings": self.underlings, "updated": datetime.now().isoformat()}, f, indent=2)

    def register(self, node_id, ip, name, capabilities, cpu_cores, ram_gb):
        with self._lock:
            self.underlings[node_id] = {
                "id": node_id,
                "ip": ip,
                "name": name,
                "capabilities": capabilities,
                "cpu_cores": cpu_cores,
                "ram_gb": ram_gb,
                "load": 0.0,
                "status": "idle",
                "last_seen": datetime.now().isoformat(),
                "tasks_completed": self.underlings.get(node_id, {}).get("tasks_completed", 0),
                "registered_at": self.underlings.get(node_id, {}).get("registered_at", datetime.now().isoformat())
            }
            self._save()
            print(f"[HIVE] Underling registered: {name} ({node_id}) @ {ip}")
            return {"status": "registered", "commander": "osone"}

    def heartbeat(self, node_id, load, status):
        with self._lock:
            if node_id in self.underlings:
                self.underlings[node_id]["last_seen"] = datetime.now().isoformat()
                self.underlings[node_id]["load"] = load
                self.underlings[node_id]["status"] = status
                self._save()

    def get_active(self):
        now = time.time()
        active = {}
        for nid, node in self.underlings.items():
            try:
                last = datetime.fromisoformat(node["last_seen"]).timestamp()
                if now - last < 60:  # alive if seen in last 60s
                    active[nid] = node
            except: pass
        return active

    def pick_best(self, capability=None):
        active = self.get_active()
        candidates = [n for n in active.values()
                      if capability is None or capability in n.get("capabilities", [])]
        if not candidates: return None
        return min(candidates, key=lambda n: n["load"])

    def dispatch(self, task_type, payload, capability=None):
        node = self.pick_best(capability)
        if not node:
            return {"error": "no underlings available", "task": task_type}
        try:
            r = requests.post(f"http://{node['ip']}:7777/task",
                json={"type": task_type, "payload": payload},
                timeout=30)
            result = r.json()
            with self._lock:
                self.underlings[node["id"]]["tasks_completed"] =                     self.underlings[node["id"]].get("tasks_completed", 0) + 1
                self._save()
            print(f"[HIVE] Task '{task_type}' dispatched to {node['name']} → {result.get('status','?')}")
            return result
        except Exception as e:
            return {"error": str(e), "node": node["name"]}

    def broadcast(self, task_type, payload):
        active = self.get_active()
        results = {}
        for nid, node in active.items():
            try:
                r = requests.post(f"http://{node['ip']}:7777/task",
                    json={"type": task_type, "payload": payload}, timeout=30)
                results[node["name"]] = r.json()
            except Exception as e:
                results[node["name"]] = {"error": str(e)}
        return results

    def summary(self):
        active = self.get_active()
        return {
            "total": len(self.underlings),
            "active": len(active),
            "nodes": [{
                "name": n["name"], "ip": n["ip"],
                "load": n["load"], "status": n["status"],
                "tasks_completed": n.get("tasks_completed", 0),
                "capabilities": n.get("capabilities", [])
            } for n in active.values()]
        }

# Global instance
hive = HiveCommander()
