from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from python_agent.core.pipeline import CommandPipeline, PipelineError
from python_agent.cpp_client import CppClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Beavis Agent text MVP")
    parser.add_argument("text", nargs="*", help="Command text, for example: звук на полную")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Send ToolCall to the C++ runtime instead of only building JSON",
    )
    parser.add_argument(
        "--executor",
        help="Path to beavis_runtime.exe",
    )
    parser.add_argument(
        "--no-log",
        action="store_true",
        help="Do not append the command to actions.jsonl",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_text = " ".join(args.text).strip()

    if not raw_text:
        raw_text = input("beavis> ").strip()

    if not raw_text:
        print("Empty command")
        return 1

    cpp_client = CppClient(executable_path=args.executor) if args.executor else None
    pipeline = CommandPipeline(cpp_client=cpp_client)

    try:
        output = pipeline.run(
            raw_text=raw_text,
            execute=args.execute,
            log=not args.no_log,
        )
    except PipelineError as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(output.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
