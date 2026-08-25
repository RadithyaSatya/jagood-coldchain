#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
FINETUNING_DIR="$REPOSITORY_ROOT/services/ai/ai-explain/finetuning"
PYTHON_BIN="${PYTHON_BIN:-/opt/homebrew/bin/python3.12}"
VENV_DIR="$FINETUNING_DIR/.venv"

"$PYTHON_BIN" -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$FINETUNING_DIR/requirements.txt"
"$VENV_DIR/bin/python" "$FINETUNING_DIR/generate_dataset.py"

cd "$REPOSITORY_ROOT"
"$VENV_DIR/bin/mlx_lm.lora" --config "$FINETUNING_DIR/config.yaml"
find "$FINETUNING_DIR/artifacts/adapters" \
  -maxdepth 1 -type f -name '0*_adapters.safetensors' -delete
"$VENV_DIR/bin/mlx_lm.lora" \
  --model mlx-community/Llama-3.2-1B-Instruct-bf16 \
  --data "$FINETUNING_DIR/data" \
  --adapter-path "$FINETUNING_DIR/artifacts/adapters" \
  --num-layers 8 \
  --batch-size 1 \
  --max-seq-length 1024 \
  --mask-prompt \
  --test \
  --test-batches -1
"$VENV_DIR/bin/python" "$FINETUNING_DIR/evaluate_model.py"
