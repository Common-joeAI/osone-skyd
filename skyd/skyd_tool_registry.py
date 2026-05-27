import ast
import json
import os
import time
import inspect
from difflib import SequenceMatcher
from datetime import datetime

class ToolRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._metadata = {}
            cls._instance._init_registry()
        return cls._instance

    def _init_registry(self):
        pre_tools = [
            "plex_status", "plex_sessions", "radarr_queue",
            "sonarr_queue", "system_stats", "media_search", "hive_status"
        ]
        for name in pre_tools:
            def make_stub(n):
                def stub(*args, **kwargs):
                    mod = __import__("skyd_tools", fromlist=[n])
                    fn = getattr(mod, n)
                    return fn(*args, **kwargs)
                return stub
            self.register(name, make_stub(name), f"{name} stub", None)
        self._load_metadata()

    def _load_metadata(self):
        path = "/var/log/skyd_tool_registry.json"
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                    for item in data:
                        name = item.get("name")
                        if name in self._tools:
                            self._metadata[name] = item
            except Exception:
                pass
        for name in self._tools:
            if name not in self._metadata:
                self._metadata[name] = {
                    "name": name,
                    "description": self._tools[name]["description"],
                    "skylang_action": self._tools[name].get("skylang_action"),
                    "call_count": 0,
                    "last_called": None
                }

    def _persist_metadata(self):
        path = "/var/log/skyd_tool_registry.json"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = list(self._metadata.values())
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def register(self, name, fn, description, skylang_action=None):
        self._tools[name] = {
            "fn": fn,
            "description": description,
            "skylang_action": skylang_action
        }
        if name not in self._metadata:
            self._metadata[name] = {
                "name": name,
                "description": description,
                "skylang_action": skylang_action,
                "call_count": 0,
                "last_called": None
            }
        else:
            self._metadata[name]["description"] = description
            self._metadata[name]["skylang_action"] = skylang_action
        self._persist_metadata()

    def _fuzzy_score(self, a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def dispatch(self, intent_str):
        best_name = None
        best_score = 0.0
        best_matched = None
        for name, meta in self._tools.items():
            score_name = self._fuzzy_score(intent_str, name)
            score_desc = self._fuzzy_score(intent_str, meta["description"])
            score = max(score_name, score_desc)
            if score > best_score:
                best_score = score
                best_name = name
                best_matched = name if score_name >= score_desc else meta["description"]
        if best_name is None or best_score < 0.3:
            return {"tool": None, "result": None, "matched": None}
        fn = self._tools[best_name]["fn"]
        result = fn()
        self._metadata[best_name]["call_count"] += 1
        self._metadata[best_name]["last_called"] = datetime.utcnow().isoformat()
        self._persist_metadata()
        return {"tool": best_name, "result": result, "matched": best_matched}

    def propose_new_tool(self, name, code_str, description):
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return {"ok": False, "name": name, "reason": f"SyntaxError: {e}"}

        banned = {"os.system", "subprocess", "__import__", "open"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    full = f"{node.func.value.id}.{node.func.attr}" if isinstance(node.func.value, ast.Name) else ""
                    if full in banned or node.func.attr in banned:
                        return {"ok": False, "name": name, "reason": f"Banned call: {full or node.func.attr}"}
                elif isinstance(node.func, ast.Name) and node.func.id in banned:
                    return {"ok": False, "name": name, "reason": f"Banned call: {node.func.id}"}
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
                if node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
                        if not arg0.value.startswith("/var/log"):
                            return {"ok": False, "name": name, "reason": "open outside /var/log"}

        try:
            ns = {"__builtins__": {"len": len, "str": str, "int": int, "dict": dict, "list": list}}
            exec(code_str, ns)
            if name not in ns or not callable(ns[name]):
                return {"ok": False, "name": name, "reason": "Callable not found after exec"}
            fn = ns[name]
            self.register(name, fn, description, None)
            path = "/var/log/skyd_new_tools.py"
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a") as f:
                f.write(f"\n# {datetime.utcnow().isoformat()}\n")
                f.write(code_str)
                f.write("\n")
            return {"ok": True, "name": name, "reason": "registered"}
        except Exception as e:
            return {"ok": False, "name": name, "reason": str(e)}

    def get_registry_snapshot(self):
        snap = []
        for name, meta in self._metadata.items():
            snap.append({
                "name": name,
                "description": meta.get("description"),
                "skylang_action": meta.get("skylang_action"),
                "call_count": meta.get("call_count", 0),
                "last_called": meta.get("last_called")
            })
        return snap