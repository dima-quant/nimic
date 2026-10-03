#!/usr/bin/env python3
import sys
import json
import re

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        # Fall back to asking user if JSON parsing fails
        print(json.dumps({"decision": "force_ask", "reason": "Could not parse hook input"}))
        return

    tool_call = data.get("toolCall", {})
    args = tool_call.get("args", {})
    cmd = args.get("CommandLine", "")

    # Patterns to intercept:
    # 1. git commit (with any options like -m, --amend, -a, etc.)
    # 2. git push
    # 3. indiscriminate/bulk git add (git add ., git add -A, git add --all, git add -u, git add *)
    git_commit_pattern = r'\bgit\s+(?:-[^\s]+\s+)*commit(?:\s|$)'
    git_push_pattern = r'\bgit\s+(?:-[^\s]+\s+)*push(?:\s|$)'
    git_bulk_add_pattern = r'\bgit\s+(?:-[^\s]+\s+)*add\s+(?:-A|--all|-u|\.|\*)(?:\s|$)'

    reasons = []
    if re.search(git_commit_pattern, cmd):
        reasons.append("git commit")
    if re.search(git_push_pattern, cmd):
        reasons.append("git push")
    if re.search(git_bulk_add_pattern, cmd):
        reasons.append("bulk staging ('git add .' or '-A')")

    if reasons:
        msg = f"User confirmation required before executing: {', '.join(reasons)}. Command: {cmd.strip()}"
        print(json.dumps({
            "decision": "force_ask",
            "reason": msg
        }))
    else:
        print(json.dumps({"decision": "allow"}))

if __name__ == "__main__":
    main()
