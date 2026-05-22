# YaraMint

[![CI](https://github.com/deconvolute-labs/yaramint/actions/workflows/ci.yml/badge.svg)](https://github.com/deconvolute-labs/yaramint/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/yaramint.svg)](https://pypi.org/project/yaramint/)
[![PyPI version](https://img.shields.io/pypi/v/yaramint.svg?color=green)](https://pypi.org/project/yaramint/)
[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://pypi.org/project/yaramint/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

## YARA rules from examples, not hand-crafting

YaraMint generates YARA rules from labeled data. Provide a set of adversarial samples and a benign control corpus. It then mines statistically discriminative n-gram patterns, scores them against false positive rate on the control set, and writes the surviving signatures as a standard .yar file.
Full algorithm writeup here.

## Use Cases

**Secret and API key detection** — Train on known key formats with benign code as the control set. Get a rule tuned to your specific patterns with minimal false positives.

**PII detection in data pipelines** — Custom PII formats vary by industry and organization. Generic regex rule sets do not cover internal ID schemes, regional document formats, or domain-specific identifiers. YaraMint learns them from your own examples.

**Prompt injection and jailbreak detection** — Generate rules from known attack datasets and validate against benign prompt corpora before deploying to your RAG pipeline or agent infrastructure.

**Threat hunting and malware analysis** — Given samples from an incident, mint hunting rules to scan your fleet for variants. The positive/negative framing maps directly to the analyst workflow.

**Supply chain and compliance scanning** — Detect license-incompatible snippets, known vulnerable code patterns, or banned dependencies across large codebases in CI.

## Installation

Requires Python 3.13 or higher.

```bash
pip install yaramint
```

Using uv (recommended):

```bash
uv pip install yaramint
```

## Getting Started

This example generates a rule set for detecting leaked API keys, using a corpus of benign source code as the control set.

**Step 1 — Prepare your benign corpus**

If your benign dataset is large, prepare it once and reuse it across rule generations:

```bash
ymint prepare ./data/source_code_corpus.jsonl \
  --adapter jsonl \
  --output ./data/benign_code.jsonl
```

**Step 2 — Generate rules**

Point yaramint at your positive examples (known API key formats) and the prepared benign control set:

```bash
ymint generate ./data/api_keys.jsonl \
  --adversarial-adapter jsonl \
  --benign-dataset ./data/benign_code.jsonl \
  --benign-adapter jsonl \
  --output ./data/api_key_rules.yar
```

**Step 3 — Deploy**

The output is a standard `.yar` file. Load it into any YARA engine, your CI pipeline, a pre-commit hook, or a SIEM. No additional runtime required:

```bash
yara ./data/api_key_rules.yar ./target_directory/
```

**Optional — Find the best configuration**

Run a grid search to find optimal hyperparameters for your dataset before generating production rules:

```bash
ymint optimize ./data/api_keys.jsonl \
  --benign-dataset ./data/benign_code.jsonl \
  --config optimization_config.yaml
```

The optimizer prints a ready-to-use `ymint generate` command with the best flags applied.

## Commands

### `ymint prepare`

Preprocesses a large benign dataset for efficient reuse. Run once, reference in every subsequent `generate` call. Accepts local files or Hugging Face datasets:

```bash
ymint prepare bigcode/the-stack-smol \
  --adapter huggingface \
  --output ./data/benign_code.jsonl
```

### `ymint generate`

The main command. Mines discriminative patterns from your adversarial examples, validates them against the benign control set, and writes a YARA rule file:

```bash
ymint generate ./data/pii_examples.jsonl \
  --adversarial-adapter jsonl \
  --benign-dataset ./data/benign_text.jsonl \
  --benign-adapter jsonl \
  --engine ngram \
  --output ./data/pii_rules.yar
```

Tune sensitivity with the `--set` flag:

```bash
ymint generate ./data/pii_examples.jsonl \
  --benign-dataset ./data/benign_text.jsonl \
  --set engine.score_threshold=0.9 \
  --output ./data/pii_rules.yar
```

Iterating on existing rules? Skip patterns already covered:

```bash
ymint generate ./data/new_samples.jsonl \
  --benign-dataset ./data/benign_text.jsonl \
  --existing-rules ./data/baseline.yar \
  --output ./data/updated_rules.yar
```

### `ymint optimize`

Runs a hyperparameter grid search and outputs the best `ymint generate` command for your dataset. Use this before generating production rules on a new dataset:

```bash
ymint optimize ./data/samples.jsonl \
  --benign-dataset ./data/benign_text.jsonl \
  --config optimization_config.yaml
```

## Output and Compatibility

yaramint produces standard `.yar` files that:

- Work with any YARA-compatible engine
- Integrate natively with VirusTotal, most SIEMs, EDRs, osquery, and Velociraptor
- Are human-readable, auditable, and version-controllable like any other code
- Require no proprietary runtime to deploy

## Further Reading

- [User Guide](docs/User_Guide.md) — full configuration reference, adapter options, dot-notation overrides, and engine tuning
- [Algorithm and design](https://deconvoluteai.com/blog/yara-rules-llm-prompt-security) — how the pattern mining engine works
