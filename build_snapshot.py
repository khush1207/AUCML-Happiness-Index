"""
Builds data/snapshot.pkl.gz (the precomputed predictions and history).

Run from the project root, in your .venv, AFTER running patch_main.py:
    python build_snapshot.py
It needs the full dataset and a few GB of RAM, so run it on your laptop,
not on Vercel. Commit the resulting file to git.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src import main  # noqa: E402

snap = main._slim_snapshot(main._build_snapshot())
snap.pop("model", None)       # rebuilt at startup, not stored
snap.pop("explainer", None)

out = main.SNAPSHOT_FILE
out.parent.mkdir(parents=True, exist_ok=True)
pd.to_pickle(snap, out)

print(f"Saved {out}  ({out.stat().st_size / 1e6:.1f} MB)")
print(f"Employees: {len(snap['employees'])}, companies: {len(snap['companies'])}, "
      f"history rows: {len(snap['history'])}")
