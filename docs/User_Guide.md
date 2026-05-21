# User Guide

This guide is for practitioners running YaraMint in real workflows. For general project information, see the README.

## Core Concepts

YaraMint generates YARA rules by identifying textual patterns that are statistically common in adversarial samples and rare in benign ones.

Every run requires two datasets:

- **Adversarial data**: the inputs you want to detect.
- **Benign data**: the control corpus used to suppress false positives.

The generator extracts candidate signatures from adversarial samples, scores them against the benign corpus, and emits only patterns that are both distinctive and stable.

### Data Model

Internally, YaraMint operates on structured Pydantic models representing normalized text samples. Both `prepare` and `generate` accept multiple input formats through adapters.

JSONL is the default and recommended format for generation because it avoids repeated downloads or streaming of large datasets, reduces preprocessing overhead during iteration, and makes datasets straightforward to inspect and debug. Other formats are supported but may incur additional cost when reused across runs.

### Engine Model

YaraMint uses a modular engine architecture. Engines define how features are extracted from text and how candidate signatures are scored against benign data. The default engine is `ngram`, which extracts character n-grams and ranks them based on adversarial prevalence and benign suppression. The surrounding workflow and configuration are engine-agnostic, so additional engines can be introduced without changing how the tool is used.

### Determinism and Reproducibility

Given the same inputs, configuration, and rule date, YaraMint produces identical output. This supports auditing, versioning, and CI-driven rule generation.

## Recommended Workflow

For most use cases, a two-step pipeline works well.

First, normalize your datasets using `ymint prepare`. This converts raw inputs into a reusable representation and avoids repeated downloads or expensive parsing. Preparation is particularly useful when working with large files, remote datasets, or when iterating on generation parameters.

Once the data is prepared, run `ymint generate` to extract signatures and emit YARA rules. Generation can consume prepared files or stream inputs directly, applies benign suppression, and writes a ready-to-use `.yar` file.

In practice, rule generation is iterative: prepare data once, generate rules, adjust thresholds or engine parameters, and regenerate. Re-run `prepare` only when the underlying data changes.

## Data Preparation with ymint prepare

The `prepare` command normalizes raw input data into a reusable representation. It is optional but recommended whenever the source data is large, remote, or expensive to parse. Preparation is a standalone preprocessing step and does not read `generation_config.yaml`.

During preparation, YaraMint loads data through an adapter, extracts the relevant text, and emits one normalized sample per line. Output is written as JSONL and can be reused across multiple generation runs without re-downloading or re-parsing the original source.

In most cases, adapters are selected automatically. Non-local inputs default to the Hugging Face adapter, local `.csv` files use the generic CSV adapter, and other local files are treated as raw text. Auto-detection is sufficient for standard datasets and common formats.

When auto-detection is not appropriate, you can force an adapter explicitly. This is useful when file extensions are misleading or when a dataset requires a specific parsing strategy:

```bash
ymint prepare data.xyz --output clean.jsonl --adapter raw-text
```

The Hugging Face adapter supports streaming directly from the Hub. Adapter-specific parameters such as `split` and `config_name` can be passed using `--set`. Preparing a dataset once avoids repeated streaming during rule generation and significantly improves iteration speed:

```bash
ymint prepare "rubend18/ChatGPT-Jailbreak-Prompts" \
  --output jailbreaks.jsonl \
  --set adapter.split=train \
  --set adapter.config_name=default
```

All adapters support row-level filtering via the `--filter` flag. Filters use a `column=value` syntax and are applied before normalization. Filtering early reduces noise, speeds up downstream processing, and improves rule quality:

```bash
ymint prepare data.csv --output clean.jsonl --filter "label=jailbreak"
```

## Rule Generation with ymint generate

The `generate` command extracts signatures from adversarial data, suppresses them against a benign control set, and emits YARA rules. This is the primary command once datasets are prepared.

Generation accepts the same input formats as `prepare`, but using prepared JSONL files is recommended when iterating. Streaming remote datasets during generation is supported but may incur repeated download or parsing costs across runs.

