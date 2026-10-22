"""Figure 2: annotation time of one whole-genome VCF, per tool."""
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
rows = list(csv.DictReader(open(HERE / "../data/runtime.csv")))
tools = ["Varlens", "Server annotator", "Previous pipeline"]
seconds = {t: [float(r["seconds"]) for r in rows if r["tool"] == t] for t in tools}
values = [sorted(seconds[t])[len(seconds[t]) // 2] for t in tools]

plt.rcParams.update({"font.size": 7, "pdf.fonttype": 42})
fig, ax = plt.subplots(figsize=(3.35, 1.9))
bars = ax.barh(tools, values, color=["#2c7fb8", "#9ecae1", "#c6dbef"])
for bar, value in zip(bars, values):
    ax.text(value * 1.05, bar.get_y() + bar.get_height() / 2, f"{value:.1f} s", va="center")
ax.set_xscale("log")
ax.set_xlabel("Time to annotate one whole-genome VCF (s)")
fig.tight_layout()
fig.savefig(HERE / "../figures/figure-2-runtime.png", dpi=600)
