from __future__ import annotations

"""CLI helper to summarise text using the configured service."""

import argparse
import sys

from summarize.services import SummarizationClient, SummarizationError


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise arbitrary text via the CML model or fallback logic.")
    parser.add_argument("text", nargs="?", help="Text to summarise. When omitted, stdin is used.")
    args = parser.parse_args()

    if args.text:
        payload = args.text
    else:
        payload = sys.stdin.read().strip()

    client = SummarizationClient()
    try:
        print(client.summarize(payload))
    except SummarizationError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