A minimal invocation requires adversarial input and an output path. A benign dataset is strongly recommended for any real-world use, as it directly controls false positives:

```bash
ymint generate jailbreaks.jsonl --benign benign.jsonl --output rules.yar
```

During generation, the engine extracts candidate features from adversarial samples, scores them against the benign corpus, and retains only patterns that meet the configured thresholds. The resulting rules are written directly to a standard `.yar` file compatible with any YARA engine.

### Benign Control Sets

The benign dataset defines what the generator should ignore. High-quality benign data matters more than sheer volume. A small but representative control set often outperforms a large, noisy one.

Benign datasets are typically prepared once and reused across multiple generation runs, allowing iteration on adversarial inputs and engine parameters without reprocessing the control data.

### CLI Overrides

Generation defaults are read from `generation_config.yaml`. Any CLI flags or `--set` overrides take precedence and apply only to the current run, making it easy to experiment without modifying committed configuration files.

### Iterative Tuning

Rule generation is inherently iterative. Generate an initial rule set, inspect the output, adjust sensitivity or engine parameters, and regenerate. Prepared datasets make this loop fast and predictable.

## Finding Hyperparameters with ymint optimize

Tuning generation parameters manually can be inefficient. The `optimize` command automates this by performing a grid search over a defined search space.

It splits your adversarial and benign data into Train (for rule generation) and Dev (for evaluation) sets, runs generation for every combination of parameters defined in your config, evaluates the resulting rules against the held-out Dev set, and reports the configuration with the best performance.

### The Optimization Configuration

Optimization is controlled by a YAML configuration file (default: `optimization_config.yaml`). This file defines three areas: the search space, selection criteria, and data splitting.

#### Search Space

The `search_space` section defines the parameters to iterate over. For the default `ngram` engine:

- **min_ngram / max_ngram**: controls the size of extracted patterns. Shorter n-grams increase recall but are noisier; longer n-grams are specific but brittle.
- **score_threshold**: the primary sensitivity knob. Lower values keep more candidate rules (higher coverage); higher values filter everything but the strongest signals.
- **benign_penalty_weight**: controls how aggressively the engine suppresses patterns that appear in benign text. Higher values reject anything that resembles safe text.
- **min_document_frequency**: the minimum percentage of adversarial samples a pattern must appear in. This filters out one-off anomalies to focus on systemic patterns.

```yaml
search_space:
  type: "ngram"
  min_ngram: [3, 4]
  max_ngram: [6]
  score_threshold: [0.05, 0.1, 0.2]
  benign_penalty_weight: [1.0, 2.0]
  min_document_frequency: [0.01]
```

#### Selection Criteria

The `selection` section determines how the best run is automatically chosen from results.

`target_metric` sets the primary metric to maximize (e.g. `recall`, `precision`, `f1_score`). Constraints define hard limits for acceptance, such as `max_false_positives: 0` to ensure zero false positives on the evaluation set:

```yaml
selection:
  target_metric: "recall"
  min_precision: 0.95
  max_false_positives: 0
```

### Running the Optimizer

The optimizer requires both adversarial and benign datasets. Prepared JSONL files are recommended for performance:

```bash
ymint optimize attacks.jsonl \
  --benign-dataset control.jsonl \
  --config optimization_config.yaml
```

The tool caches Train/Dev splits in a local `.optimize` folder to ensure that subsequent runs with different grid parameters remain comparable.

### Interpreting Results

The command outputs a summary of the best run, including metrics on the held-out Dev set, and prints a ready-to-use `ymint generate` command with the optimal `--set` overrides applied:

```text
BEST RUN: Iteration #5
   Score (recall): 0.8500
   Metrics: TP=85 FP=0 Prec=1.000 Rec=0.850
   Parameters: {'min_ngram': 3, 'score_threshold': 0.1, ...}
------------------------------------------------------------
To generate rules with this configuration:
ymint generate ... --set engine.min_ngram=3 --set engine.score_threshold=0.1 ...
```

