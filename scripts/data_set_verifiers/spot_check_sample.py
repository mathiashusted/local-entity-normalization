# Spot-check sample for the independent chemical verification (ruleset §7)
# Written by: Claude Opus 5.5, 01.10.2026. Prompt: "complete code for the stratified spot-check sample".
# Inputs: control.csv; stratum rule and flagged ids decided in conversation.
# Stratum rule: "the name carries an explicit stereo or isomer qualifier" -> stereo;
# name ends in "-ate" or names a salt/ion -> charge; everything else -> plain.
# Fixes before the final draw: added (+)/(-)/(±)/dl- markers; added r)/s) for locant forms like (6R).
import os
import pandas as pd

CONTROL_PATH = "../../data/dataset/control.csv"
SAMPLE_PATH = "../../results/verification/spot_check_sample.csv"
SEED = 42
PER_STRATUM = 7

control = pd.read_csv(CONTROL_PATH, sep=",", dtype=str, keep_default_na=False)

# Chemicals with a CID (CTRL-170 phosphatidylcholine has none and is the documented §7 exception)
chem = control[(control["entity_type"] == "chemical") & (control["pubchem_id"] != "")].copy()
assert len(chem) == 108, f"Expected 108 control chemicals with a CID, found {len(chem)}"

flagged_ids = ["CTRL-160", "CTRL-153", "CTRL-135", "CTRL-169"]  # myo-inositol, lactose, EPA, PBS
for flagged_id in flagged_ids:
    assert flagged_id in set(chem["id"]), f"Flagged row {flagged_id} not found"

STEREO_MARKERS = ["d-", "l-", "dl-", "(s)", "(r)", "r)", "s)", "(+)", "(-)", "(±)",
                  "cis", "trans", "alpha", "beta", "myo-"]

def stratum(name):
    lowered = name.lower()
    for marker in STEREO_MARKERS:
        if marker in lowered:
            return "stereo"
    if lowered.endswith("ate") or "sodium" in lowered or "chloride" in lowered:
        return "charge"
    return "plain"

chem["stratum"] = chem["canonical_name"].apply(stratum)

# Manual corrections of proxy labels, decided after reading the full list below, BEFORE sampling
manual_strata = {}  # e.g. {"CTRL-xxx": "stereo"}
for row_id, label in manual_strata.items():
    assert row_id in set(chem["id"]), f"Manual override for unknown id {row_id}"
    chem.loc[chem["id"] == row_id, "stratum"] = label

# Full label list for the one manual pass
print("Stratum labels for all 108 chemicals:")
for row in chem.sort_values(["stratum", "id"]).itertuples():
    print(f"  {row.stratum:7} {row.id}  {row.canonical_name}")

# Stratum sizes (needed for the report: "7 of N")
print("\nStratum sizes (all chemicals):")
print(chem["stratum"].value_counts().to_string())

# Draw: flagged rows deliberately, then up to PER_STRATUM random rows per stratum
rest = chem[~chem["id"].isin(flagged_ids)]
parts = [chem[chem["id"].isin(flagged_ids)].assign(stratum="flagged")]
for name in ["stereo", "charge", "plain"]:
    pool = rest[rest["stratum"] == name]
    n = min(PER_STRATUM, len(pool))
    parts.append(pool.sample(n=n, random_state=SEED))

spot_check = pd.concat(parts, ignore_index=True)
spot_check = spot_check[["id", "canonical_name", "pubchem_id", "stratum"]]

# Empty columns for the manual check
for column in ["pubchem_inchikey", "independent_source", "independent_id",
               "independent_inchikey", "verdict", "comment"]:
    spot_check[column] = ""

print(f"\nSample ({len(spot_check)} rows, seed {SEED}):")
print(spot_check[["id", "canonical_name", "pubchem_id", "stratum"]].to_string(index=False))

# Freeze: never overwrite an existing sample
assert not os.path.exists(SAMPLE_PATH), f"{SAMPLE_PATH} exists already; the sample is frozen"
os.makedirs(os.path.dirname(SAMPLE_PATH), exist_ok=True)
spot_check.to_csv(SAMPLE_PATH, index=False)
print(f"\nSaved to {SAMPLE_PATH}")
