# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib>=3.8"]
# ///
"""Rebuild the figure files of the manuscript-figures fixtures (all fictional). The committed images are
what the cases use; run this only to change them: uv run --script make-figures.py"""
import runpy
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
plt.rcParams.update({"font.size": 7, "pdf.fonttype": 42, "svg.fonttype": "none"})
THREADS = list(range(1, 13))
WALL = [212, 118, 84, 66, 55, 48, 44, 41, 40, 39, 39, 39]
CPU = [205, 214, 219, 224, 228, 231, 236, 240, 243, 246, 249, 251]
HOURS = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32]
MEMORY = [0.4, 1.1, 1.6, 1.8, 1.9, 1.9, 2.0, 2.0, 2.1, 2.1, 2.0, 1.9, 1.6, 1.2, 0.9, 0.6, 0.4]


def report(path: Path) -> None:
    """Figure 1: one row of a report as a user sees it."""
    plt.rcParams.update({"font.size": 7})
    fig, ax = plt.subplots(figsize=(3.35, 1.3))
    ax.axis("off")
    rows = [("Variant", "rs2802292 (FOXO3), genotype G/T"), ("Annotation", "Longevity association, 5 studies"),
            ("Evidence", "Willcox 2008; Flachsbart 2009; +3"), ("Caveat", "Associations, not a diagnosis")]
    for n, (key, value) in enumerate(rows):
        ax.text(0.0, 0.85 - n * 0.24, key, weight="bold", transform=ax.transAxes)
        ax.text(0.28, 0.85 - n * 0.24, value, transform=ax.transAxes)
    fig.savefig(path, dpi=600, bbox_inches="tight")
    plt.close(fig)


def sweep(path: Path, colours: tuple[str, str], width: float = 3.35) -> None:
    """The thread-pool sweep: wall-clock and CPU time for 1 to 12 threads."""
    fig, ax = plt.subplots(figsize=(width, 2.0))
    ax.plot(THREADS, WALL, color=colours[0], label="Wall-clock time")
    ax.plot(THREADS, CPU, color=colours[1], label="CPU time")
    ax.set_xlabel("Threads")
    ax.set_ylabel("Time (s)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=600)
    plt.close(fig)


def memory(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(3.35, 1.8))
    ax.plot(HOURS, MEMORY, color="#2c7fb8")
    ax.set_xlabel("Time since start (s)")
    ax.set_ylabel("Resident memory (GB)")
    fig.tight_layout()
    fig.savefig(path, dpi=600)
    plt.close(fig)


def tiny_runtime_pdf(path: Path) -> None:
    """The LaTeX fixture's runtime figure: drawn on a 16-inch canvas, so its 9 pt text prints at about 2 pt."""
    plt.rcParams.update({"font.size": 9})
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.barh(["Varlens", "Server annotator", "Previous pipeline"], [31.4, 940, 5712], color="#2c7fb8")
    ax.set_xscale("log")
    ax.set_xlabel("Time to annotate one whole-genome VCF (s)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    plt.rcParams.update({"font.size": 7})


for folder in ("seeded", "clean"):
    runpy.run_path(str(HERE / folder / "code" / "plot_runtime.py"))
    report(HERE / folder / "figures" / "figure-1-report.png")
memory(HERE / "seeded" / "figures" / "figure-4-memory.png")
memory(HERE / "clean" / "figures" / "figure-3-memory.png")
sweep(HERE / "seeded" / "figures" / "figure-3-threads.png", ("#d62728", "#2ca02c"))
sweep(HERE / "clean" / "figures" / "figure-s1-threads.png", ("#0072b2", "#e69f00"))
tiny_runtime_pdf(HERE / "latex" / "figures" / "runtime.pdf")
sweep(HERE / "latex" / "figures" / "threads.pdf", ("#0072b2", "#e69f00"), width=7.0)
memory(HERE / "latex" / "figures" / "memory.pdf")
