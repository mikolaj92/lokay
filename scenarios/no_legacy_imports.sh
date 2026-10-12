#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
if grep -R -n -E '(^|[^A-Za-z0-9_])(import src\.lokay|from src\.lokay)([^A-Za-z0-9_]|$)' "$root/src" --include='*.py'; then
  echo "legacy import" >&2
  exit 1
fi
echo "no legacy imports"
