"""Generates deterministic sample + edge-case datasets. Run: python data/generate_samples.py"""
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
REGIONS = ["North", "South", "East", "West"]
MONTHS = list(range(1, 13))
# product: (revenue per sales row, monthly cost, category)
PRODUCTS = {
    "Laptop Pro": (50_000, 100_000, "Computing"),
    "Phone X": (20_000, 60_000, "Mobile"),
    "Tablet Z": (15_000, 45_000, "Mobile"),
    "Monitor M": (9_000, 20_000, "Peripherals"),
    "Keyboard K": (2_000, 3_000, "Peripherals"),
}


def build_sales() -> pd.DataFrame:
    rows = []
    for p, (rev, _, _) in PRODUCTS.items():
        for m in MONTHS:
            for r in REGIONS:
                rows.append({"Date": f"2025-{m:02d}-15", "Product": p, "Region": r,
                             "Revenue": rev, "Units": max(1, rev // 1000)})
    df = pd.DataFrame(rows)
    # one Laptop Pro spike so total Laptop Pro revenue = 2,440,000 (profit = 12,40,000)
    idx = df[df.Product == "Laptop Pro"].index[0]
    df.loc[idx, "Revenue"] = 90_000
    return df


def build_costs() -> pd.DataFrame:
    # monthly product cost split evenly across the 4 regions (all splits are whole numbers)
    return pd.DataFrame([{"Date": f"2025-{m:02d}-28", "Product": p, "Region": r, "Cost": c // len(REGIONS)}
                         for p, (_, c, _) in PRODUCTS.items() for m in MONTHS for r in REGIONS])


def build_products() -> pd.DataFrame:
    return pd.DataFrame([{"Product": p, "Category": cat} for p, (_, _, cat) in PRODUCTS.items()])


def main():
    sales, costs, products = build_sales(), build_costs(), build_products()
    sales.to_csv(HERE / "sample/sales.csv", index=False)
    costs.to_csv(HERE / "sample/costs.csv", index=False)
    products.to_excel(HERE / "sample/products.xlsx", index=False)

    e = HERE / "edge_cases"
    pd.concat([sales, sales.head(37)]).to_csv(e / "sales_duplicates.csv", index=False)
    m = sales.copy()
    m.loc[m.index[:10], "Revenue"] = None
    m.to_csv(e / "sales_missing.csv", index=False)
    amb = sales.copy()
    amb["Date"] = [f"{(i % 12) + 1:02d}/{(i % 11) + 1:02d}/2025" for i in range(len(amb))]
    amb.to_csv(e / "sales_ambiguous_dates.csv", index=False)
    pd.DataFrame({"Product": list(PRODUCTS), "Revenue": [55_000] * 5}).to_excel(e / "report_conflict.xlsx", index=False)
    pd.DataFrame({"Product": list(PRODUCTS), "Revenue": [50_000] * 5}).to_excel(e / "sales_summary.xlsx", index=False)


if __name__ == "__main__":
    main()
