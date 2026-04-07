from __future__ import annotations

import argparse
from pathlib import Path
import sys


def filter_config(lines: list[str], include_local: bool) -> str:
    output: list[str] = []
    skipping_local_block = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if stripped == "- model_name: local-chat" and not include_local:
            skipping_local_block = True
            continue
        if skipping_local_block:
            if line.startswith("  - model_name:"):
                skipping_local_block = False
            elif line and not line.startswith(" "):
                skipping_local_block = False
            else:
                continue
        if not include_local and "auto-chat:   [gpt-chat, local-chat]" in line:
            line = line.replace("[gpt-chat, local-chat]", "[gpt-chat]")
            if "#" in line and "http" not in line:
                line = line.split("#", 1)[0].rstrip() + "\n"
            output.append(line)
            continue
        if not include_local and "tags: [chat, local]" in line:
            continue
        if "#" in line and "http" not in line:
            line = line.split("#", 1)[0].rstrip() + "\n"
        output.append(line)

    compact: list[str] = []
    previous_blank = False
    previous_content = ""
    for line in output:
        is_blank = not line.strip()
        if is_blank and not compact:
            continue
        if is_blank and previous_content.endswith(":"):
            continue
        if is_blank and previous_blank:
            continue
        compact.append(line)
        previous_blank = is_blank
        if not is_blank:
            previous_content = line.strip()
    return "".join(compact).strip() + "\n"


def render_configmap(config_text: str, namespace: str, name: str) -> str:
    rendered_lines = []
    for line in config_text.rstrip("\n").splitlines():
        rendered_lines.append("\n" if not line else f"    {line}\n")
    indented = "".join(rendered_lines)
    return (
        "apiVersion: v1\n"
        "kind: ConfigMap\n"
        "metadata:\n"
        f"  name: {name}\n"
        f"  namespace: {namespace}\n"
        "data:\n"
        "  config.yaml: |\n"
        f"{indented}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="proxy/config/config.yaml")
    parser.add_argument("--output", default="proxy/k8s/litellm/configmap.yaml")
    parser.add_argument("--namespace", default="llm-system")
    parser.add_argument("--name", default="litellm-config")
    parser.add_argument("--include-local", action="store_true")
    parser.add_argument("--stdout", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    source = root / args.source
    output = root / args.output
    config_text = filter_config(source.read_text(encoding="utf-8").splitlines(keepends=True), args.include_local)
    rendered = render_configmap(config_text, namespace=args.namespace, name=args.name)
    if args.stdout:
        sys.stdout.write(rendered)
        return 0
    if args.check:
        current = output.read_text(encoding="utf-8")
        return 0 if current == rendered else 1
    output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
