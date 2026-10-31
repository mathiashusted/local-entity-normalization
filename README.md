# Normalizing noisy biomedical entity names with small local LLMs

Code and data for the Bachelor thesis *Evaluation of local, CPU-capable LLMs for biomedical entity normalization under noisy input conditions* (Bioinformatics, FU Berlin).

Isolated, noisy entity names (no surrounding text) are normalized to identifiers: chemicals to a PubChem CID, human genes to an HGNC ID. Two research questions are addressed:

- **RQ1:** How reliably do small local models normalize noisy names, compared with non-neural lookup methods (floor) and a cloud model (ceiling)?
- **RQ2:** How often does generating a name and an identifier at the same time yield fabricated or inconsistent identifiers? Does separating the steps avoid this, and what does it cost in abstentions?

## Design

A noisy **benchmark** (319 rows) and a clean **control set** (189 entities) carry the gold identifiers. A deterministic **retrieval layer** (`scripts/shared/b3_resolver.py`) maps a name to an ID: PubChem PUG REST must return exactly one distinct CID, otherwise the layer abstains; HGNC is queried for exact, case-insensitive matches over symbol, previous symbol, alias symbol, name, previous name and alias name (in this order), approved entries only. Every API response is stored in a single JSONL cache, so lookups are reproducible offline.

Three **baselines** are provided: B1 (exact and case-folded lookup in local PubChem/HGNC snapshots), B2 (RapidFuzz fuzzy matching against the same snapshots) and B3 (the retrieval layer applied directly to the noisy input; arm C). The **LLM runs** use Gemma 4 E2B, Gemma 4 E4B, Phi-4-mini and Qwen3.5 4B via Ollama (CPU only), with Gemini 3.6 Flash as cloud reference. In **arm A** the model generates name and identifier; in **arm B** it generates only the name and the retrieval layer supplies the ID; **arm C** uses no model. Inference is done by a TypeScript fork of [ECO-ID](https://github.com/mathiashusted/ECO-ID) (commit `141dac29c0e06380e58d04482ff88f94b719111e`), which is not part of this repository; its raw outputs are stored in `results/llm/`. Outcomes are assigned by `decide()` in `scripts/shared/scoring.py`; for arm A, identifier format, existence and agreement with the predicted name are additionally checked. Reported are ID, name and entity-type accuracy, fabrication, inconsistency and abstention rates, Wilson 95 % intervals and exact McNemar tests.

## Layout

| Path | Content |
| --- | --- |
| `data/dataset/` | `benchmark.csv`, `control.csv`, `benchmark.txt` (plain list of the benchmark inputs) |
| `data/cache/api.jsonl` | Cached PubChem/HGNC responses, one JSON object per line, keyed by URL |
| `data/reference/` | Local PubChem and HGNC snapshots (git-ignored) |
| `scripts/shared/` | `b3_resolver.py` (retrieval layer and cache), `scoring.py` (`decide()`, Wilson interval), `llm_run_loader.py` |
| `scripts/baseline/` | `baseline{1,2,3}_generation.ipynb`, `baseline_evaluation.ipynb` |
| `scripts/llm/` | `llm_generation_a.ipynb`, `llm_generation_b.ipynb` (ID resolution/verification), `llm_evaluation.ipynb` |
| `scripts/final/` | `results.ipynb`: final tables, McNemar tests, failure analysis, figures |
| `scripts/data_set_verifiers/` | Dataset checks: `resolution_auditor.py`, `name_to_id_matcher.py`, `cross_verifier.py`, `integrity_checks.py`, `spot_check_sample.py` |
| `results/` | `baselines/`, `intermediate/`, `llm/` (raw `eco-id-results-*.csv`, `resolved/`), `final/` (`baselines.csv`, `llm_arm_a.csv`, `llm_arm_b.csv`, `failure_analysis_decisions.csv`, figures), `verification/` |

## Reproduction

**Requirements:** Python 3.12 or newer, Jupyter, `pandas`, `rapidfuzz`, `statsmodels`, `matplotlib` and `requests` (one cell in B3). No versions are pinned. For the model runs, the [fork of ECO-ID](https://github.com/mathiashusted/ECO-ID) with Ollama integration is required . Ollama 0.34.4 with the tags `gemma4:e2b`, `gemma4:e4b`, `phi4-mini:3.8b` and `qwen3.5:4b` (`ollama pull <tag>`) is required, running on the CPU (check with `ollama ps`); Gemini is accessed via its API.

**Order:** Each notebook is run top to bottom from its own directory, since paths are relative (`../../`).

1. Place the PubChem/HGNC snapshots in `data/reference/` (needed for B1 and B2 only).
2. `scripts/baseline/`: `baseline1_generation`, `baseline2_generation`, `baseline3_generation`, then `baseline_evaluation` (writes `results/final/baselines.csv`).
3. Run the models with the ECO-ID fork, producing `results/llm/eco-id-results-{A,B}-<model>.csv` (the files are included).
4. `scripts/llm/`: `llm_generation_a`, `llm_generation_b`, then `llm_evaluation` (writes `results/final/llm_arm_{a,b}.csv`).
5. `scripts/final/results.ipynb`.

Network lookups are served from `data/cache/api.jsonl` where possible; only uncached URLs are requested from the live APIs and appended to the cache.

## Data and sources

PubChem (CID-Title, CID-Synonym-filtered, CID-MeSH; [Extras](https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/)) and HGNC ([complete set](https://www.genenames.org/download/)) snapshots were downloaded on 2026-09-20 and are not included because of their size. The API cache was fetched between 2026-10-13 and 2026-10-29. The benchmark was seeded from [ECO-ID Supplementary Table S1](https://github.com/khabatv/ECO-ID-Supplementary/blob/main/Supplementary%20Table%20S1.csv). Details are given in the thesis: [link TODO].

## License and AI use

This repository is released under the [MIT License](LICENSE). The PubChem and HGNC data, the cached API responses and the ECO-ID material remain subject to their respective providers' terms.

Parts of the code were created using generative AI. AI use is declared in each file or notebook cell where applicable.