# Actual source-bundle registration failure

The first registration loop stopped on this real input:

```text
evidence/source-bundle/assets/benchmarks/sirt6/reference/README.md
```

The helper's `artifact` function rejected any path whose basename was `README.md`:

```text
ValueError: Use an evidence filename inside its skill folder; README.md is the generated status index.
```

The coordinating registration process raised `subprocess.CalledProcessError` with exit 1.
Previously registered evidence remained intact. This failure was observed while retaining the real
SIRT6 module documentation, not from a fixture-based smoke run.

The generated index occupies only `RUN/SKILL/README.md`, so forbidding nested source READMEs was
unnecessary. A new regression test retained original module documentation beneath
`evidence/module/README.md` while protecting the generated root index, including an alias containing
`..`. It failed against the original helper: [actual failed test](../commands/0014.stdout.txt).
The helper now compares the resolved target with the generated index path. Source documentation can
be retained with its original filename; the index remains protected. The retry keeps the original
input bytes and hashes rather than renaming or dropping their README files.