Copy that line to generate your final production rules using the full dataset.

### Visualizing Results

yaramint includes a standalone visualization script to generate charts from optimization results. First install the visualization dependencies:

```bash
uv sync --group plots
```

Note: the `scripts/` directory is not included in the PyPI package. Clone the repo to access it.

Then run the visualizer on your results file:

```bash
uv run --group plots python scripts/plot_optimization_results.py \
  optimization_results_20260128.json \
  --metric f1_score
```

This generates a folder in `data/plots/` containing three visualizations.

#### 1. The Pareto Frontier (Precision vs. Recall)

This is the primary tool for decision-making. It visualizes the trade-offs available across configurations.

- **X-Axis (Recall)**: how many attacks were caught.
- **Y-Axis (Precision)**: how clean the alerts are (low false positive rate).

Look for configurations in the top-right corner with high detection rates and few false alarms. Pay attention to the point where recall increases slightly but precision drops sharply; this is where the engine becomes too permissive and starts flagging benign content.

#### 2. Parameter Correlation Matrix

This heatmap shows which parameters actually affect performance.

- **Red (+1.0)**: strong positive correlation with the target metric.
- **Blue (-1.0)**: strong negative correlation.
- **Gray (0.0)**: no correlation. Parameters near zero can be ignored during tuning.

#### 3. Best Run Summary and Confusion Matrix

The script identifies the single best configuration and generates a confusion matrix for it.

- **Top-Right (False Positives)**: safe inputs flagged incorrectly.
- **Bottom-Left (False Negatives)**: attacks that were not caught.
- **Diagonal (TN/TP)**: correct predictions.

The output folder also contains `summary.txt` listing the exact parameter values used.

## Configuration and Overrides

Rule generation behavior is controlled through a combination of defaults, a configuration file, and CLI overrides. This supports both reproducible builds and rapid experimentation.

The `generation_config.yaml` file defines default settings for `generate` only. It is ignored by `prepare`. The file should be checked into version control to make rule generation auditable and repeatable.

Configuration is resolved in the following order: built-in defaults, then `generation_config.yaml`, then CLI flags and `--set` overrides. CLI values always take precedence and apply only to the current run.

### Configuration Structure

The configuration file is organized into four areas: output settings, metadata, data adapters, and the engine.

Output settings define where rules are written and how they are annotated. Metadata such as tags and rule dates are applied uniformly to all generated rules. Adapter sections describe how adversarial and benign data are loaded when not specified on the CLI. The engine section controls feature extraction and scoring.

### Example Configuration

```yaml
output_path: "rules.yar"

tags:
  - "generated"
  - "prompt_injection"

metadata:
  category: "prompt_injection"
  confidence: "high"

adversarial_adapter:
  type: "jsonl"

benign_adapter:
  type: "jsonl"

engine:
  type: "ngram"
  score_threshold: 0.1
  max_rules_per_run: 50
  rule_date: "2025-10-27"
  min_ngram: 3
  max_ngram: 10
  min_document_frequency: 0.01
  benign_penalty_weight: 1.0
```

### CLI Overrides with --set

The `--set` flag overrides any configuration value using dot notation. Nested structures are created automatically, and values are type-inferred at runtime:

```bash
ymint generate input.jsonl --set engine.score_threshold=0.8
```

Overrides are ephemeral by design and do not affect subsequent runs. For long-lived or shared settings, update the configuration file instead.

The same mechanism passes adapter-specific parameters such as dataset subsets or authentication tokens:

```bash
ymint generate input.jsonl \
  --set adversarial_adapter.config_name=red_team_v2 \
  --set adversarial_adapter.token=hf_123456789
```

Type inference follows simple rules. Boolean values use `true` or `false`. Numeric values are interpreted as integers or floats. All other values are treated as strings. Quoting is only required when the value contains spaces or special characters.

## Engine Tuning and Sensitivity

Engine parameters control how aggressively YaraMint generates rules. Tuning is primarily about balancing coverage against false positives, and small changes can have a large impact on the resulting rule set.

