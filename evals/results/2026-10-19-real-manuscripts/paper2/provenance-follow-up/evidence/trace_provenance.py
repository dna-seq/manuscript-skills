"""Retain the evidence behind the bounded paper2 evaluation provenance check."""

import csv
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

REPO = Path('/home/antonkulaga/sources/just-module-creator')
HERE = Path(__file__).resolve().parent
ROUND_INTRO = 'fab4db5c0f1369dee6ad44b8eb36da410b365087'
ROUND_COMPLETE = '221b95f6c187f852e68449c4f815bed20bbba49e'


def git(*args: str) -> str:
    return subprocess.run(['git', *args], cwd=REPO, check=True,
                          capture_output=True, text=True).stdout


def main() -> None:
    commits = {}
    for label, commit in [('round-introduced', ROUND_INTRO), ('round-completed', ROUND_COMPLETE)]:
        body = git('show', '--format=fuller', commit, '--', 'docs/manuscript/manuscript.tex')
        (HERE / f'{label}.git-show.txt').write_text(body)
        project = git('show', f'{commit}:pyproject.toml')
        version = next(line for line in project.splitlines() if line.startswith('version ='))
        commits[label] = {'commit': commit, 'version_declaration': version}

    files = git('ls-files', 'assets/benchmarks/sirt6', 'docs/BENCHMARKING.md',
                'docs/manuscript/claw-bio-inspired-benchmark.md',
                'src/just_module_creator/bench.py', 'scripts/bench_score.py').splitlines()
    hashes = []
    for name in files:
        source = REPO / name
        destination = HERE / 'source-bundle' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        hashes.append({'path': name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()})

    raw = json.loads((HERE.parent / 'commands/0006.stdout.txt').read_text())
    comparison = []
    for result in raw:
        variants = result['variants']
        citations = result['citations']
        direction = result['direction']
        comparison.append({
            'preparation_run': str(Path(result['run']).relative_to(REPO)),
            'rsid_recall': variants['rsid_recall'],
            'recovered_pairs': variants['recovered_pairs'],
            'expected_pairs': variants['expected_pairs'],
            'pair_recall': variants['pair_recall'],
            'decoy_rate': variants['decoy_rate'],
            'citation_recall': citations['recall'],
            'citation_identity_accuracy': citations['accuracy'],
            'citation_resolver': citations['resolver'],
            'both_asserted': direction['both_asserted'],
            'agreeing_direction': direction['agreeing'],
            'direction_agreement': direction['agreement'],
        })
    with (HERE / 'preparation-scores.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison[0]))
        writer.writeheader()
        writer.writerows(comparison)

    history_names = sorted(set(git('log', '--all', '--name-only', '--format=').splitlines()))
    retained_names = [name for name in history_names
                      if any(token in name for token in ('repro-bench', 'run-sirt6', 'benchmarks/sirt6'))]
    (HERE / 'history-paths.txt').write_text('\n'.join(retained_names) + '\n')
    search_roots = [REPO / name for name in ('assets', 'data', 'docs', '.claude')]
    search_roots.extend(Path('/home/antonkulaga/sources/just-dna-lite') / name
                        for name in ('data', 'docs'))
    matches = []
    for root in search_roots:
        for path in root.rglob('*'):
            if any(token in path.name.lower() for token in ('sirt6', 'repro-bench')):
                matches.append(str(path))
    transcript_root = Path('/home/antonkulaga/.claude/projects/-home-antonkulaga-sources-just-module-creator')
    summary = {
        'repository': str(REPO), 'checkout': git('rev-parse', 'HEAD').strip(),
        'historical_round': commits,
        'interpretation': 'Manuscript runs 1/2/3 intentionally replace preparation a/b/a2. '
                          'Different scores alone are not a numerical contradiction.',
        'raw_later_round': 'not_found_in_searched_locations',
        'historical_archive_path': 'data/interim/repro-bench-2/',
        'historical_archive_exists_here': (REPO / 'data/interim/repro-bench-2').exists(),
        'searched_roots': [str(path) for path in search_roots],
        'matching_paths': sorted(set(matches)),
        'local_project_transcript_count': len(list(transcript_root.rglob('*.jsonl'))),
        'search_limit': 'Current local checkout, locally available Git refs, listed connected folders '
                        'and this project transcript directory. No remote original-machine archive '
                        'or inaccessible Claude session was retrieved.',
        'preparation_scores': comparison,
        'source_hashes': hashes,
    }
    (HERE / 'provenance.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({key: summary[key] for key in (
        'checkout', 'historical_round', 'interpretation', 'raw_later_round',
        'historical_archive_exists_here', 'local_project_transcript_count',
        'preparation_scores')}, indent=2))


if __name__ == '__main__':
    main()
