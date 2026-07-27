#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cp "$ROOT_DIR/app/mobile_saas_app.html" "$ROOT_DIR/outputs/mobile_saas_app.html"
echo "Saved mobile app preview to $ROOT_DIR/outputs/mobile_saas_app.html"

if [[ -x "$ROOT_DIR/work/build_mobile_saas_backend.sh" ]]; then
  "$ROOT_DIR/work/build_mobile_saas_backend.sh"
fi
