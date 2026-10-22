# /// script
# requires-python = ">=3.11"
# dependencies = ["typer>=0.12", "pillow>=10", "pymupdf>=1.24,<2"]  # 2.x adds onnxruntime and numpy; 1.x is one wheel
# ///
"""Find a manuscript's figures and show each one at the size it will be printed.

    uv run --script figures.py inventory PAPER.md --output-dir RUN/manuscript-figures/figures
    uv run --script figures.py inventory main.tex --output-dir OUT --column-mm 89 --min-pt 7
    uv run --script figures.py workspace PAPER.md --into SEAT_WORKSPACE/figures

Looking at a figure is the reviewer's job; this script does only what looking cannot. A model or a person
sees pixels, not millimetres: a 3,000-pixel plot looks sharp on screen and its labels may print at 4 pt in
an 85 mm column. So `inventory` reads a Markdown or LaTeX manuscript (following \\input and \\include),
finds each figure's files, caption and label, and writes for each figure:

- `view.png`: the figure at 300 dpi at its printed width, to look at the details;
- `sheet.png`: the figure at its printed size (the column width, or the page width for a `figure*`) at
  150 dpi, in colour, in greyscale and as people with red-green colour blindness see it (deuteranopia and
  protanopia, simulated after Machado et al. 2009), to judge legibility, greyscale print and colour choice.

It measures the smallest text and the thinnest line as printed, exactly, where a PDF or SVG keeps them as
vectors (a raster's text is judged on the sheet), and the resolution of a raster at its printed width. It
lists every citation of each figure with its section and line, and figures never cited, first cited out of
order, or cited but absent. `figures.json` holds the records, `figures.md` lists them with the screening
notes: each a place to look, not a verdict.

`workspace` gives a simulated referee or reader the figures as PNG images with an index of numbers,
captions and file names, and nothing else, so the seat looks for itself.

Exit codes: 0 when the files were written, 1 when outputs already exist, 2 for a usage error.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any

import typer
from PIL import Image, ImageDraw, ImageFont, ImageOps

app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__.split("\n\n")[0])

RASTER = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".gif", ".webp", ".bmp"}
VECTOR = {".pdf", ".svg"}
POSTSCRIPT = {".eps", ".ps"}
TRY_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg", ".tif", ".tiff")
VIEW_DPI, PRINT_DPI = 300, 150
# Machado, Oliveira & Fernandes (2009), severity 1.0, applied to linear RGB.
CVD = {
    "Deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "Protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
}


# ---------- reading the manuscript ----------

@dataclass
class Source:
    path: Path
    text: str  # comments and code blocks blanked to spaces, so offsets stay put
    kind: str  # markdown | latex
    pieces: list[tuple[int, Path, int]]  # (offset in text, file, offset in that file) where each stretch starts

    def where(self, offset: int) -> str:
        start, path, local = next(p for p in reversed(self.pieces) if p[0] <= offset)
        original = path.read_text(encoding="utf-8", errors="replace")
        return f"{path.name} line {original.count(chr(10), 0, local + offset - start) + 1}"


@dataclass
class Figure:
    number: str  # "2", "S1", or "" when the manuscript gives none
    order: int
    start: int  # the span of the figure and its caption in the text
    end: int
    files: list[str] = field(default_factory=list)
    caption: str = ""
    labels: list[str] = field(default_factory=list)
    wide: bool = False

    @property
    def id(self) -> str:
        return f"Figure {self.number}" if self.number else f"Unnumbered figure {self.order}"

    @property
    def slug(self) -> str:
        return f"figure-{self.number.lower()}" if self.number else f"figure-u{self.order}"


def blank(text: str, pattern: re.Pattern[str]) -> str:
    """Spaces in place of every match (newlines kept), so offsets and line numbers stay as in the file."""
    return pattern.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


MD_HIDDEN = re.compile(r"<!--.*?-->|^\s{0,3}(`{3,}|~{3,})[^\n]*\n.*?^\s{0,3}\1[^\n]*$", re.S | re.M)
TEX_HIDDEN = re.compile(r"(?<!\\)%[^\n]*|\\begin\{(verbatim|lstlisting|minted|comment)\}.*?\\end\{\1\}", re.S)
TEX_INPUT = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")


def read_latex(path: Path, at: int = 0, depth: int = 0) -> tuple[str, list[tuple[int, Path, int]]]:
    """The source with \\input and \\include inlined, and where each stretch came from."""
    text = blank(path.read_text(encoding="utf-8", errors="replace"), TEX_HIDDEN)
    out, pieces, done = [], [], 0
    for match in TEX_INPUT.finditer(text):
        child = path.parent / match.group(1).strip()
        child = child if child.suffix == ".tex" else child.with_name(child.name + ".tex")
        if depth >= 6 or not child.is_file():
            continue
        pieces.append((at, path, done))
        out.append(text[done:match.start()])
        at += match.start() - done
        child_text, child_pieces = read_latex(child, at, depth + 1)
        out.append(child_text)
        pieces += child_pieces
        at += len(child_text)
        done = match.end()
    pieces.append((at, path, done))
    out.append(text[done:])
    return "".join(out), pieces


def read_source(paper: Path) -> Source:
    if paper.suffix.lower() == ".tex":
        text, pieces = read_latex(paper)
        return Source(paper, text, "latex", pieces)
    return Source(paper, blank(paper.read_text(encoding="utf-8", errors="replace"), MD_HIDDEN), "markdown", [(0, paper, 0)])


def latex_plain(text: str) -> str:
    """LaTeX reduced to the words a reader sees: enough to read a caption, not to typeset it."""
    text = re.sub(r"\\label\{[^}]*\}", "", text).replace("~", " ").replace("\\%", "%").replace("\\&", "&").replace("--", "–")
    for _ in range(3):
        text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
    return re.sub(r"\s+", " ", re.sub(r"\\[a-zA-Z]+\*?|[{}$]", "", text)).strip()


def braced(text: str, at: int) -> str:
    """The contents of the balanced {...} group that starts at or after `at`."""
    start, depth = text.find("{", at), 0
    for i in range(max(start, 0), len(text)):
        depth += {"{": 1, "}": -1}.get(text[i], 0) if text[i - 1] != "\\" else 0
        if depth == 0:
            return text[start + 1:i]
    return text[start + 1:]


MD_IMAGE = re.compile(r"!\[(?P<alt>(?:[^\[\]]|\[[^\]]*\])*)\]\(\s*<?(?P<src>[^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)(?P<attrs>\{[^}]*\})?"
                      r"|<img\b[^>]*?\bsrc=[\"'](?P<html>[^\"']+)[\"']", re.I)


def caption_number(block: str) -> str | None:
    """The number a caption gives itself ("**Figure 2.**", "Figure S1:", "Supplementary Figure 3."). A sentence
    that starts "Figure 2 shows" is not a caption: a caption's label is set off by markup or punctuation."""
    m = re.match(r"^\s*(?P<open>[*_]{1,2})?\s*(?P<supp>Supplementary\s+)?(?:Figure|Fig\.?)\s*(?P<num>S?\d+)\s*(?P<punct>[.:|])?",
                 block, re.I)
    if not m or not (m.group("open") or m.group("punct")):
        return None
    number = m.group("num").upper()
    return f"S{number}" if m.group("supp") and not number.startswith("S") else number


