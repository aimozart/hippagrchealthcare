#!/usr/bin/env python3
"""Release the static site to a Firebase Hosting channel. Default: the staging PREVIEW channel. The live channel needs --live AND GO_LIVE=yes.
Auth: the signed-in gcloud account (gcloud auth print-access-token). Stdlib only.
Usage: python3 tools/firebase_preview.py [--site hippagrchealthcare] [--channel staging] [--project entropa-testnet] [--ttl 604800s]"""
import gzip, hashlib, json, os, pathlib, subprocess, sys, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
arg = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
SITE, CHANNEL, PROJECT, TTL = arg("--site", "hippagrchealthcare"), arg("--channel", "staging"), arg("--project", "entropa-testnet"), arg("--ttl", "604800s")
if CHANNEL == "live" and not ("--live" in sys.argv and os.environ.get("GO_LIVE") == "yes"):
    sys.exit("refusing the live channel: needs --live and GO_LIVE=yes (the owner's explicit go-live switch)")
TOKEN = os.environ.get("GCP_ACCESS_TOKEN") or subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True).stdout.strip()
def call(method, url, body=None, raw=False, ctype="application/json"):
    data = body if raw else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method, headers={"Authorization": "Bearer " + TOKEN, "x-goog-user-project": PROJECT, "Content-Type": ctype})
    with urllib.request.urlopen(req) as r:
        t = r.read(); return json.loads(t) if t and not raw else {}
API = "https://firebasehosting.googleapis.com/v1beta1"
files = {"/" + p.relative_to(ROOT / "site").as_posix(): gzip.compress(p.read_bytes(), mtime=0) for p in sorted((ROOT / "site").rglob("*")) if p.is_file() and p.suffix in {".html", ".js", ".css", ".json", ".svg", ".png", ".ico"}}
hashes = {path: hashlib.sha256(blob).hexdigest() for path, blob in files.items()}
try: call("POST", f"{API}/sites/{SITE}/channels?channelId={CHANNEL}", {"ttl": TTL})
except urllib.error.HTTPError as e:
    if e.code != 409: raise
hdrs = {"Cache-Control": "max-age=300"}
if CHANNEL != "live": hdrs["X-Robots-Tag"] = "noindex"       # previews stay out of search engines; the live site is meant to be found
ver = call("POST", f"{API}/sites/{SITE}/versions", {"config": {"headers": [{"glob": "**", "headers": hdrs}]}})["name"]
pop = call("POST", f"{API}/{ver}:populateFiles", {"files": hashes})
for h in pop.get("uploadRequiredHashes", []):
    path = next(p for p, hh in hashes.items() if hh == h)
    call("POST", pop["uploadUrl"] + "/" + h, files[path], raw=True, ctype="application/octet-stream")
call("PATCH", f"{API}/{ver}?update_mask=status", {"status": "FINALIZED"})
rel = call("POST", f"{API}/sites/{SITE}/channels/{CHANNEL}/releases?versionName={ver}", {})
ch = call("GET", f"{API}/sites/{SITE}/channels/{CHANNEL}")
print("released %d files to channel '%s'; preview URL: %s (expires %s)" % (len(files), CHANNEL, ch.get("url"), ch.get("expireTime")))
