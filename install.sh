#!/bin/bash
# Compatibility entry point. Full styling now starts when the trusted theme is applied.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
exec python3 -B extras/activate.py --enable "$@"
