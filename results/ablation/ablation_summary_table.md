| Dataset | Variant | Records | Completed | Success | Success Rate | Failed | Main Claims |
|---|---|---:|---:|---:|---:|---:|---|
| arvo | Full BugRC | 266 | 266 | 266 | 100.0% | 0 | - |
| arvo | w/o causality chain | 266 | 266 | 257 | 96.6% | 0 | official_incomplete_bugrc_blocks=257, official_and_bugrc_both_cut_path=7, bugrc_better_but_needs_validation=2 |
| arvo | w/o CVE/pattern prior | 266 | 265 | 238 | 89.5% | 1 | - |
| arvo | w/o project prior | 266 | 265 | 234 | 88.0% | 1 | - |
| arvo | LLM-only root cause | 266 | 266 | 234 | 88.0% | 0 | official_incomplete_bugrc_blocks=234, official_and_bugrc_both_cut_path=18, not_enough_evidence=9, bugrc_better_but_needs_validation=5 |
| arvo | Trigger-site baseline | 266 | 266 | 236 | 88.7% | 0 | official_incomplete_bugrc_blocks=236, official_and_bugrc_both_cut_path=10, not_enough_evidence=16, bugrc_better_but_needs_validation=4 |
| magma | Full BugRC | 138 | 138 | 131 | 94.9% | 0 | bugrc_blocks_better_than_magma_reference=14, bugrc_matches_ground_truth=117, bugrc_incomplete=7 |
| magma | w/o causality chain | 138 | 138 | 126 | 91.3% | 0 | bugrc_blocks_better_than_magma_reference=16, bugrc_matches_ground_truth=110, bugrc_incomplete=11, not_enough_evidence=1 |
| magma | w/o CVE/pattern prior | 138 | 138 | 127 | 92.0% | 0 | bugrc_matches_ground_truth=114, bugrc_incomplete=10, bugrc_blocks_better_than_magma_reference=13, not_enough_evidence=1 |
| magma | w/o project prior | 138 | 138 | 127 | 92.0% | 0 | bugrc_matches_ground_truth=117, bugrc_incomplete=10, bugrc_blocks_better_than_magma_reference=10, not_enough_evidence=1 |
| magma | LLM-only root cause | 138 | 138 | 119 | 86.2% | 0 | bugrc_matches_ground_truth=115, bugrc_incomplete=19, bugrc_blocks_better_than_magma_reference=4 |
| magma | Trigger-site baseline | 138 | 138 | 90 | 65.2% | 0 | bugrc_matches_ground_truth=88, bugrc_incomplete=44, not_enough_evidence=4, bugrc_blocks_better_than_magma_reference=2 |
