#!/usr/bin/env python3
"""
media_janitor.py — skyd module
Finds duplicate/bad media, deletes the junk copy, tells Radarr to grab better versions.

Bad file criteria:
  - < 1MB file
  - .iso, .wmv, .m2ts, .avi extensions
  - BR-DISK or _compressed in filename
  - Duplicate videos in same folder (keep largest/highest quality)

Quality rank: Remux > Bluray > WEBDL/WEBRip > HDTV > DVD > unknown
"""

import os, json, subprocess, logging
from pathlib import Path
from datetime import datetime

RADARR_URL  = os.environ.get("RADARR_URL", "http://172.22.0.1:7878")
RADARR_KEY  = os.environ.get("RADARR_KEY")
SONARR_URL  = os.environ.get("SONARR_URL", "http://172.22.0.1:8989")
SONARR_KEY  = os.environ.get("SONARR_KEY")
LOG_PATH    = "/var/log/skyd_janitor.log"
MEDIA_PATHS = ["/mnt/user/Data/Movies", "/mnt/user/Data/tvshows"]
STATE_PATH  = "/var/log/skyd_janitor_state.json"

VIDEO_EXTS = {'.mkv', '.mp4', '.avi', '.wmv', '.m2ts', '.mov', '.mpg', '.mpeg', '.flv', '.ts'}
BAD_EXTS   = {'.iso', '.wmv', '.avi', '.m2ts'}
BAD_NAMES  = ['br-disk', '_compressed', 'br_disk', 'brdisk']

QUALITY_RANK = {
    'remux': 100, 'bluray': 80, 'webdl': 60, 'webrip': 55,
    'hdtv': 40, 'dvd': 20, 'unknown': 5
}

logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format='%(asctime)s [JANITOR] %(message)s')
log = logging.getLogger('janitor')

def _curl(method, url, key, data=None):
    cmd = ['curl', '-s', '-X', method, url, '-H', f'X-Api-Key: {key}']
    if data:
        cmd += ['-H', 'Content-Type: application/json', '-d', json.dumps(data)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    try:
        return json.loads(r.stdout) if r.stdout.strip() else {}
    except:
        return {}

def radarr_movies():
    return _curl('GET', f'{RADARR_URL}/api/v3/movie', RADARR_KEY)

def radarr_delete_file(file_id):
    _curl('DELETE', f'{RADARR_URL}/api/v3/movieFile/{file_id}', RADARR_KEY)

def radarr_search(movie_id):
    _curl('POST', f'{RADARR_URL}/api/v3/command', RADARR_KEY,
          {"name": "MoviesSearch", "movieIds": [movie_id]})

def quality_score(filepath):
    name = filepath.lower()
    for q, score in sorted(QUALITY_RANK.items(), key=lambda x: -x[1]):
        if q in name:
            return score
    return QUALITY_RANK['unknown']

def is_bad_file(path):
    p = Path(path)
    name_lower = p.name.lower()
    try:
        size = p.stat().st_size
        if size < 1024 * 1024:
            return True, f"tiny ({size} bytes)"
    except:
        return True, "stat failed"
    if p.suffix.lower() in BAD_EXTS:
        return True, f"bad ext ({p.suffix})"
    for bad in BAD_NAMES:
        if bad in name_lower:
            return True, f"bad pattern ({bad})"
    return False, None

def find_duplicates(folder):
    videos = [f for f in Path(folder).iterdir()
              if f.is_file() and f.suffix.lower() in VIDEO_EXTS]
    if len(videos) <= 1:
        return []
    ranked = sorted(videos,
                    key=lambda f: (quality_score(str(f)), f.stat().st_size),
                    reverse=True)
    keeper = ranked[0]
    return [(str(d), str(keeper)) for d in ranked[1:]]

def load_state():
    try:
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH) as f:
                return json.load(f)
    except:
        pass
    return {"last_scan": {}}

def save_state(state):
    try:
        with open(STATE_PATH, 'w') as f:
            json.dump(state, f, indent=2)
    except:
        pass

def run_janitor():
    log.info("=== Media Janitor starting ===")
    report = {
        "timestamp": datetime.now().isoformat(),
        "bad_files_removed": [],
        "duplicates_removed": [],
        "radarr_searches_triggered": [],
        "errors": []
    }
    state = load_state()
    last_scan = state.get("last_scan", {})

    # Build Radarr path lookup
    try:
        movies = radarr_movies()
        radarr_by_path = {}
        for m in movies:
            if m.get('hasFile') and m.get('movieFile'):
                p = m['movieFile'].get('path', '')
                if p:
                    radarr_by_path[p] = m
        log.info(f"Radarr: {len(movies)} movies, {len(radarr_by_path)} with files")
    except Exception as e:
        log.error(f"Radarr load failed: {e}")
        radarr_by_path = {}

    searched = set()

    def radarr_path(disk_path):
        return disk_path.replace('/mnt/user/Data/Movies', '/media') \
                        .replace('/mnt/user/Data/tvshows', '/media/tv')

    def nuke_and_search(disk_path, label):
        rp = radarr_path(disk_path)
        movie = radarr_by_path.get(rp)
        try:
            if movie:
                radarr_delete_file(movie['movieFile']['id'])
                log.info(f"  Radarr-deleted: {movie['title']}")
            else:
                try:
                    os.remove(disk_path)
                except Exception as e:
                    logging.warning(f"os.remove failed for {disk_path}: {e}")
                log.info(f"  Direct-deleted: {disk_path}")
            if movie and movie['id'] not in searched:
                radarr_search(movie['id'])
                searched.add(movie['id'])
                report["radarr_searches_triggered"].append(movie['title'])
                log.info(f"  Search triggered: {movie['title']}")
        except Exception as e:
            log.error(f"  Failed {disk_path}: {e}")
            report["errors"].append(str(e))

    for media_root in MEDIA_PATHS:
        if not os.path.exists(media_root):
            log.warning(f"Path not found: {media_root}")
            continue
        log.info(f"Scanning {media_root}...")
        for root, dirs, files in os.walk(media_root):
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            cur_mtime = os.path.getmtime(root)
            saved_mtime = last_scan.get(root, 0)
            if cur_mtime <= saved_mtime:
                continue
            for fname in files:
                if Path(fname).suffix.lower() not in VIDEO_EXTS:
                    continue
                fpath = os.path.join(root, fname)
                bad, reason = is_bad_file(fpath)
                if bad:
                    log.info(f"BAD: {fname} — {reason}")
                    nuke_and_search(fpath, fname)
                    report["bad_files_removed"].append({"file": fname, "reason": reason})
            for dp, keeper in find_duplicates(root):
                log.info(f"DUPE: keeping {Path(keeper).name}, removing {Path(dp).name}")
                nuke_and_search(dp, Path(dp).name)
                report["duplicates_removed"].append({
                    "removed": Path(dp).name, "kept": Path(keeper).name
                })
            last_scan[root] = cur_mtime

    save_state({"last_scan": last_scan})

    with open('/var/log/skyd_janitor_last.json', 'w') as f:
        json.dump(report, f, indent=2)

    summary = (f"Janitor done — "
               f"{len(report['bad_files_removed'])} bad, "
               f"{len(report['duplicates_removed'])} dupes, "
               f"{len(report['radarr_searches_triggered'])} searches, "
               f"{len(report['errors'])} errors")
    log.info(summary)
    print(summary)
    return report

if __name__ == "__main__":
    run_janitor()