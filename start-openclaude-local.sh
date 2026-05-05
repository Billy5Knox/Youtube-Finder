#!/usr/bin/env bash
# start-openclaude-local.sh — Launch OpenClaude with a local Ollama model
#
# Usage:
#   ./start-openclaude-local.sh            # interactive menu
#   ./start-openclaude-local.sh 1          # launch with gemma4:e4b
#   ./start-openclaude-local.sh gemma4     # launch by partial name match

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────
OLLAMA_URL="http://localhost:11434"
PROVIDER="ollama"

# Chat-capable models only (skip embedding models)
MODELS=(
  "gemma4:e4b"
  "qwen2.5-coder:14b-32k"
  "qwen2.5-coder:14b"
  "qwen3:14b"
)

DESCRIPTIONS=(
  "Gemma 4 — 8B general purpose"
  "Qwen 2.5 Coder — 14B, 32K context"
  "Qwen 2.5 Coder — 14B, default context"
  "Qwen 3 — 14B general purpose"
)

# ── Helpers ────────────────────────────────────────────────────────────
check_ollama() {
  if ! curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    echo "Error: Ollama is not running at $OLLAMA_URL"
    echo "Start Ollama first, then re-run this script."
    exit 1
  fi
}

show_menu() {
  echo ""
  echo "╔══════════════════════════════════════════════════╗"
  echo "║       OpenClaude — Local Model Launcher          ║"
  echo "╚══════════════════════════════════════════════════╝"
  echo ""
  for i in "${!MODELS[@]}"; do
    printf "  [%d]  %-28s  %s\n" "$((i + 1))" "${MODELS[$i]}" "${DESCRIPTIONS[$i]}"
  done
  echo ""
  echo "  [a]  Launch ALL models (separate sessions)"
  echo "  [q]  Quit"
  echo ""
}

launch_model() {
  local model="$1"
  echo ""
  echo "── Launching OpenClaude with $model ──"
  echo "   Provider: $PROVIDER"
  echo "   Ollama:   $OLLAMA_URL"
  echo ""
  openclaude --provider "$PROVIDER" --model "$model"
}

launch_all() {
  echo ""
  echo "Launching a session for each model in new terminal windows..."
  echo ""
  for model in "${MODELS[@]}"; do
    echo "  Starting: $model"
    # Open each in a new mintty/git-bash window on Windows
    if command -v mintty &> /dev/null; then
      mintty -t "OpenClaude — $model" bash -c "openclaude --provider $PROVIDER --model $model; read -p 'Press Enter to close...'" &
    elif command -v cmd.exe &> /dev/null; then
      cmd.exe /c start "OpenClaude — $model" bash -c "openclaude --provider $PROVIDER --model $model; read -p 'Press Enter to close...'" &
    else
      echo "    (no windowing available — skipping $model)"
    fi
  done
  echo ""
  echo "All sessions launched."
}

# ── Main ───────────────────────────────────────────────────────────────
check_ollama

# If an argument was passed, use it directly
if [[ "${1:-}" != "" ]]; then
  arg="$1"

  # Numeric selection
  if [[ "$arg" =~ ^[0-9]+$ ]] && (( arg >= 1 && arg <= ${#MODELS[@]} )); then
    launch_model "${MODELS[$((arg - 1))]}"
    exit 0
  fi

  # "all" shortcut
  if [[ "$arg" == "a" || "$arg" == "all" ]]; then
    launch_all
    exit 0
  fi

  # Partial name match
  for model in "${MODELS[@]}"; do
    if [[ "$model" == *"$arg"* ]]; then
      launch_model "$model"
      exit 0
    fi
  done

  echo "Error: No model matching '$arg'"
  echo "Available: ${MODELS[*]}"
  exit 1
fi

# Interactive menu
while true; do
  show_menu
  read -rp "  Select model: " choice

  case "$choice" in
    [1-4])
      launch_model "${MODELS[$((choice - 1))]}"
      break
      ;;
    a|A)
      launch_all
      break
      ;;
    q|Q)
      echo "Bye."
      exit 0
      ;;
    *)
      echo "  Invalid choice. Try again."
      ;;
  esac
done
