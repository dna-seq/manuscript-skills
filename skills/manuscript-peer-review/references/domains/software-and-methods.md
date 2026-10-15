# Domain module: software and methods

Questions for the `software-methods` seat, and for the reproducibility seat when the paper presents or
benchmarks software. They are reviewer questions, not a checklist: a thin README is a concern only when
a claim (usability, reproducibility, availability) depends on it.

## Load it when

- the design is `software-tool`, `method-benchmark` or `database-resource`;
- or the paper presents a tool, package, pipeline, web service, model or database as its contribution,
  benchmarks methods, or makes claims about speed, scalability, usability or ease of installation.

## Do not load it when

- the study only used standard software to reach a scientific result: versions and parameters are then
  the reproducibility seat's ordinary questions;
- the paper's only software content is a code availability statement for an analysis; the
  reproducibility seat and manuscript-reporting-check cover that.

## What the seat checks from the paper and its links

Work from the manuscript, its supplementary files and what its links show without installing anything.
Opening a public repository page or package index entry to read its README, licence and release list is
fine for the authors' own draft; in invited-referee mode, only when the venue's review process provides
the link for that purpose.

- **Documentation.** Is there enough to use the tool for the paper's stated purpose: installation,
  inputs and outputs, parameters with defaults, a worked example?
- **Installability.** Through which route (PyPI, Bioconda, CRAN or Bioconductor, a container image, a
  web service)? Are dependencies pinned or bounded? Which operating systems are claimed, and is that
  claim tested? A platform list in an availability statement is optional (polish) unless a headline
  claim depends on it.
- **Tests.** Is there a test suite and test data with expected outputs? Is it run automatically?
- **Licence.** Is a licence stated in the paper and in the repository, and do they agree? Is it an
  open licence if the paper says "open source"? Data and model weights may carry separate terms.
- **Versioned archive.** Is the exact version described in the paper archived (a Zenodo or Software
  Heritage record, a tagged release) and named in the paper? A moving branch cannot reproduce a table.
- **Comparison with existing tools.** Which tools were compared and why those? Is the obvious comparator
  present? Same inputs, versions stated, defaults or tuning applied equally (the authors' own tool tuned
  while others run on defaults is an unfair comparison), runtime and memory measured on the same
  hardware with the hardware stated?
- **Test data.** Are the benchmark data public, versioned and of a realistic size and type? Synthetic
  data alone cannot support claims about real data.
- **Claims about use.** "Scalable", "fast", "user-friendly", "easy to install": each needs a
  measurement, a comparison or a user study, or should be stated more narrowly.
- **Maintenance.** Who maintains it and how users report problems, when the paper invites adoption.

## What the seat does not demand

- A graphical interface, a particular language or framework, or support for every platform, unless the
  paper claims it.
- Comparison with every tool in the field. The comparators a referee will expect are the widely used
  ones for the same task and any the paper claims to beat.
- Superiority, when the contribution is something else (speed, transparency, a new data type).

## Running the authors' code

Only when the authors ask for it (or, in invited-referee mode, when the user asks and the venue's
review process supplies the code for review). Then:

- Ask before installing third-party code; it executes with the user's permissions.
- Use a sandbox: a container or virtual machine, or at least a fresh environment in a scratch directory,
  with no credentials, no access to the user's other files and no network beyond what installation
  needs.
- Use the paper's or repository's documented instructions and the test data they supply; never the
  user's private data.
- Record what ran: the version or commit, the commands, the environment and the output. A failure is a
  finding only if it reproduces from the documented instructions; quote the instruction that failed.
- Results from a run are evidence for adjudication. They never replace the paper's numbers, and a
  difference is reported as a difference, not corrected.

If the code was not run, say so under "What this review did not have".
