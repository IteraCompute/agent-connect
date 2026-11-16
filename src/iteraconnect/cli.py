"""Public CLI. Defaults are useful without modifying any native agent config."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from . import __version__
from .config import ConnectError, api_key, gateway_key, gateway_url, load, private_write, save
from .diagnostics import probe
from .gateway import Gateway, provider_models
from .integrations import (
    cc_link,
    connect,
    install_magpie,
    magpie,
    magpie_bin,
    sync_magpie,
    write_export,
)
from .launch import launch
from .network import json_request
from .smoke import smoke


def parser():
    p = argparse.ArgumentParser(
        prog="itera-connect", description="IteraCompute + CC Switch + Magpie"
    )
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument(
        "--config", type=Path, help="Agent Connect config.json; credentials are env references"
    )
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Write the default IteraCompute profile if no config exists")
    providers = sub.add_parser("provider", help="Choose IteraCompute or any other API provider")
    actions = providers.add_subparsers(dest="action", required=True)
    actions.add_parser("list")
    use = actions.add_parser("use")
    use.add_argument("id")
    add = actions.add_parser("add")
    add.add_argument("id")
    add.add_argument("--name")
    add.add_argument("--key-env", required=True)
    add.add_argument("--model", required=True)
    for kind in ("chat", "responses", "anthropic", "gemini"):
        add.add_argument("--" + kind, help="Native protocol base URL")
    add.add_argument(
        "--allow-http", action="store_true", help="Allow HTTP for a trusted LAN endpoint"
    )
    for command in ("serve", "up"):
        server = sub.add_parser(
            command,
            help="Serve the loopback relay"
            if command == "serve"
            else "Start the relay and Magpie together; sync providers first",
        )
        if command == "up":
            server.add_argument(
                "--web", action="store_true", help="Serve Magpie's management UI too"
            )
    sub.add_parser("install-magpie", help="Download the pinned, SHA-256 verified Magpie CLI")
    sub.add_parser("sync", help="Add/update these relay providers in Magpie; relay must be running")
    models = sub.add_parser("models", help="Fetch the provider's current catalog")
    models.add_argument("--provider")
    con = sub.add_parser(
        "connect", help="Use Magpie's native adapter to connect an installed agent"
    )
    con.add_argument("target")
    con.add_argument("--provider")
    con.add_argument("--model")
    dis = sub.add_parser("disconnect", help="Use Magpie to restore an agent's previous provider")
    dis.add_argument("target")
    link = sub.add_parser(
        "cc-link", help="Create a CC Switch provider import with a local-only key"
    )
    link.add_argument("target")
    link.add_argument("--provider")
    link.add_argument("--model")
    link.add_argument(
        "--api-format", choices=("openai_chat", "openai_responses", "anthropic", "gemini_native")
    )
    link.add_argument("--via", choices=("gateway", "magpie"), default="gateway")
    export = sub.add_parser("export", help="Write a private, standalone native config fragment")
    export.add_argument(
        "target", choices=("claude", "codex", "workbuddy", "workbuddy-ai", "openclaw", "hermes")
    )
    export.add_argument("--provider")
    export.add_argument("--model")
    export.add_argument("--out", type=Path, required=True)
    runner = sub.add_parser(
        "run", help="Launch Claude Code or Codex with process-local API settings"
    )
    runner.add_argument("target", choices=("claude", "codex"))
    runner.add_argument("--provider")
    runner.add_argument("--model")
    runner.add_argument("--via", choices=("gateway", "magpie", "direct"), default="gateway")
    for command in ("probe", "smoke"):
        test = sub.add_parser(
            command,
            help="Test API contracts"
            if command == "probe"
            else "Test installed native clients in a temporary HOME",
        )
        if command == "smoke":
            test.add_argument(
                "targets", nargs="*", default=["claude", "codex", "openclaw", "workbuddy", "hermes"]
            )
        test.add_argument("--provider")
        test.add_argument("--model")
        test.add_argument("--via", choices=("gateway", "magpie", "direct"), default="gateway")
        test.add_argument("--out", type=Path)
        if command == "probe":
            test.add_argument(
                "--protocol", action="append", choices=("chat", "responses", "anthropic")
            )
            test.add_argument("--budget", type=int, default=256)
            test.add_argument("--no-tools", action="store_true")
        else:
            test.add_argument("--timeout", type=int, default=90)
    sub.add_parser("doctor", help="Report missing keys, clients and gateway; never display keys")
    for command in ("magpie", "cc-switch"):
        sub.add_parser(command, help="Pass all following arguments to the upstream program")
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    trailing = []
    if "--" in argv:
        index = argv.index("--")
        argv, trailing = argv[:index], argv[index + 1 :]
    p = parser()
    args = p.parse_args(argv)
    if trailing and args.command not in ("run", "magpie", "cc-switch"):
        p.error("Arguments after -- are accepted only for run, magpie and cc-switch")
    try:
        return dispatch(args, trailing)
    except (ConnectError, OSError) as e:
        # OSError filenames may come from native tools: keep OS errors generic.
        message = (
            str(e) if isinstance(e, ConnectError) else "Local file or process operation failed"
        )
        print("itera-connect: " + message, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


def output(value, path=None):
    text = json.dumps(value, indent=2) + "\n"
    if path:
        private_write(path, text)
    print(text, end="")


def dispatch(args, trailing):
    config = load(args.config)
    command = args.command
    pid = getattr(args, "provider", None) or config["active_provider"]
    if pid not in config["providers"]:
        raise ConnectError("Unknown provider")
    vendor_env_names = [p["key_env"] for p in config["providers"].values()]
    if command == "init":
        from .config import state_dir

        path = args.config or state_dir() / "config.json"
        if path.exists():
            raise ConnectError("Configuration already exists; use provider commands to change it")
        save(config, path)
        gateway_key()
        print(
            "Created IteraCompute profile. Set ITERACOMPUTE_API_KEY, then run itera-connect up --web"
        )
    elif command == "provider":
        if args.action == "list":
            output(config)
        elif args.action == "use":
            if args.id not in config["providers"]:
                raise ConnectError("Unknown provider")
            config["active_provider"] = args.id
            save(config, args.config)
            print("Default provider: " + args.id + ". Restart the relay to apply.")
        else:
            if args.id in config["providers"]:
                raise ConnectError(
                    "Provider already exists; edit its environment-only config explicitly"
                )
            config["providers"][args.id] = {
                "name": args.name or args.id,
                "key_env": args.key_env,
                "default_model": args.model,
                "allow_http": args.allow_http,
                "endpoints": {
                    k: getattr(args, k).rstrip("/")
                    for k in ("chat", "responses", "anthropic", "gemini")
                    if getattr(args, k)
                },
            }
            save(config, args.config)
            print("Added " + args.id + ". Restart the relay and run sync.")
    elif command in ("serve", "up"):
        with Gateway(config) as gateway:
            print("Relay listening at " + gateway_url(config), flush=True)
            if command == "serve":
                gateway.serve_forever()
            else:
                worker = threading.Thread(target=gateway.serve_forever, daemon=True)
                worker.start()
                try:
                    sync_magpie(config)
                    print("Providers synced. Starting Magpie.", flush=True)
                    result = magpie(
                        ["serve", *(["--web"] if args.web else [])],
                        timeout=None,
                        vendor_env_names=vendor_env_names,
                    )
                    return result.returncode
                finally:
                    gateway.shutdown()
                    worker.join(timeout=3)
    elif command == "install-magpie":
        print("Verified Magpie: " + str(install_magpie()))
    elif command == "sync":
        output({"synced": sync_magpie(config)})
    elif command == "models":
        output({"provider": pid, "data": provider_models(config["providers"][pid])})
    elif command == "connect":
        connect(config, args.target, pid, args.model)
        print("Connected " + args.target + ". Restart the client if it keeps its config in memory.")
    elif command == "disconnect":
        magpie([args.target, "default"], capture=True, vendor_env_names=vendor_env_names)
        print("Disconnected " + args.target + ". Restart it if required.")
    elif command == "cc-link":
        print(cc_link(config, args.target, pid, args.model, args.api_format, args.via))
    elif command == "export":
        write_export(config, args.target, pid, args.out, args.model)
        print("Fragment written to " + str(args.out) + "; merge it into your client config.")
    elif command == "run":
        return launch(config, args.target, pid, args.model, args.via, trailing)
    elif command == "probe":
        if not 32 <= args.budget <= 8192:
            raise ConnectError("Probe budget must be between 32 and 8192 tokens per request")
        result = probe(
            config, pid, args.model, args.via, args.protocol, args.budget, not args.no_tools
        )
        output(result, args.out)
        return 0 if result["passed"] else 1
    elif command == "smoke":
        if not 10 <= args.timeout <= 600:
            raise ConnectError("Smoke timeout must be between 10 and 600 seconds per client")
        results = [smoke(config, t, pid, args.model, args.via, args.timeout) for t in args.targets]
        output({"kind": "native-clients", "results": results}, args.out)
        return 0 if results and all(r["status"] == "passed" for r in results) else 1
    elif command == "doctor":
        clients = {
            t: bool(shutil.which(t)) for t in ("claude", "codex", "openclaw", "hermes", "cc-switch")
        }
        try:
            clients["magpie"] = bool(magpie_bin())
        except ConnectError:
            clients["magpie"] = False
        try:
            relay = (
                json_request("GET", gateway_url(config) + "/health", timeout=2).get("name")
                == "iteraconnect"
            )
        except ConnectError:
            relay = False
        output(
            {
                "version": __version__,
                "clients": clients,
                "relay_running": relay,
                "providers": {
                    k: {
                        "key_present": bool(api_key(v, required=False)),
                        "key_env": v["key_env"],
                        "protocols": list(v["endpoints"]),
                    }
                    for k, v in config["providers"].items()
                },
            }
        )
    elif command == "magpie":
        return magpie(trailing, timeout=None, vendor_env_names=vendor_env_names).returncode
    elif command == "cc-switch":
        binary = shutil.which("cc-switch")
        if not binary:
            raise ConnectError(
                "Install CC Switch from its official release, then use cc-link to import"
            )
        return subprocess.run([binary, *trailing]).returncode
    return 0
