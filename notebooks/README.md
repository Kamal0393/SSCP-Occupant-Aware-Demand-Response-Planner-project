# Reproducible planning experiment

`baseline_vs_optimized_experiment.ipynb` compares the existing deterministic baseline strategy with the OR-Tools optimized strategy using `data/synthetic_demo.json` from Gap 1. It selects the generated overloaded transformer and reads the seed, target, and dataset counts from sample metadata. The checked-in notebook has executed outputs from the backend virtual environment; it uses the project's `ComparisonService`, `PlanningService`, `PlanningAnalysisService`, `ExplanationService`, and solver.

## Run the notebook

Jupyter is an optional interactive tool and is not added to the project's runtime requirements. From the repository root, activate the backend environment and install the notebook kernel if needed:

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m pip install jupyter ipykernel
python -m ipykernel install --user --name sscp-planner --display-name "Python (SSCP planner)"
cd ..
jupyter notebook notebooks/baseline_vs_optimized_experiment.ipynb
```

Select the `Python (SSCP planner)` kernel. The notebook locates `backend/` and `data/` relative to the repository root, validates that the JSON matches its recorded seed and generation parameters, then regenerates the same domain dataset before running the comparison. The sample uses seed `2026`, 4 transformers, 16 buildings, 1 occupant and 4 appliances per building, and 96 fifteen-minute intervals per profile.

## What it measures

The result table reports the uncontrolled event peak, baseline and optimized post-dispatch peaks, absolute and percentage reduction, target, strict target status, comfort score/impact, estimated TOU cost change, decision counts, opted-out building protection, and the actual OR-Tools status. A counterfactual clears the opted-out flag only to show how much dispatch the strategy would otherwise assign to that building; it is clearly identified as counterfactual.

The event-profile visualization is built as inline SVG from the profile and strategy decisions, using the existing analysis service's event-slot calculation. No plotting package is added.

## Error analysis and limitations

The notebook executes an excessive target and a transformer rating whose required relief exceeds available load; both currently return `infeasible_reduction_capacity` status tags in decisions rather than raising `InsufficientReductionCapacityError`. It checks that missing tariff rates leave the plan available while the analysis reports no cost estimate, and that an emergency override without a token returns HTTP 403 with `UnauthorizedOverrideError`.

`OccupancySensorFailureError` is declared, but occupancy patterns are not part of `PlanningContext` or the current planning API input, so that sensor failure cannot be exercised in the planning flow. The notebook documents this gap and also describes solver scale, generated-load assumptions, comfort proxy limits, and the one-transformer/one-seed experiment size. Its measured target shortfall is retained instead of being rounded into a success.
