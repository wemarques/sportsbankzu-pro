from fastapi import APIRouter
from typing import Dict, Any
import os

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
    if os.path.isdir(data_dir):
        for league in os.listdir(data_dir):
            ldir = os.path.join(data_dir, league)
            if os.path.isdir(ldir):
                present = []
                for fname in ("matches.csv", "teams.csv", "teams2.csv", "league.csv", "players.csv"):
                    if os.path.exists(os.path.join(ldir, fname)):
                        present.append(fname)
                items["data_dirs"].append({ "league": league, "present": present })
    return items