def parse_markdown(source: Source) -> list[Figure]:
    """A paragraph with images is a figure; its caption is the paragraph after it (or before it) that starts
    "Figure N", else the image's alt text."""
    paragraphs = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"(?:[^\n]*\S[^\n]*(?:\n|$))+", source.text)]
    figures: list[Figure] = []
    for index, (start, end, block) in enumerate(paragraphs):
        images = list(MD_IMAGE.finditer(block))
        if not images:
            continue
        figure = Figure("", len(figures) + 1, start, end, files=[m.group("src") or m.group("html") for m in images])
        figure.labels = [l for m in images for l in re.findall(r"#(fig[:\-][\w:.\-]+)", m.group("attrs") or "")]
        around = [i for i in (index + 1, index - 1) if 0 <= i < len(paragraphs) and caption_number(paragraphs[i][2]) is not None
                  and not MD_IMAGE.search(paragraphs[i][2]) and not any(f.start <= paragraphs[i][0] < f.end for f in figures)]
        if around:
            cap_start, cap_end, caption = paragraphs[around[0]]
            figure.caption, figure.number = caption.strip(), caption_number(caption) or ""
            figure.start, figure.end = min(start, cap_start), max(end, cap_end)
        elif len(images) == 1 and (images[0].group("alt") or "").strip():
            figure.caption = images[0].group("alt").strip()
            figure.number = caption_number(figure.caption) or ""
        figures.append(figure)
    if figures and not any(f.number for f in figures):
        for n, figure in enumerate(figures, 1):  # numbered in order of appearance, as pandoc does
            figure.number = str(n)
    return figures


