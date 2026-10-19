"""Score a benchmark run. The logic is `just_module_creator.bench`; this is argv.

    uv run python scripts/bench_score.py REFERENCE_SPEC RUN_SPEC [RUN_SPEC ...]
    uv run python scripts/bench_score.py --census RUN_SPEC [RUN_SPEC ...]

The module moved into `src/` so it could be tested and type-checked: `scripts/` is
in neither `testpaths` nor pyright's `include`, which is why a `TypeError` on the
first unkeyed table sat here unnoticed. This file stays because the argv contract
is the one the round's already-produced numbers were generated against.
"""

from __future__ import annotations

import sys

from just_module_creator.bench import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
