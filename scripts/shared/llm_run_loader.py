import pandas as pd



def load_run(path, arm, benchmark):
    df = pd.read_csv(path, dtype=str, keep_default_na=False)

    assert len(df) == len(benchmark), f"The dataframe {path} does not have length 319. Check the benchmark matches up"
    assert (df["Arm"] == arm).all(), "Arn not defined on all runs!"

    df.insert(0, "id", None)
    for idx, row in df.iterrows():
        bench_row = benchmark.iloc[idx]
        # Add the ID
        assert bench_row["input"] == row["Input Entity"], f"{path} on row {idx} differs from benchmark"
        df.loc[idx, 'id'] = bench_row["id"]

    assert df["id"].is_unique
    return df