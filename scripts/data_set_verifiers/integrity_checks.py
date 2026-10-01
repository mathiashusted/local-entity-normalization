# Integrity checks for benchmark.csv and control.csv (ruleset §8)
#
# Provenance
# Tool: Claude Opus 5.5 (Anthropic), 01.10.2026
# Prompt: "Write the new script. Make it only check the absolutely necessary. Do not check anything
#          that the cross verifier already has. Only add your stuff in a new script."
# Inputs: Ruleset.md (chapter: integrity constraints), cross_verifier.py (author's own script),
#         benchmark.csv, control.csv
#
# Purpose
# During manual editing, two rows were emptied instead of deleted: one benchmark row (GENE-152) and
# one control row (CTRL-109, TP53). An emptied row is still read as a row, so neither my
# cross_verifier.py nor the notebook checks noticed it. This script closes that gap. It complements
# cross_verifier.py, which checks that benchmark and control agree with each other (constraints 2
# and 10), and checks each file on its own:
#   - every row has an id, and no id occurs twice (constraints 1 and 14);
#   - every row has an entity type, either "chemical" or "gene" (constraint 6);
#   - a row has an empty canonical name and an empty accepted ID if and only if it has no
#     recoverable target, i.e. id_status = "none" (constraint 4).
# The script lists every violation with its row id and stops with an error if any are found.
#
# Testing and result
# Tested on the two damaged file versions described above: it reported both emptied rows.
# Run on the corrected benchmark.csv (319 rows) and control.csv (189 rows) on 01.10.2026:
# no violations.

import pandas as pd
BENCHMARK_PATH = "../../data/data set/benchmark.csv"
CONTROL_PATH = "../../data/data set/control.csv"


def main():
    benchmark = pd.read_csv(BENCHMARK_PATH, dtype=str, keep_default_na=False)
    control = pd.read_csv(CONTROL_PATH, dtype=str, keep_default_na=False)
    errors = []

    # Constraints 1, 6, 14: every row has a unique, non-empty id and a valid entity_type
    for name, data in [("benchmark", benchmark), ("control", control)]:
        for row in data.itertuples():
            if row.id == "":
                errors.append(f"{name}: row {row.Index} has an empty id (cleared row?)")
            if row.entity_type not in ["chemical", "gene"]:
                errors.append(f"{name} {row.id}: entity_type is '{row.entity_type}'")
        duplicated_ids = data[data["id"].duplicated() & (data["id"] != "")]["id"]
        for duplicate in duplicated_ids:
            errors.append(f"{name}: id {duplicate} occurs more than once")

    # Constraint 4: canonical_name and accepted_id are empty if and only if id_status = none
    for row in benchmark.itertuples():
        is_none = row.id_status == "none"
        is_empty = row.canonical_name == "" and row.accepted_id == ""
        if is_none != is_empty:
            errors.append(f"benchmark {row.id}: id_status is '{row.id_status}', "
                          f"but canonical_name/accepted_id emptiness disagrees")

    print(f"Checked {len(benchmark)} benchmark rows and {len(control)} control rows: {len(errors)} violations")
    for error in errors:
        print("  " + error)
    assert len(errors) == 0, "Integrity checks failed"


if __name__ == "__main__":
    main()