TEX_FIGURE = re.compile(r"\\begin\{(?P<env>figure\*?|SCfigure\*?|wrapfigure)\}(?P<body>.*?)\\end\{(?P=env)\}", re.S)
TEX_GRAPHICS = re.compile(r"\\(?:includegraphics|includesvg)\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
TEX_SUPPLEMENT = re.compile(r"\\renewcommand\s*\{?\\thefigure\}?\s*\{\s*S")


def parse_latex(source: Source) -> list[Figure]:
    """Each figure environment, numbered in order; after \\renewcommand{\\thefigure}{S...} they are S1, S2..."""
    switch = next((m.start() for m in TEX_SUPPLEMENT.finditer(source.text)), len(source.text))
    figures, counts = [], {"": 0, "S": 0}
    for match in TEX_FIGURE.finditer(source.text):
        body, prefix = match.group("body"), "S" if match.start() > switch else ""
        counts[prefix] += 1
        figure = Figure(f"{prefix}{counts[prefix]}", len(figures) + 1, match.start(), match.end(),
                        files=[f.strip() for f in TEX_GRAPHICS.findall(body)], labels=re.findall(r"\\label\{([^}]+)\}", body),
                        wide=match.group("env").endswith("*"))
        if caption := re.search(r"\\caption\*?\s*(?:\[[^\]]*\])?", body):
            figure.caption = latex_plain(braced(body, caption.end()))
        figures.append(figure)
    return figures


def resolve(name: str, source: Source) -> Path | None:
    """The figure file, beside the manuscript or in a \\graphicspath folder; LaTeX may leave out the extension."""
    dirs = [source.path.parent] + [source.path.parent / d for m in re.finditer(r"\\graphicspath\s*\{((?:\{[^}]*\})+)\}", source.text)
                                   for d in re.findall(r"\{([^}]*)\}", m.group(1))]
    name = name.replace("%20", " ")
    for folder in dirs:
        base = folder / name
        for candidate in [base, *(base.with_name(base.name + ext) for ext in TRY_EXTENSIONS)]:
            if candidate.is_file():
                return candidate.resolve()
    return None


# ---------- citations ----------

TEXT_CITE = re.compile(r"(?P<supp>Supplementary\s+)?(?:Figures?|Figs?\.?)\s*(?P<list>S?\d+[a-zA-Z]?(?:\s*(?:[-–—]|,|and|&)\s*S?\d+[a-zA-Z]?)*)", re.I)
REF_CITE = re.compile(r"\\(?:c|C|auto|sub|name)?ref\*?\{([^}]+)\}|@(fig[:\-][\w:.\-]+)")
HEADING = {"markdown": re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.M),
           "latex": re.compile(r"\\(?:sub)*section\*?\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}")}


def cited_numbers(supp: bool, listing: str) -> list[str]:
    """"2", "2a, 3", "2–4", "S1 and S3" as figure numbers; a range counts every figure in it."""
    parts, numbers = re.findall(r"S?\d+|[-–—]", listing, re.I), []
    for i, part in enumerate(parts):
        if part in "-–—" and 0 < i < len(parts) - 1:
            lo, hi = int(parts[i - 1].lstrip("Ss")), int(parts[i + 1].lstrip("Ss"))
            prefix = "S" if parts[i + 1].upper().startswith("S") else ""
            numbers += [f"{prefix}{n}" for n in range(lo + 1, hi) if hi - lo < 30]
        elif part not in "-–—":
            number = part.upper()
            numbers.append(f"S{number}" if supp and not number.startswith("S") else number)
    return numbers


