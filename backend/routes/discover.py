from fastapi import APIRouter
from typing import Dict, Any
import os

try:
    import boto3  # type: ignore
except Exception:
    boto3 = None  # type: ignore

router = APIRouter(tags=["discover"])

@router.get("/discover")
def discover() -> Dict[str, Any]:
    from backend.main import get_base_root, get_data_dir
    base_root = get_base_root()
    items: Dict[str, Any] = {
        "root": base_root,
        "exists": os.path.isdir(base_root),
        "data_dirs": [],
        "files": [],
    }
    if not os.path.isdir(base_root):
        return items
    for name in os.listdir(base_root):
        path = os.path.join(base_root, name)
        if os.path.isfile(path) and (name.endswith(".py") or name.endswith(".txt")):
            items["files"].append(name)
    data_dir = get_data_dir()
    bucket = os.getenv("S3_BUCKET")
    prefix = (os.getenv("S3_PREFIX") or "data").strip("/")
    if bucket and boto3 is not None:
        s3 = boto3.client("s3")
        try:
            resp = s3.list_objects_v2(Bucket=bucket, Prefix=f"{prefix}/", Delimiter="/")
            for item in resp.get("CommonPrefixes", []):
                name = item.get("Prefix", "").replace(f"{prefix}/", "").strip("/")
                if not name:
                    continue
                matches_key = f"{prefix}/{name}/matches.csv"
                try:
                    s3.head_object(Bucket=bucket, Key=matches_key)
                    items["data_dirs"].append({ "league": name, "present": ["matches.csv"], "source": "s3" })
                except Exception:
                    continue
        except Exception:
            pass
    if os.path.isdir(data_dir):
        for league in os.listdir(data_dir):
            ldir = os.path.join(data_dir, league)
            if os.path.isdir(ldir):
                present = []
                for fname in ("matches.csv", "teams.csv", "teams2.csv", "league.csv", "players.csv"):
                    if os.path.exists(os.path.join(ldir, fname)):
                        present.append(fname)
                items["data_dirs"].append({ "league": league, "present": present, "source": "local" })
    return items
