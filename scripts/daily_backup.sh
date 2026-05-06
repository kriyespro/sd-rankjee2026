#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash scripts/daily_backup.sh /absolute/path/to/project
# If no argument is provided, script uses current directory.

PROJECT_DIR="${1:-$(pwd)}"
cd "$PROJECT_DIR"

echo "[backup] $(date '+%Y-%m-%d %H:%M:%S') Starting daily backup..."
python3 manage.py create_backup --types full db
echo "[backup] $(date '+%Y-%m-%d %H:%M:%S') Completed."
