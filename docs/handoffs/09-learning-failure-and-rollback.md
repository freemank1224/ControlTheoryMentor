# P4 Learning Failure and Rollback Strategy

## Purpose

Define the minimum safe fallback strategy when P4 learning loop behaviors fail in runtime.

## Failure Categories

### 1. Learning API unavailable

Symptoms:

1. `POST /api/learning/track` fails
2. `GET /api/learning/progress` fails
3. `POST /api/learning/feedback` fails

Immediate actions:

1. Keep tutor session flow running (learning calls are non-blocking for tutoring UX)
2. Surface non-fatal warning in logs/UI
3. Verify backend and Redis connectivity
4. Check `GET /api/learning/metrics` and inspect `lastStatusCode` / `lastErrorCode` for `track`, `progress`, `feedback`

### 2. Redis transient outage

Symptoms:

1. Redis ping fails
2. Learning progress temporarily not persisted to primary store

Current mitigation in code:

1. `FailoverLearningService` switches to in-memory fallback
2. After Redis recovery, fallback data is synced back to primary store before switching backend

Operational checks:

1. check backend logs for fallback mode entry and exit
2. call `GET /api/learning/progress` before and after Redis recovery to confirm no data loss
3. call `GET /api/learning/metrics` to verify `errorCodeMapping` and recent `LEARNING_STORE_UNAVAILABLE` traces

### 4. Error code mapping drift

Symptoms:

1. error responses missing `detail.code`
2. operations cannot correlate failures with learning API categories

Immediate actions:

1. verify learning route still exports `errorCodeMapping` via `/api/learning/metrics`
2. verify `track` / `progress` / `feedback` failures map to expected codes (`LEARNING_STORE_UNAVAILABLE`, `LEARNING_*_FAILED`)
3. run learning integration tests to catch regressions in mapping behavior

### 3. Frontend personalization inconsistency

Symptoms:

1. tutor session starts but learning panel empty for existing learner
2. pending review concepts not shown

Immediate actions:

1. verify learner id being sent from frontend start request
2. verify backend response metadata contains `learningSnapshot`
3. re-fetch progress with same learner+graph pair

## Rollback Levels

### Level 0: No rollback (preferred)

Use when only learning side-effects fail while tutoring core remains healthy.

Actions:

1. keep learning APIs enabled
2. keep tutor APIs enabled
3. patch and redeploy targeted fix

### Level 1: Disable frontend learning controls

Use when learning endpoints are unstable but tutor endpoints are stable.

Actions:

1. hide/disable feedback and progress widgets in tutor page
2. keep learnerId optional in requests
3. continue tutor step orchestration

Expected impact:

1. tutoring still works
2. progress loop temporarily paused

### Level 2: Disable tutor-learning bridge events

Use when backend learning service causes runtime instability.

Actions:

1. guard tutor-side event tracking calls (no hard failure)
2. keep tutor session endpoints serving without learning event writes
3. preserve ability to re-enable bridge after fix

Expected impact:

1. no new learning records
2. tutor plan personalization may degrade

### Level 3: Full P4 rollback to P3 behavior

Use only if P4 changes block tutoring core flows.

Actions:

1. revert backend router registration for learning endpoints
2. revert tutor service learning integration points
3. revert frontend learner/progress/feedback UI additions
4. redeploy and validate P3 content+tutor baseline

Expected impact:

1. loss of P4 learning loop features
2. restored P3 operational baseline

## Safe Recovery Checklist After Rollback/Fix

1. `POST /api/tutor/session/start` works
2. `POST /api/tutor/session/{id}/next` works
3. `POST /api/content/generate` or artifact loading works
4. `GET /api/learning/progress` works (if learning re-enabled)
5. no event loss across Redis outage/recovery in failover test
6. `GET /api/learning/metrics` reflects healthy traffic with rising `successRequests`

## Command Snippets

### Check backend and redis containers

```powershell
docker compose ps
```

### Rebuild backend and worker

```powershell
docker compose up -d --build backend worker
```

### Run P4 backend regression

```powershell
Push-Location backend
../.venv/Scripts/python.exe -m pytest tests/unit/test_learning_service.py tests/integration/test_learning_api.py tests/integration/test_tutor_api.py -q
Pop-Location
```

### Run P4 frontend API regression

```powershell
Push-Location frontend
npm run test -- tests/integration/api.test.ts --run
Pop-Location
```

### Inspect learning runtime metrics

```powershell
Invoke-RestMethod "http://localhost:18000/api/learning/metrics" | ConvertTo-Json -Depth 8
```
