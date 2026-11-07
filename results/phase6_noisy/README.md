# results/phase6_noisy: the Phase 6 summaries before the Phase 8.3 re-run

These files are byte-for-byte copies of the files of the same name in `results/` as they were at commit `dcd9fd0`
(the merge of pull request 1; the `results/` tree is identical at `90c5aae`, the last Phase 8.7 commit). They were taken with
`git show dcd9fd0:results/<name> > results/phase6_noisy/<name>` and each copy was checked against the git blob id
(`git rev-parse dcd9fd0:results/<name>` equals `git hash-object results/phase6_noisy/<name>`).

They summarize the Phase 6 benchmark matrix: session `run_1792350994`, run on 2026-10-19 while the machine was noisy at the start
(idle baseline of the session 0.843 CPU-s/s, quiet calibration baseline 0.131 CPU-s/s, canary_max 0.0689 on cores 0 and 1 and 0.0369 on core 0,
curve rate 32000 pps). Commit `2c3126d` (Phase 8.3) overwrote `results/summary.*`, `results/verdicts.md`, `results/exclusions.md`,
`results/runs.json`, `results/figures_data.json`, `results/baseline_calibration.json`, `results/calibration.json` and `results/bench_plan.tsv`
and replaced the raw logs under `logs/bench_*.log` and `logs/attempts/` with the Phase 8.3 logs. The Phase 6 raw logs are only in git history
(for example `git show dcd9fd0:logs/bench_A_nm_64_1.log`). See `DEVIATIONS.md` entries D8.19 to D8.25.

Nothing in this folder was recomputed. Do not edit these files.

| file | sha256 |
|---|---|
| summary.md | f46b5fff682bb1e67e6b51e33f782ecca45a00699dd3da2f465c3700d26cc36f |
| summary.json | 0c7ebe74111d20f098c576a848dec4e83a66e8025d173ff1f02bb35873d6a4fe |
| verdicts.md | 6aed64525a743e8006479cb46c119ceaf34dd6718aacaf6fd0c2b7baca2d93c9 |
| exclusions.md | 80a212dac90c7ed63fad26bd5a73ed28317db7679ce3a6ee5ce92633d3472ffc |
| runs.json | d4861d8a3154e3b49e0f9a3296092d3d06f0e6df26820b602f79bab5800d8d78 |
| figures_data.json | 0fbb190455b86b74cd75a53a06787cf4437cd7908ea0ca3ad87d73951e68f8ea |
| baseline_calibration.json | 81ec04ff6d2d090db65f7517654e4283efef829381be431b91da8677c5cd1ada |
| calibration.json | 0a28ad36d0fe46a7d20dd4adc5f644fa345f8b384867190452321782f4ffc07f |
| bench_plan.tsv | d66618595cfee2e847831c3bbd87814c436cb7096b7d3a56b64b44c9eca92f8b |
| fig_cpu_cost.png | a925c054234c2c4e2657ae1368bc6f5a5d5d753ceca47be916b010abe9c993c5 |
| fig_drop_rate.png | 54d299c5db34335cf29ba3992e42134f0e84c713f694ef7988f514b2ccb33d3e |
