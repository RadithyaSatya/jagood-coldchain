# Fine-Tuning Results

Run date: 23 August 2026
Hardware: Apple M2, 8 GB unified memory
Base model: `mlx-community/Llama-3.2-1B-Instruct-bf16`
Method: LoRA on the final 8 transformer layers

## Training summary

| Metric | Result |
|---|---:|
| Total base parameters | 1,235.814 million |
| Trainable LoRA parameters | 2.818 million (0.228%) |
| Training iterations | 100 |
| Initial validation loss | 1.808 |
| Final validation loss | 0.001 |
| Held-out test loss | 0.001 |
| Held-out test perplexity | 1.001 |
| Peak training memory | 3.497 GB |

## Before/after generation check

Ten examples were selected from the held-out synthetic test split. The evaluator checks exact
coverage of supplied route, delay, remaining-shelf-life, and primary-factor strings. It also checks
whether prompt-injection-like content embedded in an operator note appears in the answer.

| Metric | Base model | Fine-tuned adapter |
|---|---:|---:|
| Mean supplied-fact coverage | 35% | 100% |
| Forbidden-output rate | 0% | 0% |
| Mean reference-string similarity | 25.3% | 100% |

The full outputs are stored in `artifacts/evaluation.json`. These high scores reflect a narrow,
template-structured synthetic task. They demonstrate task specialization and reproducibility, not
real-shipment accuracy, broad language quality, or food-safety validation. A larger paraphrased and
human-reviewed evaluation set is future work.

## Runtime verification

The adapter was fused into the BF16 base, converted to GGUF, quantized to Q8 by Ollama, and called
through Ollama's OpenAI-compatible `/v1/chat/completions` endpoint. After restoring the Llama 3 chat
template in `Modelfile.fused`, the runtime response reproduced the four supplied facts and the
reference Indonesian explanation on the smoke-test case.

Method references: [MLX-LM LoRA documentation](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md)
and [Ollama model import documentation](https://docs.ollama.com/import).
