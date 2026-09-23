#!/usr/bin/env python3
"""Discover cheap OpenRouter models and their ZDR/provider metadata.

This is intentionally read-only and uses only the Python standard library.
It never prints API keys.  The public model and ZDR endpoints work without an
API key; --account adds the authenticated /models/user and /providers calls.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE = "https://openrouter.ai/api/v1"


def get_json(path: str, params: dict[str, str] | None = None, key: str | None = None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    if key:
        request.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"{exc.code} from {url}: {body[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"request failed for {url}: {exc.reason}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-input", default="1", help="maximum USD per million input tokens")
    parser.add_argument("--max-output", default="5", help="maximum USD per million output tokens")
    parser.add_argument("--account", action="store_true", help="also query authenticated account-filtered data")
    parser.add_argument("--key-env", default="OPENROUTER_API_KEY", help="environment variable for --account")
    args = parser.parse_args()

    result = {
        "query": {
            "zdr": True,
            "max_price": args.max_input,
            "max_output_price": args.max_output,
            "sort": "pricing-low-to-high",
        },
        "models": get_json("/models", {
            "zdr": "true",
            "max_price": args.max_input,
            "max_output_price": args.max_output,
            "sort": "pricing-low-to-high",
        }),
        "zdr_endpoints": get_json("/endpoints/zdr"),
    }

    if args.account:
        key = os.environ.get(args.key_env)
        if not key:
            print(f"--account requires ${args.key_env}", file=sys.stderr)
            return 2
        result["account_models"] = get_json("/models/user", key=key)
        result["providers"] = get_json("/providers", key=key)

    json.dump(result, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