def citations(source: Source, figures: list[Figure]) -> list[dict]:
    """Every mention of a figure outside its own caption, in text order, with its section and line."""
    by_number = {f.number: f for f in figures if f.number}
    by_label = {label: f for f in figures for label in f.labels}
    heads = [(m.start(), latex_plain(m.group(1)) if source.kind == "latex" else re.sub(r"[*_`]", "", m.group(1)))
             for m in HEADING[source.kind].finditer(source.text)]
    found = []

    def add(number: str, figure: Figure | None, at: int, label: str = "") -> None:
        if figure is not None and figure.start <= at < figure.end:
            return  # the caption's own "Figure 2."
        caption = next((f.id for f in figures if f.start <= at < f.end), "")
        found.append({"id": figure.id if figure else (number if label else f"Figure {number}"), "exists": figure is not None, "offset": at,
                      "label": label, "in_caption_of": caption, "where": source.where(at),
                      "section": next((t for s, t in reversed(heads) if s <= at), "Before the first heading")})

    for m in TEXT_CITE.finditer(source.text):
        for number in cited_numbers(bool(m.group("supp")), m.group("list")):
            add(number, by_number.get(number), m.start())
    for m in REF_CITE.finditer(source.text):
        for label in (x.strip() for x in (m.group(1) or m.group(2)).split(",")):
            if label in by_label or label.startswith("fig"):  # a section, table or equation label is not ours
                add(label, by_label.get(label), m.start(), label)
    return sorted(found, key=lambda c: c["offset"])


def citation_problems(figures: list[Figure], cites: list[dict]) -> list[dict]:
    """Figures never cited in the text, cited only in another caption, first cited out of order, or cited but absent."""
    body = [c for c in cites if c["exists"] and not c["in_caption_of"]]
    first: dict[str, dict] = {}
    for c in body:
        first.setdefault(c["id"], c)
    notes = []
    for figure in figures:
        if figure.id not in first:
            captions = sorted({c["in_caption_of"] for c in cites if c["id"] == figure.id and c["in_caption_of"]})
            notes.append({"check": "citation", "figure": figure.id, "note": f"{figure.id} is cited only in the caption of {', '.join(captions)}, never in the text."
                          if captions else f"{figure.id} is never cited in the text."})
    main = sorted((f for f in figures if f.number.isdigit() and f.id in first), key=lambda f: first[f.id]["offset"])
    for i, figure in enumerate(main):
        if lower := [g for g in main[i + 1:] if int(g.number) < int(figure.number)]:
            c = first[figure.id]
            notes.append({"check": "citation", "figure": figure.id,
                          "note": f"{figure.id} is first cited before {lower[0].id} ({c['section']}, {c['where']})."})
    for c in cites:
        if not c["exists"] and not any(n["figure"] == c["id"] and n["note"].startswith("The text cites") for n in notes):
            what = f"a figure labelled {c['label']}" if c["label"] else c["id"]
            notes.append({"check": "citation", "figure": c["id"], "note": f"The text cites {what}, which does not exist ({c['section']}, {c['where']})."})
    return notes


# ---------- rendering and measuring ----------

@dataclass
class Page:
    path: Path
    page: int  # 1-based
    vector: bool
    width_pt: float = 0.0  # a vector page's width
    pixels: tuple[int, int] = (0, 0)


def pages_of(path: Path, scratch: Path) -> tuple[list[Page], str]:
    """The renderable pages of a figure file, or none and the reason."""
    suffix = path.suffix.lower()
    if suffix in POSTSCRIPT:
        target = scratch / f"{path.stem}.from-eps.pdf"
        if not shutil.which("gs") or subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-dEPSCrop", "-sDEVICE=pdfwrite",
                                                     f"-sOutputFile={target}", str(path)], capture_output=True, timeout=120).returncode:
            return [], "an EPS file needs Ghostscript (gs) to render, and it is missing or failed"
        path, suffix = target, ".pdf"
    if suffix in VECTOR:
        import pymupdf

        try:
            with pymupdf.open(str(path)) as doc:
                return [Page(path, n + 1, True, width_pt=doc[n].rect.width) for n in range(doc.page_count)], ""
        except Exception as exc:  # a damaged file: report it and go on
            return [], f"could not be opened ({exc})"
    if suffix in RASTER:
        try:
            with Image.open(path) as image:
                return [Page(path, 1, False, pixels=image.size)], ""
        except OSError as exc:
            return [], f"could not be opened ({exc})"
    return [], f"{suffix or 'a file without an extension'} is not an image format this script renders"


