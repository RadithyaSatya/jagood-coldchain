# Fine-Tuning JaGOOD AI Explain

This directory provides a reproducible LoRA fine-tuning pipeline for the explanation layer used by
JaGOOD. It is deliberately separate from the runtime dependencies because MLX training requires an
Apple-silicon Mac.

## Scope

The adapter specializes `Llama-3.2-1B-Instruct` for one narrow task: turning structured JaGOOD
route, delay, quality, and SHAP-derived facts into concise Indonesian or English explanations. It
does not train the model to calculate routes, risk, delay, or product quality.

The synthetic supervised dataset is generated with a fixed seed and split before training into 240
training, 30 validation, and 30 held-out test examples. Prompt-injection-like operator notes are
included in a small subset, while the expected answer remains grounded in the trusted fields.

## Reproduce training on Apple silicon

From the repository root:

```bash
bash services/ai/ai-explain/finetuning/train.sh
```

The script uses Python 3.12, installs the pinned MLX-LM training dependency in a local virtual
environment, regenerates the dataset, runs 100 LoRA iterations, and reports loss on the held-out
test set. It also compares base and adapted generations on held-out factual-grounding cases.
Learned weights and configuration are saved under `artifacts/adapters/`.

This is genuine parameter-efficient fine-tuning: LoRA matrices in the final eight transformer
layers are optimized while the pretrained base weights remain frozen. Prompt engineering alone is
not presented as fine-tuning.

## Build the fine-tuned model for Ollama

The adapter was trained against the same Llama 3.2 1B Instruct base used by `llama3.2:1b` in
Ollama. After training:

```bash
cd services/ai/ai-explain/finetuning
bash export_ollama.sh
ollama run llama-jagood-ai-explain:latest
```

Then configure the service:

```bash
export OLLAMA_MODEL=llama-jagood-ai-explain:latest
docker compose up --build
```

`export_ollama.sh` fuses the adapter into the BF16 base, converts the fused Safetensors model with
the official llama.cpp converter, and asks Ollama to create a Q8 model. The generated fused model
is intentionally gitignored because it is larger than 2 GB and can be reproduced from the checked-
in adapter. The derived model name starts with `Llama` to follow the Llama 3.2 license naming rule.
JaGOOD is built with Llama 3.2; attribution is recorded in `NOTICE`.

Do not apply the adapter to another base model. A base mismatch can produce invalid output.

## Evidence for the proposal

The repository contains:

- deterministic dataset generation and immutable split hashes in `data/manifest.json`;
- training hyperparameters in `config.yaml`;
- learned LoRA weights and configuration under `artifacts/adapters/` after training;
- validation loss during training and held-out test loss after training;
- before/after factual coverage and prompt-injection checks in `artifacts/evaluation.json`;
- Ollama `Modelfile` definitions connecting the trained adapter to the application runtime.

The dataset is synthetic and task-specific. Evaluation demonstrates specialization on the held-out
synthetic task; it is not evidence of operational accuracy on real shipments.
