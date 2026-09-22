import pandas as pd
import sys
import json
import time
import urllib.request
import urllib.error
from urllib.parse import quote

# The cross verifier acts as a final check that benchmark.csv and control.csv are consistent with each other
# It verifies that all entities in the benchmark.csv have an entry in the control.csv and that no entries
# from control.csv have no entries in benchmark.csv.
# The entities are matched over the canonical_name, which is the only column that should always have a match
# Finally, the entities' IDs are once again verified against the API


def main():
    benchmark_data = pd.read_csv("benchmark/benchmark.csv", dtype=str)
    control_data = pd.read_csv("benchmark/control.csv", dtype=str)

    assert "canonical_name" in benchmark_data.columns and "canonical_name" in control_data.columns

    control_ids = dict(zip(control_data["canonical_name"], control_data["accepted_id"]))
    mismatches = 0
    empty_name_cols = 0

    for id, canonical_name, accepted_id in zip(benchmark_data["id"], benchmark_data["canonical_name"], benchmark_data["accepted_id"]):
        if pd.isna(canonical_name):
            empty_name_cols += 1
            continue
        control_id = control_ids.get(canonical_name)
        match = accepted_id == control_id
        if not match:
            mismatches += 1
            print(f"Mismatch on id {id} with name: {canonical_name} - benchmark_id={accepted_id}, control_id={control_id}")
    print(f"Number of mismatches: {mismatches}, empty name columns: {empty_name_cols}")
    print(f"Continuing with control.csv...")

    not_found = 0

    for id, canonical_name in zip(control_data["id"], control_data["canonical_name"]):
        assert not pd.isna(canonical_name) # The control.csv file must have all name columns filled in

        matches = benchmark_data[benchmark_data["canonical_name"] == canonical_name]
        if matches.empty:
            not_found += 1
            print(f"No match found for id {id} with name {canonical_name}")
            continue

    print(f"Number of control entities not found in benchmark: {not_found}")




if __name__ == "__main__":
    main()
