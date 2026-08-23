#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
FINETUNING_DIR="$REPOSITORY_ROOT/services/ai/ai-explain/finetuning"
VENV_DIR="$FINETUNING_DIR/.venv"
FUSED_DIR="$FINETUNING_DIR/artifacts/fused"
MODEL_NAME="${OLLAMA_MODEL_NAME:-llama-jagood-ai-explain:latest}"
CONVERTER_DIR="$(mktemp -d /tmp/jagood-llama-convert.XXXXXX)"
trap 'rm -rf "$CONVERTER_DIR"' EXIT

if [[ ! -f "$FINETUNING_DIR/artifacts/adapters/adapters.safetensors" ]]; then
  echo "Adapter not found. Run finetuning/train.sh first." >&2
  exit 1
fi
if [[ ! -x "$VENV_DIR/bin/mlx_lm.fuse" ]]; then
  echo "Training environment not found. Run finetuning/train.sh first." >&2
  exit 1
fi

"$VENV_DIR/bin/python" -m pip install "torch==2.13.0"
"$VENV_DIR/bin/hf" download \
  mlx-community/Llama-3.2-1B-Instruct-bf16 README.md .gitattributes >/dev/null

cd "$REPOSITORY_ROOT"
"$VENV_DIR/bin/mlx_lm.fuse" \
  --model mlx-community/Llama-3.2-1B-Instruct-bf16 \
  --adapter-path "$FINETUNING_DIR/artifacts/adapters" \
  --save-path "$FUSED_DIR"

git clone --depth 1 https://github.com/ggml-org/llama.cpp.git "$CONVERTER_DIR/llama.cpp"
PYTHONPATH="$CONVERTER_DIR/llama.cpp/gguf-py" "$VENV_DIR/bin/python" \
  "$CONVERTER_DIR/llama.cpp/convert_hf_to_gguf.py" \
  "$FUSED_DIR" \
  --outfile "$FUSED_DIR/llama-jagood-ai-explain-f16.gguf" \
  --outtype f16

cd "$FINETUNING_DIR"
ollama create "$MODEL_NAME" -f Modelfile.fused -q q8_0
echo "Created Ollama model: $MODEL_NAME"