def render(page: Page, width_px: int) -> Image.Image:
    """The page `width_px` pixels wide, on white."""
    if page.vector:
        import pymupdf

        with pymupdf.open(str(page.path)) as doc:
            zoom = width_px / doc[page.page - 1].rect.width
            pix = doc[page.page - 1].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    with Image.open(page.path) as source:
        image = source.convert("RGBA")
    flat = Image.new("RGBA", image.size, "white")
    flat.alpha_composite(image)
    return flat.convert("RGB").resize((width_px, max(1, round(image.height * width_px / image.width))), Image.Resampling.LANCZOS)


def vector_sizes(page: Page, scale: float) -> dict[str, Any]:
    """The smallest text and the thinnest stroked line of a vector page, in points as printed."""
    import pymupdf

    with pymupdf.open(str(page.path)) as doc:
        target = doc[page.page - 1]
        spans = sorted((round(span["size"] * scale, 1), span["text"].strip()) for block in target.get_text("dict")["blocks"]
                       for line in block.get("lines", []) for span in line["spans"] if span["text"].strip())
        try:
            widths = [d["width"] * scale for d in target.get_drawings()[:20000] if d.get("width") and "s" in (d.get("type") or "")]
        except Exception:  # unusual drawings: the line weight stays unmeasured
            widths = []
    return {"min_text_pt": spans[0][0] if spans else None, "smallest_text": [{"pt": s, "text": t} for s, t in spans[:4]],
            "min_line_pt": round(min(widths), 2) if widths else None}


def simulated(image: Image.Image, matrix: tuple) -> Image.Image:
    lin = [round(((v / 255) / 12.92 if v <= 10 else (((v / 255) + 0.055) / 1.055) ** 2.4) * 255) for v in range(256)] * 3
    srgb = [round((12.92 * (v / 255) if v <= 1 else 1.055 * (v / 255) ** (1 / 2.4) - 0.055) * 255) for v in range(256)] * 3
    return image.point(lin).convert("RGB", tuple(x for row in matrix for x in (*row, 0.0))).point(srgb)


