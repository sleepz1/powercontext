"""Wait for real MySQL-protocol seekdb and the PowerContext HTTP server."""
import json
import os
import time
from pathlib import Path

from sdd_context.config import get_settings
from sdd_context.db import SeekDB
from sdd_context.powerctx import PowerContextClient

settings = get_settings()
for attempt in range(90):
    try:
        # Database may not exist yet: init_schema also proves DDL works.
        db = SeekDB(settings)
        db.init_schema()
        with db.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION() AS version, @@version_comment AS product")
                identity = cur.fetchone()
        PowerContextClient(settings).health()
        path = settings.evidence_root / "db/server_identity.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(identity, indent=2))
        print(f"Real services ready: {identity}")
        break
    except Exception as exc:
        if attempt == 89:
            raise RuntimeError("Services did not become ready within 180 seconds") from exc
        time.sleep(2)
