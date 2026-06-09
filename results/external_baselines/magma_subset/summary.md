# Magma External Baseline Subset

- Subset size: 18
- VulRepair function-level inputs extracted: 18/18
- VulRepair status: completed
- VulRepair predictions: {'prediction_count': 18, 'nonempty_predictions': 18, 's2sv_encoded_predictions': 18, 'code_like_predictions': 8, 'directly_applicable_unified_diffs': 0, 'direct_project_patch_rate': 0.0, 'interpretation': 'VulRepair completed function-level inference, but its artifact emits S2SV edit-script predictions. These are not directly applicable project-level patches without the original dataset-specific de-preprocessing and patch reconstruction step.'}
- CPR/ExtractFix status: compatibility_assessed
- CPR/ExtractFix applicability: {'not_applicable_without_custom_harness': 18}

## Notes

- VulRepair is evaluated as a function-level neural AVR baseline because its artifact expects localized vulnerable functions.
- CPR/ExtractFix require tool-specific crash inputs, KLEE-compatible bitcode, repair specifications, and crash constraints; cases lacking these are recorded as not applicable rather than failed repairs.