def sheet(printed: Image.Image, width_mm: float) -> Image.Image:
    """The printed size in colour, in greyscale and under the two red-green colour blindnesses, two by two."""
    tiles = [(printed, f"As printed, {width_mm:g} mm wide"), (ImageOps.grayscale(printed).convert("RGB"), "Greyscale"),
             *((simulated(printed, matrix), f"{name} (simulated)") for name, matrix in CVD.items())]
    pad, head, (w, h) = 12, 22, printed.size
    canvas = Image.new("RGB", (2 * w + 3 * pad, 2 * (h + head) + 3 * pad), (236, 236, 232))
    draw = ImageDraw.Draw(canvas)
    try:
        label = ImageFont.load_default(size=14)
    except TypeError:  # Pillow before 10.1 has only the bitmap font
        label = ImageFont.load_default()
    for n, (tile, text) in enumerate(tiles):
        x, y = pad + (n % 2) * (w + pad), pad + (n // 2) * (h + head + pad)
        draw.text((x, y), text, fill=(30, 30, 30), font=label)
        canvas.paste(tile, (x, y + head))
    return canvas


def measure(page: Page, folder: Path, width_mm: float, settings: dict) -> tuple[dict, list[str]]:
    """Write view.png and sheet.png for one page and measure it as printed; return the record and the notes."""
    folder.mkdir(parents=True, exist_ok=True)
    render(page, round(width_mm / 25.4 * VIEW_DPI)).save(folder / "view.png")
    sheet(render(page, round(width_mm / 25.4 * PRINT_DPI)), width_mm).save(folder / "sheet.png")
    record: dict[str, Any] = {"page": page.page, "vector": page.vector}
    notes = []
    if page.vector:
        record |= vector_sizes(page, width_mm / 25.4 * 72 / page.width_pt)
        if record["min_text_pt"] is None:
            notes.append("holds no text (drawn as outlines), so its size was not measured: judge it on the sheet")
        elif record["min_text_pt"] < settings["min_pt"]:
            words = ", ".join(f"“{s['text'][:30]}” {s['pt']:g} pt" for s in record["smallest_text"][:3])
            notes.append(f"has text as small as {record['min_text_pt']:g} pt printed {width_mm:g} mm wide ({words}); the minimum used is {settings['min_pt']:g} pt")
        if record["min_line_pt"] is not None and record["min_line_pt"] < settings["min_line_pt"]:
            notes.append(f"has lines as thin as {record['min_line_pt']:g} pt printed {width_mm:g} mm wide; the minimum used is {settings['min_line_pt']:g} pt")
    else:
        record |= {"pixels": list(page.pixels), "dpi": round(page.pixels[0] / (width_mm / 25.4))}
        if record["dpi"] < settings["min_dpi"]:
            notes.append(f"is {page.pixels[0]} pixels wide, {record['dpi']} dpi printed {width_mm:g} mm wide; the minimum used is {settings['min_dpi']} dpi")
    return record, notes


# ---------- commands ----------

def refuse_existing(path: Path) -> None:
    if path.exists():
        typer.echo(f"{path} exists; write this attempt to a new folder so the earlier one stays.", err=True)
        raise typer.Exit(1)


def find_figures(paper: Path) -> tuple[Source, list[Figure]]:
    source = read_source(paper)
    return source, parse_latex(source) if source.kind == "latex" else parse_markdown(source)


@app.command()
def inventory(
    paper: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="The manuscript, Markdown or LaTeX")],
    output_dir: Annotated[Path, typer.Option("--output-dir", help="Where the images, figures.json and figures.md go")],
    column_mm: Annotated[float, typer.Option(help="The venue's single-column width, mm")] = 85.0,
    page_mm: Annotated[float, typer.Option(help="The venue's full-page width, for a figure that spans the page, mm")] = 178.0,
    min_pt: Annotated[float, typer.Option(help="The smallest printed text the venue allows, pt")] = 6.0,
    min_line_pt: Annotated[float, typer.Option(help="The thinnest printed line to accept, pt")] = 0.25,
    min_dpi: Annotated[int, typer.Option(help="The lowest resolution of a raster image as printed, dpi")] = 300,
) -> None:
    """Find every figure, render it as printed, measure it, and list its citations."""
    refuse_existing(output_dir / "figures.json")
    source, figures = find_figures(paper)
    settings = {"column_mm": column_mm, "page_mm": page_mm, "min_pt": min_pt, "min_line_pt": min_line_pt, "min_dpi": min_dpi}
    cites = citations(source, figures)
    records, notes = [], citation_problems(figures, cites)
    for figure in figures:
        width_mm = page_mm if figure.wide else column_mm
        files = []
        for name in figure.files:
            path = resolve(name, source)
            pages, problem = pages_of(path, output_dir) if path else ([], "was not found")
            if problem:
                files.append({"path": name, "problem": problem})
                notes.append({"check": "file", "figure": figure.id, "note": f"{figure.id}: {name} {problem}."})
            for page in pages:
                folder = output_dir / figure.slug / (path.stem if len(figure.files) > 1 else "") / (f"page-{page.page}" if len(pages) > 1 else "")
                measured, problems = measure(page, folder, width_mm, settings)
                at = f"{name}, page {page.page}" if len(pages) > 1 else name
                notes += [{"check": "size", "figure": figure.id, "note": f"{figure.id}: {at} {p}."} for p in problems]
                files.append({"path": name, **measured, "view": (folder / "view.png").relative_to(output_dir).as_posix(),
                              "sheet": (folder / "sheet.png").relative_to(output_dir).as_posix()})
        own = [c for c in cites if c["id"] == figure.id]
        records.append({"id": figure.id, "label": figure.labels[0] if figure.labels else "", "caption": figure.caption,
                        "where": source.where(figure.start), "printed_mm": width_mm,
                        "printed_width": "page (figure*)" if figure.wide else "column", "files": files,
                        "cited": [{k: c[k] for k in ("section", "where", "in_caption_of")} for c in own]})
    for leftover in output_dir.glob("*.from-eps.pdf"):
        leftover.unlink()
    document = {"paper": str(paper), "settings": settings, "figures": records, "findings": notes}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "figures.json").write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "figures.md").write_text(markdown(document), encoding="utf-8")
    typer.echo(json.dumps({"output_dir": str(output_dir.resolve()), "figures": len(records), "notes": len(notes)}, indent=2))