The most important parameter is the score threshold. Higher values produce fewer, more specific rules with lower false-positive risk. Lower values increase sensitivity and coverage but may introduce weaker or more generic signatures. In practice, start by adjusting this value before touching other parameters.

N-gram settings control the size and stability of extracted patterns. Shorter n-grams increase recall but are more likely to collide with benign text. Longer n-grams are more specific but may overfit to narrow phrasing. Default ranges work well for most text-based adversarial datasets and rarely need aggressive adjustment.

Document frequency thresholds determine how common a pattern must be across adversarial samples to be considered stable. Increasing this value favors broadly representative patterns; decreasing it allows rules to capture rarer signals.

The benign penalty weight controls how strongly common benign patterns are suppressed. Increasing it makes the generator more conservative, particularly when benign and adversarial language overlap significantly.

The maximum rule count prevents runaway outputs during experimentation. Fixed rule dates ensure deterministic builds suitable for audits and CI pipelines.

## Metadata and Rule Management

yaramint supports adding metadata to every generated rule, providing context for audits, versioning, and operational workflows.

Tags classify rules by category, source, or purpose. They are applied uniformly to all rules in a generation run and can be specified in the configuration file or via `--tag`:

```bash
ymint generate input.jsonl --tag "experimental" --tag "v1"
```

The rule date ensures deterministic builds and supports reproducible auditing. Set it in the configuration file or override it per run:

```bash
ymint generate input.jsonl --rule-date "2025-01-01"
```

Consistent metadata makes it easier to integrate generated rules with existing YARA rulebases, version control workflows, and automated deployment pipelines.

## Advanced Workflows

Most practitioners treat rule generation as an iterative process:

1. Prepare datasets once and reuse them across multiple runs.
2. Generate an initial rule set.
3. Adjust engine parameters, thresholds, or filters based on output.
4. Regenerate and inspect results.

For large adversarial datasets, streaming directly from remote sources is supported while keeping a local prepared benign dataset. This avoids repeated downloads for the control set while still processing new adversarial data efficiently.

Existing rulebases can be supplied as a baseline to skip regenerating already-covered signatures, enabling incremental updates without overwriting previous work.

## Performance and Scaling

Prepared JSONL datasets are faster to process than repeatedly streaming or parsing raw inputs. Memory usage grows with the size of the adversarial and benign datasets and with the number of candidate patterns extracted.

Streaming remote adversarial datasets is supported but repeated streaming adds overhead. Keeping a local copy for iterative generation is recommended. Reusing a prepared benign dataset avoids repeated processing and ensures consistent scoring across runs.

For very large corpora, processing inputs in smaller batches or increasing available memory helps maintain predictable performance without affecting rule quality.

## Debugging and Common Failure Modes

Most issues come from dataset configuration or parameter choices.

**Empty rule outputs** are usually caused by overly strict thresholds, an empty or misconfigured adversarial dataset, or excessive suppression from the benign corpus. Lower the score threshold or verify input data.

**Too many trivial rules** often result from low thresholds, short n-grams, or sparse benign data. Increase thresholds or raise the minimum n-gram length.

**Benign data leakage** occurs when benign inputs contain adversarial patterns, leading to suppressed rules. Verify that the control set is clean and representative of the content you want to allow.

**Adapter misconfiguration** can produce malformed or empty outputs. Confirm adapter selection, particularly for uncommon formats or Hugging Face streams.

Inspect prepared JSONL outputs and use small test datasets to verify behavior before scaling up.

## Output, Validation, and Integration

YaraMint produces standard `.yar` files that load directly into any YARA-compatible engine. Before deploying to production, validate generated rules by scanning representative benign data to confirm low false positives, and sampling adversarial inputs to verify coverage. Prepared datasets simplify this process by making test data consistent and repeatable.

Generated rules can be integrated into existing rulebases or versioned independently. Metadata such as tags and rule dates supports auditing and deterministic builds.
