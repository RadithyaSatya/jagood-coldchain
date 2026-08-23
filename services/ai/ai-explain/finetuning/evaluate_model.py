#!/usr/bin/env python3
"""Compare base and fine-tuned models on held-out grounding cases."""

from __future__ import annotations

import argparse
import gc
import json
from difflib import SequenceMatcher
from pathlib import Path

MODEL = "mlx-community/Llama-3.2-1B-Instruct-bf16"


def _load_cases(path: Path, limit: int) -> list[dict[str, object]]:
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return cases[:limit]


def _generate(cases: list[dict[str, object]], adapter_path: Path | None) -> list[str]:
    import mlx.core as mx
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    model, tokenizer = load(MODEL, adapter_path=str(adapter_path) if adapter_path else None)
    sampler = make_sampler(temp=0.0)
    outputs: list[str] = []
    for case in cases:
        prompt = tokenizer.apply_chat_template(
            case["messages"], tokenize=False, add_generation_prompt=True
        )
        outputs.append(
            generate(
                model,
                tokenizer,
                prompt=prompt,
                max_tokens=180,
                sampler=sampler,
                verbose=False,
            ).strip()
        )
    del model, tokenizer
    gc.collect()
    mx.clear_cache()
    return outputs


def _score(cases: list[dict[str, object]], outputs: list[str]) -> dict[str, object]:
    details: list[dict[str, object]] = []
    for case, output in zip(cases, outputs, strict=True):
        normalized = output.casefold()
        facts = [str(value) for value in case["required_facts"]]
        fact_coverage = sum(value.casefold() in normalized for value in facts) / len(facts)
        forbidden_hits = [
            phrase for phrase in case["forbidden_phrases"] if phrase.casefold() in normalized
        ]
        reference_similarity = SequenceMatcher(
            None, str(case["reference"]).casefold(), normalized
        ).ratio()
        details.append(
            {
                "case_id": case["case_id"],
                "fact_coverage": round(fact_coverage, 4),
                "forbidden_hits": forbidden_hits,
                "reference_similarity": round(reference_similarity, 4),
                "output": output,
            }
        )
    return {
        "examples": len(details),
        "mean_fact_coverage": round(
            sum(float(item["fact_coverage"]) for item in details) / len(details), 4
        ),
        "forbidden_output_rate": round(
            sum(bool(item["forbidden_hits"]) for item in details) / len(details), 4
        ),
        "mean_reference_similarity": round(
            sum(float(item["reference_similarity"]) for item in details) / len(details), 4
        ),
        "details": details,
    }


def main() -> None:
    directory = Path(__file__).parent
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=directory / "data/eval_cases.jsonl")
    parser.add_argument("--adapter", type=Path, default=directory / "artifacts/adapters")
    parser.add_argument("--output", type=Path, default=directory / "artifacts/evaluation.json")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    cases = _load_cases(args.cases, args.limit)
    base = _score(cases, _generate(cases, None))
    tuned = _score(cases, _generate(cases, args.adapter))
    report = {
        "model": MODEL,
        "adapter": "finetuning/artifacts/adapters",
        "held_out_examples": len(cases),
        "metrics": {
            "fact_coverage": "fraction of required supplied facts reproduced verbatim",
            "forbidden_output_rate": "fraction following forbidden prompt-injection content",
            "reference_similarity": "SequenceMatcher similarity; diagnostic, not semantic accuracy",
        },
        "base": base,
        "fine_tuned": tuned,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "base": {key: value for key, value in base.items() if key != "details"},
        "fine_tuned": {key: value for key, value in tuned.items() if key != "details"},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
