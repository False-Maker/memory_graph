#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-intranet}"

missing=()

require_var() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    missing+=("$name")
  fi
}

require_one_of() {
  local a="$1"
  local b="$2"
  if [[ -z "${!a:-}" && -z "${!b:-}" ]]; then
    missing+=("$a|$b")
  fi
}

# NEO4J_PASSWORD is now optional (default config uses NetworkX/SQLite + FAISS)
# Only require it if NEO4J_URI is explicitly set
if [[ -n "${NEO4J_URI:-}" ]]; then
  require_var "NEO4J_PASSWORD"
fi

require_one_of "OPENAI_API_KEY" "ANTHROPIC_API_KEY"

if [[ "$MODE" == "cloud" ]]; then
  require_var "PRIVATE_NETWORK_ONLY"
  require_var "ALLOWLIST_CIDRS"
  if [[ "${PRIVATE_NETWORK_ONLY:-}" != "true" ]]; then
    missing+=("PRIVATE_NETWORK_ONLY=true")
  fi
fi

if (( ${#missing[@]} > 0 )); then
  printf 'Missing required environment variables for mode=%s:\n' "$MODE" >&2
  for item in "${missing[@]}"; do
    printf ' - %s\n' "$item" >&2
  done
  exit 1
fi

echo "Environment check passed for mode=$MODE"
