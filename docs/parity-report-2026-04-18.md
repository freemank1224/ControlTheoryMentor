# Graphify Parity Report - 2026-04-18

## Outcome

The worker stack is now aligned to the upstream Graphify 0.4.21 pipeline shape for the supported local flow:

- `detect -> extract/build -> cluster -> analyze -> report -> export`
- local heuristic semantic extraction removed
- `generate_graph_task` removed
- task routing reduced to the real PDF processing path
- runtime now fails fast when semantic provider configuration is missing or invalid

## Code Parity

### Replaced local mock behavior

- `worker/graphify_wrapper.py` now orchestrates official Graphify modules plus real model-backed semantic extraction
- `worker/tasks.py` now exposes only the real `process_pdf_task`, `health_check_task`, and `cleanup_old_tasks`
- `worker/celery_app.py` now routes only `worker.tasks.process_pdf_task`

### Provider compatibility

- OpenAI-compatible Chat Completions remains supported
- Anthropic-compatible endpoints are now also supported when `GRAPHIFY_LLM_BASE_URL` contains `/anthropic`
- Verified against Minimax endpoint `https://api.minimaxi.com/anthropic` with model `MiniMax-M2.7`

## Validation

### Automated validation

- Worker unit tests passed: `10 passed`
- Updated tests cover:
  - provider config validation
  - extraction merge/deduplication
  - artifact-oriented PDF processing
  - Celery task behavior
  - Anthropic-compatible semantic extraction branch
  - Anthropic thinking-only response repair path

### Live provider validation

The live semantic path was exercised against a real provider.

#### Full source attempt

- Source: `C:/Users/Dyson/Downloads/ModernControlSystem-12E.pdf`
- Size: 1109 pages
- Result: reached live semantic extraction with Minimax-backed runtime, but full-book completion was not operationally practical in-session because of provider latency and scale

#### Completed bounded regression

- Source sample: `C:/Users/Dyson/Documents/ControlTheoryMentor/pdfs/ModernControlSystem-12E-sample-5p.pdf`
- Output root: `graph_data/graph-regression-sample-1776486632/graphify-out`
- Result: completed successfully with real provider-backed semantic extraction

Observed outputs:

- `graph.json`
- `GRAPH_REPORT.md`
- `cypher.txt`
- `graph.html`
- `manifest.json`
- intermediate `.graphify_*` artifacts

Observed metrics from the completed run:

- nodes: 11
- edges: 19
- communities: 3
- token cost: 1048 input, 1112 output
- Graphify version: 0.4.21

### Container deployment validation

The Docker/Compose deployment path is now wired to the same real runtime inputs used locally:

- root `.env` is injected into `backend` and `worker`
- sample PDFs are mounted into `/app/pdfs`
- graph artifacts are written to `/shared/graph_data`

Container verification steps completed:

- confirmed `GRAPHIFY_LLM_MODEL=MiniMax-M2.7`
- confirmed `GRAPHIFY_LLM_BASE_URL=https://api.minimaxi.com/anthropic`
- confirmed `GRAPHIFY_LLM_ANTHROPIC_THINKING_DISABLED=true`
- confirmed sample PDF exists inside worker container at `/app/pdfs/ModernControlSystem-12E-sample-5p.pdf`

Observed container regressions:

- initial in-container run at `graph_data/graph-docker-regression-sample-1776491070/graphify-out` completed but degraded to 1 node and 0 edges
- after adding an Anthropic repair request for thinking-only responses and rebuilding the worker image, the rerun at `graph_data/graph-docker-regression-sample-r3-1776491439/graphify-out` completed with materially improved output

Observed metrics from the repaired container run:

- nodes: 8
- edges: 13
- communities: 3
- token cost: 1048 input, 866 output
- Graphify version: 0.4.21

This confirms the real container deployment path works end-to-end, not only the local virtual environment path. The remaining issue is output-quality variance for this provider/runtime combination, not missing Docker wiring.

## Remaining Gaps

- Full-book regression for `ModernControlSystem-12E.pdf` is not yet completed end-to-end
- The current worker reports file-level semantic progress, not chunk-level progress, so very large documents are hard to observe during long runs
- Large-document operational tuning is still needed for this provider/model pair
- Container output quality is improved but still below the local bounded regression result (`8/13` vs `11/19`), so provider-specific stability work is still warranted

## Conclusion

Functional parity is achieved for the worker architecture and runtime honesty requirements.

The repository no longer uses a fake Graphify semantic layer. It now runs the upstream Graphify module flow with a real external semantic provider and produces authentic Graphify artifacts.

Docker/Compose deployment has also been validated with the real Minimax-backed runtime. What remains is scale validation and provider-specific operational tuning for very large PDFs, plus quality stabilization under container execution, not a parity gap in the worker design itself.