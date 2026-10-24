import json
import os
import urllib.parse
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, ".env")


def load_env(path):
    env = {}
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def kintone_request(base_url, token, params):
    url = base_url + "/app/form/fields.json"
    url += "?" + urllib.parse.urlencode(params, doseq=True)
    req = urllib.request.Request(url, headers={"X-Cybozu-API-Token": token}, method="GET")
    with urllib.request.urlopen(req) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body)


def main():
    env = load_env(ENV_PATH)
    subdomain = env.get("KINTONE_SUBDOMAIN")
    guest_space_id = env.get("KINTONE_GUEST_SPACE_ID")
    token = env.get("KINTONE_TOKEN_WORKERS")
    if not subdomain or not guest_space_id or not token:
        raise RuntimeError("KINTONE_SUBDOMAIN / KINTONE_GUEST_SPACE_ID / KINTONE_TOKEN_WORKERS are required.")

    base_url = f"https://{subdomain}.cybozu.com/k/guest/{guest_space_id}/v1"
    resp = kintone_request(base_url, token, {"app": 165})
    props = resp.get("properties", {})
    rows = []
    for code, meta in props.items():
        label = meta.get("label", "")
        ftype = meta.get("type", "")
        rows.append((label, code, ftype))
    rows.sort(key=lambda x: x[0])
    for label, code, ftype in rows:
        print(f"{label}\t{code}\t{ftype}")


if __name__ == "__main__":
    main()
