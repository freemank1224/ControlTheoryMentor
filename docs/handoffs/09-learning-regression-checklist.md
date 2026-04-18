# P4 Learning Regression Checklist

## Scope

This checklist validates the P4 learning loop across backend and frontend:

1. learning API correctness
2. tutor to learning event bridge
3. frontend learner-aware tutor workflow
4. failover/failback persistence behavior

## Pre-conditions

1. `docker compose up -d --build backend worker frontend redis`
2. Backend API reachable at `http://localhost:18000`
3. Frontend reachable at `http://localhost:3000` or compose frontend endpoint
4. At least one graph id available (example: `graph-task-123`)

## Automated Regression

### Backend

Run:

```powershell
Push-Location backend
../.venv/Scripts/python.exe -m pytest tests/unit/test_learning_service.py tests/integration/test_learning_api.py tests/integration/test_tutor_api.py -q
Pop-Location
```

Expected:

1. learning service tests pass (including fallback and failback)
2. learning API tests pass
3. tutor integration includes personalization snapshot and event growth

### Frontend

Run:

```powershell
Push-Location frontend
npm run test -- tests/integration/api.test.ts --run
Pop-Location
```

Expected:

1. API client can call `learning/progress`
2. API client can call `learning/track`
3. API client can call `learning/feedback`

## Manual End-to-End Checklist

### A. Start learner-aware tutor session

1. Open tutor page.
2. Enter `learner id` and `graph id`.
3. Start session.

Verify:

1. session starts successfully
2. page shows learning panel
3. learning panel shows event count after step navigation

### B. Step navigation generates progress

1. Click next to enter step 1.
2. Click next to enter interactive step.
3. Submit a learner response.

Verify:

1. event count increases
2. last step id updates
3. pending/mastered concept badges render when available

### C. Feedback loop works

1. Fill feedback rating, difficulty, and optional comment.
2. Submit feedback.

Verify:

1. feedback count increases
2. average rating updates
3. API returns updated progress in response

### D. Session restart personalization

1. Start a new tutor session with the same `learner id` and `graph id`.

Verify:

1. session metadata includes `learningSnapshot`
2. tutor plan includes weak-concept-oriented wording when pending review concepts exist

## Failure Signals

Treat any of the following as regression:

1. `learning/progress` returns empty despite prior events for same learner+graph
2. tutor session metadata loses `learnerId` or `learningSnapshot`
3. frontend tutor page cannot submit feedback
4. Redis recovery causes loss of events recorded during outage

## Evidence to Capture

For each run keep:

1. backend pytest output
2. frontend vitest output
3. one API response sample from each endpoint:
1. `POST /api/learning/track`
2. `GET /api/learning/progress`
3. `POST /api/learning/feedback`
4. screenshot of tutor page learning panel after at least one feedback submission
