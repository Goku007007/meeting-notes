#!/usr/bin/env bash
set -euo pipefail

# Run from apps/api regardless of where the command is invoked from.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${API_DIR}"

# Load local env vars if present.
if [[ -f ".env" ]]; then
  set -a
  source ".env"
  set +a
fi

# macOS fork safety: avoid Objective-C runtime crash in RQ forked children.
if [[ "$(uname -s)" == "Darwin" ]]; then
  export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy || true
  export NO_PROXY="*"
  export no_proxy="*"
fi

REDIS_URL_VALUE="${REDIS_URL:-redis://localhost:6379/0}"

# On macOS, default to SimpleWorker to avoid fork-related crashes.
if [[ "$(uname -s)" == "Darwin" ]]; then
  WORKER_CLASS="${RQ_WORKER_CLASS:-rq.worker.SimpleWorker}"
else
  WORKER_CLASS="${RQ_WORKER_CLASS:-rq.worker.Worker}"
fi

echo "Starting RQ worker..."
echo "  redis: ${REDIS_URL_VALUE}"
echo "  worker class: ${WORKER_CLASS}"

PYTHONPATH=. ./.venv/bin/rq worker default \
  --worker-class "${WORKER_CLASS}" \
  --url "${REDIS_URL_VALUE}" \
  --with-scheduler
