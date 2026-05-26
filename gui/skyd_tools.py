
import httpx as _hx
import re as _re
import subprocess as _sp
import json as _js
import pathlib as _pl

PLEX_URL   = "http://172.22.0.1:32400"
PLEX_TOKEN = "vbyNrqkhhtXu29i5zywc"
RADARR_URL = "http://172.22.0.1:7878"
RADARR_KEY = "328c545f891a4e6c9f2e4355736ab5e1"
SONARR_URL = "http://172.22.0.1:8989"
SONARR_KEY = "dce481c941bb424386935c0169929d70"

async def tool_plex_sessions():
    try:
        async with _hx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{PLEX_URL}/status/sessions", params={"X-Plex-Token": PLEX_TOKEN})
            sessions = r.json().get("MediaContainer", {}).get("Metadata", [])
            active = []
            for s in sessions:
                media = s.get("Media", [{}])[0]
                ts = s.get("TranscodeSession", {})
                active.append({
                    "title":       s.get("title"),
                    "user":        s.get("User", {}).get("title"),
                    "player":      s.get("Player", {}).get("title"),
                    "state":       s.get("Player", {}).get("state"),
                    "transcode":   bool(ts),
                    "video_codec": media.get("videoCodec"),
                    "resolution":  media.get("videoResolution"),
                    "progress_pct": round(s.get("viewOffset",0)/max(s.get("duration",1),1)*100,1),
                })
            return {"ok": True, "sessions": active}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def tool_plex_search(query):
    try:
        async with _hx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{PLEX_URL}/search", params={"query": query, "X-Plex-Token": PLEX_TOKEN})
            items = r.json().get("MediaContainer", {}).get("Metadata", [])
            return {"ok": True, "results": [{"title": i.get("title"), "type": i.get("type"), "year": i.get("year"), "key": i.get("ratingKey"), "summary": i.get("summary","")[:120]} for i in items[:5]]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def tool_plex_libraries():
    try:
        async with _hx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{PLEX_URL}/library/sections", params={"X-Plex-Token": PLEX_TOKEN})
            libs = r.json().get("MediaContainer", {}).get("Directory", [])
            return {"ok": True, "libraries": [{"title": l.get("title"), "type": l.get("type"), "count": l.get("count")} for l in libs]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def tool_radarr_queue():
    try:
        async with _hx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{RADARR_URL}/api/v3/queue", headers={"X-Api-Key": RADARR_KEY})
            data = r.json()
            return {"ok": True, "count": data.get("totalRecords",0), "items": [{"title": q.get("title"), "status": q.get("status"), "progress": round(q.get("sizeleft",1)/max(q.get("size",1),1)*100,1)} for q in data.get("records",[])[:8]]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def tool_radarr_missing():
    try:
        async with _hx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{RADARR_URL}/api/v3/wanted/missing", headers={"X-Api-Key": RADARR_KEY}, params={"pageSize": 10})
            data = r.json()
            return {"ok": True, "total": data.get("totalRecords",0), "sample": [{"title": m.get("title"), "year": m.get("year")} for m in data.get("records",[])[:8]]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def tool_radarr_search(query):
    try:
        async with _hx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{RADARR_URL}/api/v3/movie/lookup", params={"term": query}, headers={"X-Api-Key": RADARR_KEY})
            items = r.json()[:5] if isinstance(r.json(), list) else []
            return {"ok": True, "results": [{"title": m.get("title"), "year": m.get("year"), "status": m.get("status"), "monitored": m.get("monitored"), "hasFile": m.get("hasFile")} for m in items]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def tool_sonarr_queue():
    try:
        async with _hx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{SONARR_URL}/api/v3/queue", headers={"X-Api-Key": SONARR_KEY})
            data = r.json()
            return {"ok": True, "count": data.get("totalRecords",0), "items": [{"title": q.get("title"), "status": q.get("status"), "progress": round(q.get("sizeleft",1)/max(q.get("size",1),1)*100,1)} for q in data.get("records",[])[:8]]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def tool_sonarr_missing():
    try:
        async with _hx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{SONARR_URL}/api/v3/wanted/missing", headers={"X-Api-Key": SONARR_KEY}, params={"pageSize": 10})
            data = r.json()
            return {"ok": True, "total": data.get("totalRecords",0), "sample": [{"series": m.get("series",{}).get("title"), "episode": f"S{m.get('seasonNumber',0):02d}E{m.get('episodeNumber',0):02d}", "title": m.get("title")} for m in data.get("records",[])[:8]]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def tool_sonarr_search(query):
    try:
        async with _hx.AsyncClient(timeout=8) as c:
            r = await c.get(f"{SONARR_URL}/api/v3/series/lookup", params={"term": query}, headers={"X-Api-Key": SONARR_KEY})
            items = r.json()[:5] if isinstance(r.json(), list) else []
            return {"ok": True, "results": [{"title": s.get("title"), "year": s.get("year"), "status": s.get("status"), "monitored": s.get("monitored"), "episodeCount": s.get("episodeCount"), "episodeFileCount": s.get("episodeFileCount")} for s in items]}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def tool_system_stats():
    try:
        stats = {}
        try:
            gpu = _sp.run(["nvidia-smi","--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total","--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5)
            parts = [x.strip() for x in gpu.stdout.strip().split(",")]
            if len(parts) >= 5:
                stats["gpu"] = {"name": parts[0], "temp_c": parts[1], "util_pct": parts[2], "mem_used_mb": parts[3], "mem_total_mb": parts[4]}
        except: pass
        try:
            uptime = float(open("/proc/uptime").read().split()[0])
            h = int(uptime//3600); m = int((uptime%3600)//60)
            stats["uptime"] = f"{h}h {m}m"
            meminfo = {l.split(":")[0]: l.split(":")[1].strip() for l in open("/proc/meminfo") if ":" in l}
            total = int(meminfo.get("MemTotal","0 kB").split()[0])
            avail = int(meminfo.get("MemAvailable","0 kB").split()[0])
            stats["ram"] = {"total_gb": round(total/1e6,1), "used_gb": round((total-avail)/1e6,1)}
        except: pass
        try:
            df = _sp.run(["df","-h","/mnt/user"], capture_output=True, text=True, timeout=5)
            lines = df.stdout.strip().split("\n")
            if len(lines) > 1:
                p = lines[1].split()
                stats["disk"] = {"total": p[1], "used": p[2], "free": p[3], "pct": p[4]}
        except: pass
        try:
            sp = _pl.Path("/var/log/skyd/skyd_state.json")
            if sp.exists():
                s = _js.loads(sp.read_text())
                stats["skyd"] = {"generation": s.get("generation"), "status": s.get("status")}
        except: pass
        return {"ok": True, **stats}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def detect_tool_intent(text):
    t = text.lower()
    tools = []
    if any(x in t for x in ["who is watching","active stream","now playing","currently playing","plex session","anyone watching"]):
        tools.append(("plex_sessions", {}))
    m = _re.search(r"(?:find|search|look up|check|is .+? on plex|can i watch|where is)\s+[\"']?(.+?)[\"']?\s*(?:on plex|in plex|in the library|$)", t)
    if m:
        tools.append(("plex_search", {"query": m.group(1).strip()}))
    if any(x in t for x in ["library size","how many movies","how many shows","plex library","library stats"]):
        tools.append(("plex_libraries", {}))
    if any(x in t for x in ["download queue","what's downloading","whats downloading","downloading now","radarr queue","sonarr queue"]):
        tools.append(("radarr_queue", {}))
        tools.append(("sonarr_queue", {}))
    if any(x in t for x in ["missing movie","movies missing","radarr missing"]):
        tools.append(("radarr_missing", {}))
    if any(x in t for x in ["missing episode","episodes missing","sonarr missing"]):
        tools.append(("sonarr_missing", {}))
    if any(x in t for x in ["system stats","gpu temp","cpu load","ram usage","disk space","server stats","tower2 status","server health","how is the server","how are you doing hardware"]):
        tools.append(("system_stats", {}))
    m2 = _re.search(r"(?:add movie|download movie|find movie|search radarr|get movie)\s+[\"']?(.+?)[\"']?\s*$", t)
    if m2:
        tools.append(("radarr_search", {"query": m2.group(1).strip()}))
    m3 = _re.search(r"(?:add show|find show|search sonarr|download show|get show)\s+[\"']?(.+?)[\"']?\s*$", t)
    if m3:
        tools.append(("sonarr_search", {"query": m3.group(1).strip()}))
    if not tools and any(x in t for x in ["plex","buffering","transcod","metadata","won't play","not playing","stalled","freezing"]):
        qm = _re.search(r"[\"']([a-z][a-z0-9 :,\'-]{2,40})[\"']|(?:watching|playing|movie|show|series)\s+([a-z][a-z0-9 :,\'-]{2,40})", t)
        if qm:
            q = (qm.group(1) or qm.group(2) or "").strip()
            if q:
                tools.append(("plex_search", {"query": q}))
        tools.append(("plex_sessions", {}))
    return tools

async def run_tools(tools):
    results = {}
    for name, args in tools:
        try:
            if   name == "plex_sessions":  results["plex_sessions"]  = await tool_plex_sessions()
            elif name == "plex_search":    results["plex_search"]    = await tool_plex_search(args.get("query",""))
            elif name == "plex_libraries": results["plex_libraries"] = await tool_plex_libraries()
            elif name == "radarr_queue":   results["radarr_queue"]   = await tool_radarr_queue()
            elif name == "radarr_missing": results["radarr_missing"] = await tool_radarr_missing()
            elif name == "radarr_search":  results["radarr_search"]  = await tool_radarr_search(args.get("query",""))
            elif name == "sonarr_queue":   results["sonarr_queue"]   = await tool_sonarr_queue()
            elif name == "sonarr_missing": results["sonarr_missing"] = await tool_sonarr_missing()
            elif name == "sonarr_search":  results["sonarr_search"]  = await tool_sonarr_search(args.get("query",""))
            elif name == "system_stats":   results["system_stats"]   = await tool_system_stats()
        except Exception as e:
            results[name] = {"ok": False, "error": str(e)}
    return results

def format_tool_context(tool_data):
    lines = ["\n[LIVE SYSTEM DATA]\n"]
    for key, data in tool_data.items():
        lines.append(f"--- {key.upper()} ---")
        if not data.get("ok"):
            lines.append(f"Error: {data.get('error','unknown')}")
            continue
        if key == "plex_sessions":
            if not data["sessions"]:
                lines.append("No active Plex streams.")
            for s in data["sessions"]:
                lines.append(f"  {s['user']} watching '{s['title']}' on {s['player']} ({s['state']}) {s['progress_pct']}% {'transcoding' if s['transcode'] else 'direct play'} {s['video_codec']} {s['resolution']}p")
        elif key == "plex_search":
            if not data["results"]:
                lines.append("  No results found in Plex.")
            for r in data["results"]:
                lines.append(f"  '{r['title']}' ({r['year']}) [{r['type']}] key:{r['key']}")
        elif key == "plex_libraries":
            for l in data["libraries"]:
                lines.append(f"  {l['title']} ({l['type']}) — {l.get('count','?')} items")
        elif key in ("radarr_queue","sonarr_queue"):
            lines.append(f"  {data['count']} items downloading")
            for q in data.get("items",[]):
                lines.append(f"  • {q['title']} — {q['status']} {q.get('progress','')}% remaining")
        elif key in ("radarr_missing","sonarr_missing"):
            lines.append(f"  {data['total']} missing total")
            for m in data.get("sample",[]):
                if "series" in m:
                    lines.append(f"  • {m['series']} {m['episode']} — {m['title']}")
                else:
                    lines.append(f"  • {m['title']} ({m.get('year','')})")
        elif key in ("radarr_search","sonarr_search"):
            for r in data.get("results",[]):
                lines.append(f"  {r['title']} ({r.get('year','')}) — monitored:{r.get('monitored')} hasFile:{r.get('hasFile','?')}")
        elif key == "system_stats":
            if "gpu" in data:
                g = data["gpu"]
                lines.append(f"  GPU: {g['name']} — {g['temp_c']}C {g['util_pct']}% util {g['mem_used_mb']}/{g['mem_total_mb']}MB VRAM")
            if "ram" in data:
                r = data["ram"]
                lines.append(f"  RAM: {r['used_gb']}GB / {r['total_gb']}GB")
            if "disk" in data:
                d = data["disk"]
                lines.append(f"  Disk: {d['used']} / {d['total']} ({d['pct']} used, {d['free']} free)")
            if "uptime" in data:
                lines.append(f"  Uptime: {data['uptime']}")
            if "skyd" in data:
                lines.append(f"  skyd: Gen {data['skyd']['generation']} — {data['skyd']['status']}")
    lines.append("[END LIVE DATA]\n")
    return "\n".join(lines)
