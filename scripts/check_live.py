"""Exercise the selected private provider with isolated clients. Print only test outcomes."""

import argparse
import os
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from iteraconnect.diagnostics import probe
from iteraconnect.gateway import Gateway
from iteraconnect.settings import read_settings, runtime_config
from iteraconnect.smoke import smoke


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--clients", nargs="+", choices=("claude", "codex", "openclaw", "hermes"))
    parser.add_argument("--protocols", nargs="+", choices=("chat", "responses", "anthropic"))
    args = parser.parse_args()
    if not args.clients and not args.protocols:
        parser.error("select clients or protocols to test")
    if not args.settings.is_file():
        parser.error("supply an existing private test settings file")
    data = read_settings(args.settings)
    pid = data["selected_provider"]
    if not data["providers"][pid]["api_key"]:
        parser.error("the selected provider requires a dedicated test key")
    passed = True
    with tempfile.TemporaryDirectory() as state, patch.dict(os.environ, ITERACONNECT_HOME=state):
        config = runtime_config(data)
        with Gateway(config, address=("127.0.0.1", 0)) as relay:
            config["gateway"]["port"] = relay.server_port
            worker = threading.Thread(target=relay.serve_forever, daemon=True)
            worker.start()
            try:
                if args.protocols:
                    report = probe(config, pid, protocols=args.protocols)
                    for row in report["results"]:
                        print(
                            row["protocol"], row["case"], row["status"], row["seconds"], flush=True
                        )
                    passed &= report["passed"]
                for client in args.clients or []:
                    row = smoke(config, client, pid, native=True)
                    print(client, row["status"], row.get("seconds", "-"), flush=True)
                    passed &= row["status"] == "passed"
            finally:
                relay.shutdown()
                worker.join()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