def markdown(document: dict) -> str:
    s = document["settings"]
    lines = [f"# Figures of {Path(document['paper']).name}", "",
             f"Measured printed {s['column_mm']:g} mm wide (one column; {s['page_mm']:g} mm for a figure that spans the page), "
             f"against {s['min_pt']:g} pt text, {s['min_line_pt']:g} pt lines and {s['min_dpi']} dpi. Open each sheet: it is the "
             "figure at its printed size, in greyscale and under red-green colour blindness. Every note is a place to look.", ""]
    for r in document["figures"]:
        lines += [f"## {r['id']}" + (f" ({r['label']})" if r["label"] else ""), "", f"- Where: {r['where']}; printed {r['printed_mm']:g} mm wide",
                  f"- Caption: {' '.join(r['caption'].split()) or '(none found)'}"]
        for f in r["files"]:
            if "problem" in f:
                lines.append(f"- {f['path']}: {f['problem']}")
                continue
            size = (f"smallest text {f['min_text_pt']:g} pt" if f.get("min_text_pt") else "no vector text") if f["vector"] \
                else f"{f['dpi']} dpi as printed"
            line = f"; thinnest line {f['min_line_pt']:g} pt" if f.get("min_line_pt") is not None else ""
            lines.append(f"- {f['path']}" + (f" page {f['page']}" if f["page"] > 1 else "") + f": {size}{line}. [sheet]({f['sheet']}), [view]({f['view']})")
        body = [c for c in r["cited"] if not c["in_caption_of"]]
        lines.append(f"- Cited {'once' if len(body) == 1 else f'{len(body)} times'} in the text" + (f", first in {body[0]['section']} ({body[0]['where']})" if body else ""))
        lines += [f"- Note: {n['note']}" for n in document["findings"] if n["figure"] == r["id"]] + [""]
    if other := [n for n in document["findings"] if n["figure"] not in {r["id"] for r in document["figures"]}]:
        lines += ["## Citations of figures that do not exist", ""] + [f"- {n['note']}" for n in other] + [""]
    return "\n".join(lines)


@app.command()
def workspace(
    paper: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="The manuscript the seat reads")],
    into: Annotated[Path, typer.Option("--into", help="The seat workspace's figures folder")],
    width: Annotated[int, typer.Option(help="Width of each image, pixels")] = 1600,
) -> None:
    """Put the figures in a simulated referee's or reader's workspace: a PNG per figure (per file or page of a
    multi-part one) and index.md with each figure's number, caption and images. No measurement, no note."""
    refuse_existing(into / "index.md")
    into.mkdir(parents=True, exist_ok=True)
    source, figures = find_figures(paper)
    lines = ["# Figures", "", "Each figure of the manuscript as an image. Open one when your reading reaches it, as you would look at it on the page.", ""]
    for figure in figures:
        names = []
        for n, name in enumerate(figure.files, 1):
            path = resolve(name, source)
            for page in (pages_of(path, into)[0] if path else []):
                target = into / (figure.slug + (f"-{n}" if len(figure.files) > 1 else "") + (f"-p{page.page}" if page.page > 1 else "") + ".png")
                render(page, width if page.vector else min(width, page.pixels[0])).save(target)
                names.append(target.name)
        lines.append(f"- **{figure.id}**: " + (", ".join(f"`{n}`" for n in names) or "(no image)") + (f". {' '.join(figure.caption.split())}" if figure.caption else ""))
    for leftover in into.glob("*.from-eps.pdf"):
        leftover.unlink()
    (into / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    typer.echo(json.dumps({"into": str(into.resolve()), "images": sorted(p.name for p in into.glob("*.png"))}, indent=2))


if __name__ == "__main__":
    app()
