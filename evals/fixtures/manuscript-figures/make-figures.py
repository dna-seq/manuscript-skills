# /// script
# requires-python = ">=3.11"
# dependencies = ["matplotlib>=3.8"]
# ///
"""Rebuild the figure files of the manuscript-figures fixtures (all fictional). The committed images are
what the cases use; run this only to change them: uv run --script make-figures.py [FOLDER ...]"""
import runpy
import sys
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


SECONDS = HOURS  # devices/: the same run, sampled every 2 s
BUSY = [0.3, 6.2, 11.4, 11.8, 11.9, 11.9, 11.8, 11.9, 11.9, 11.8, 11.9, 11.7, 9.6, 6.1, 3.2, 1.1, 0.2]


def small_runtime_pdf(path: Path) -> None:
    """devices/ Figure 2: drawn one column wide with 7 pt text and placed across the page, where it prints at
    14 pt; in one 85 mm column it would still print at about 6.7 pt."""
    from matplotlib.ticker import FuncFormatter

    fig, ax = plt.subplots(figsize=(3.5, 1.4))
    tools, seconds = ["Varlens", "Server annotator", "Previous pipeline"], [31.4, 940, 5712]
    ax.barh(tools, seconds, color="#2c7fb8")
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:g}"))
    for y, value in enumerate(seconds):
        ax.text(value * 1.15, y, f"{value:g} s", va="center")
    ax.set_xlim(10, 40000)
    ax.set_xlabel("Time to annotate one whole-genome VCF (s)")
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def spacious_memory_pdf(path: Path) -> None:
    """devices/ Figure 3: the memory trace on a canvas more than twice the height its plot needs."""
    fig = plt.figure(figsize=(3.35, 3.6))
    ax = fig.add_axes((0.17, 0.64, 0.78, 0.31))
    ax.plot(SECONDS, MEMORY, color="#2c7fb8")
    ax.set_xlabel("Time since start (s)")
    ax.set_ylabel("Resident memory (GB)")
    fig.savefig(path)
    plt.close(fig)


def busy_threads_pdf(path: Path) -> None:
    """devices/ Figure 4: CPU use during the same run, on the same time axis as Figure 3."""
    fig, ax = plt.subplots(figsize=(3.35, 1.6))
    ax.plot(SECONDS, BUSY, color="#e69f00")
    ax.set_xlabel("Time since start (s)")
    ax.set_ylabel("Busy threads")
    ax.set_ylim(0, 12.5)
    fig.tight_layout()
    fig.savefig(path)
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


def build(folder: str) -> None:
    """One fixture folder's figures, so a change to one does not redraw the others."""
    if folder in ("seeded", "clean"):
        runpy.run_path(str(HERE / folder / "code" / "plot_runtime.py"))
        report(HERE / folder / "figures" / "figure-1-report.png")
    if folder == "seeded":
        memory(HERE / "seeded" / "figures" / "figure-4-memory.png")
        sweep(HERE / "seeded" / "figures" / "figure-3-threads.png", ("#d62728", "#2ca02c"))
    if folder == "clean":
        memory(HERE / "clean" / "figures" / "figure-3-memory.png")
        sweep(HERE / "clean" / "figures" / "figure-s1-threads.png", ("#0072b2", "#e69f00"))
    if folder == "latex":
        tiny_runtime_pdf(HERE / "latex" / "figures" / "runtime.pdf")
        sweep(HERE / "latex" / "figures" / "threads.pdf", ("#0072b2", "#e69f00"), width=7.0)
        memory(HERE / "latex" / "figures" / "memory.pdf")
    if folder == "devices":
        (HERE / "devices" / "figures").mkdir(parents=True, exist_ok=True)
        report(HERE / "devices" / "figures" / "report.png")
        small_runtime_pdf(HERE / "devices" / "figures" / "runtime.pdf")
        spacious_memory_pdf(HERE / "devices" / "figures" / "memory.pdf")
        busy_threads_pdf(HERE / "devices" / "figures" / "threads.pdf")


for name in sys.argv[1:] or ("seeded", "clean", "latex", "devices"):
    build(name)
