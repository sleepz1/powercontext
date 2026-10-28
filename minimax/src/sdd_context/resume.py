"""Restart boundary: only durable service configuration crosses stdin."""
import json
import os
import sys

from .config import Settings
from .powerctx import PowerContextClient


def main():
    payload = json.load(sys.stdin)
    client = PowerContextClient(Settings(powercontext_url=payload["url"], powercontext_scope_key=payload["scope_key"]))
    scope = client.ensure_scope()
    prepared = client.prepare("refund eligibility MiniMax AE-02 task state", max_bytes=6000)
    print(json.dumps({"scope_id": scope, "prepared": prepared, "pid": os.getpid()}))


if __name__ == "__main__":
    main()
