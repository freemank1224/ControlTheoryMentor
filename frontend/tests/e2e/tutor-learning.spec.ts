import { test, expect, type Page, type Route } from '@playwright/test';

type TutorSessionStatus = 'ready' | 'in_progress' | 'awaiting_response' | 'completed';

type StepType = 'intro' | 'concept' | 'practice' | 'summary';

interface TeachingStepState {
  id: string;
  type: StepType;
  title: string;
  objective: string;
  content: {
    markdown: string;
    contentArtifactId: string;
    contentArtifactStatus: 'ready';
    graphHighlights: string[];
    relatedTopics: string[];
  };
  relatedTopics: string[];
  requiresResponse: boolean;
}

interface TutorSessionState {
  sessionId: string;
  learnerId: string;
  graphId: string;
  question: string;
  status: TutorSessionStatus;
  currentStepIndex: number;
  awaitingResponse: boolean;
  feedback: string | null;
  plan: {
    summary: string;
    goals: string[];
    steps: TeachingStepState[];
  };
  messages: Array<{ role: 'assistant' | 'user' | 'system'; content: string }>;
  learningSnapshot: {
    masteredConceptIds: string[];
    pendingReviewConceptIds: string[];
    averageFeedbackRating: number | null;
    eventCount: number;
  };
  createdAt: string;
  updatedAt: string;
}

interface LearningProgressState {
  learnerId: string;
  graphId: string;
  sessionId: string | null;
  currentStepId: string | null;
  completedStepIds: string[];
  masteryByConcept: Record<string, number>;
  conceptMastery: Array<{ conceptId: string; score: number; level: string; updatedAt: string }>;
  masteredConceptIds: string[];
  pendingReviewConceptIds: string[];
  feedbackCount: number;
  averageFeedbackRating: number | null;
  eventCount: number;
  lastEventType: string | null;
  lastActivityAt: string;
  recentEvents: Array<Record<string, unknown>>;
  recentFeedback: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
}

interface ContentArtifactState {
  id: string;
  markdown: string;
}

function nowIso(): string {
  return new Date().toISOString();
}

function progressKey(learnerId: string, graphId: string): string {
  return `${learnerId}::${graphId}`;
}

function buildDefaultProgress(learnerId: string, graphId: string): LearningProgressState {
  return {
    learnerId,
    graphId,
    sessionId: null,
    currentStepId: null,
    completedStepIds: [],
    masteryByConcept: {},
    conceptMastery: [],
    masteredConceptIds: [],
    pendingReviewConceptIds: [],
    feedbackCount: 0,
    averageFeedbackRating: null,
    eventCount: 0,
    lastEventType: null,
    lastActivityAt: nowIso(),
    recentEvents: [],
    recentFeedback: [],
    metadata: { store: 'playwright-mock' },
  };
}

function buildSteps(sessionId: string, weakConceptId?: string): TeachingStepState[] {
  const weakHint = weakConceptId ? ` 当前建议优先补练概念：${weakConceptId}。` : '';
  return [
    {
      id: 'step-1',
      type: 'intro',
      title: '建立问题背景: PID Controller',
      objective: '明确问题背景',
      content: {
        markdown: '我们先确认 PID 在当前控制问题中的目标和边界。',
        contentArtifactId: `${sessionId}-content-step-1`,
        contentArtifactStatus: 'ready',
        graphHighlights: ['concept-pid'],
        relatedTopics: ['concept-pid'],
      },
      relatedTopics: ['concept-pid'],
      requiresResponse: false,
    },
    {
      id: 'step-2',
      type: 'concept',
      title: '拆解核心概念: PID Controller',
      objective: '检查学员是否理解核心概念',
      content: {
        markdown: '请你用自己的话解释积分项如何影响稳态误差。',
        contentArtifactId: `${sessionId}-content-step-2`,
        contentArtifactStatus: 'ready',
        graphHighlights: ['concept-pid'],
        relatedTopics: ['concept-pid'],
      },
      relatedTopics: ['concept-pid'],
      requiresResponse: true,
    },
    {
      id: 'step-3',
      type: 'practice',
      title: '理解检查与迁移',
      objective: '迁移到具体场景',
      content: {
        markdown: `把 PID 放到一个具体场景中，说明你会优先观察哪些量。${weakHint}`,
        contentArtifactId: `${sessionId}-content-step-3`,
        contentArtifactStatus: 'ready',
        graphHighlights: ['concept-pid', 'concept-feedback'],
        relatedTopics: ['concept-feedback'],
      },
      relatedTopics: ['concept-feedback'],
      requiresResponse: true,
    },
    {
      id: 'step-4',
      type: 'summary',
      title: '总结与下一步',
      objective: '总结并安排复习',
      content: {
        markdown: '总结本轮关键点，并给出下一步复习建议。',
        contentArtifactId: `${sessionId}-content-step-4`,
        contentArtifactStatus: 'ready',
        graphHighlights: ['concept-pid'],
        relatedTopics: ['concept-pid'],
      },
      relatedTopics: ['concept-pid'],
      requiresResponse: false,
    },
  ];
}

function buildSessionResponse(session: TutorSessionState) {
  const currentStep =
    session.currentStepIndex >= 0 && session.currentStepIndex < session.plan.steps.length
      ? session.plan.steps[session.currentStepIndex]
      : null;

  return {
    sessionId: session.sessionId,
    plan: session.plan,
    currentStep,
    currentStepIndex: session.currentStepIndex,
    status: session.status,
    messages: session.messages,
    canAdvance: session.status !== 'completed' && !session.awaitingResponse,
    needsUserResponse: session.awaitingResponse,
    feedback: session.feedback,
    metadata: {
      pdfId: session.graphId,
      question: session.question,
      learnerId: session.learnerId,
      mode: 'interactive',
      topics: ['concept-pid', 'concept-feedback'],
      totalSteps: session.plan.steps.length,
      createdAt: session.createdAt,
      updatedAt: session.updatedAt,
      store: 'playwright-mock',
      learningSnapshot: session.learningSnapshot,
    },
  };
}

function buildArtifactPayload(artifact: ContentArtifactState) {
  return {
    artifact: {
      id: artifact.id,
      status: 'ready',
      renderHint: 'markdown',
      targetContentTypes: ['markdown'],
      markdown: artifact.markdown,
      mermaid: null,
      latex: null,
      interactive: null,
      source: {
        stage: 'intro',
        stepId: 'step-0',
        stepTitle: 'placeholder',
        objective: 'placeholder',
        question: 'placeholder',
        graphId: 'graph-task-e2e',
        sessionMode: 'interactive',
        learnerLevel: 'intermediate',
        responseMode: 'passive',
        conceptIds: [],
        highlightedNodeIds: [],
        evidencePassageIds: [],
        targetContentTypes: ['markdown'],
        renderHint: 'markdown',
      },
      cacheKey: `cache-${artifact.id}`,
      createdAt: nowIso(),
      updatedAt: nowIso(),
      metadata: {},
    },
    cacheHit: true,
  };
}

async function json(route: Route, status: number, body: unknown) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
}

function ensureProgress(
  progressStore: Map<string, LearningProgressState>,
  learnerId: string,
  graphId: string,
): LearningProgressState {
  const key = progressKey(learnerId, graphId);
  const existing = progressStore.get(key);
  if (existing) {
    return existing;
  }
  const created = buildDefaultProgress(learnerId, graphId);
  progressStore.set(key, created);
  return created;
}

async function mockTutorLearningApis(page: Page) {
  const sessions = new Map<string, TutorSessionState>();
  const progressStore = new Map<string, LearningProgressState>();
  const artifacts = new Map<string, ContentArtifactState>();
  let sessionCounter = 0;

  await page.route('**/api/**', async (route) => {
    const request = route.request();
    const method = request.method();
    const url = new URL(request.url());
    const path = url.pathname;

    const bodyText = request.postData();
    const body = bodyText ? (JSON.parse(bodyText) as Record<string, unknown>) : {};

    if (method === 'GET' && path.startsWith('/api/graph/')) {
      await json(route, 200, {
        elements: {
          nodes: [
            { data: { id: 'concept-pid', label: 'PID Controller', type: 'concept' } },
            { data: { id: 'concept-feedback', label: 'Feedback Loop', type: 'concept' } },
          ],
          edges: [{ data: { id: 'e1', source: 'concept-feedback', target: 'concept-pid', label: 'supports' } }],
        },
        metadata: { graphId: path.split('/').pop() },
      });
      return;
    }

    if (method === 'GET' && path.startsWith('/api/content/')) {
      const contentId = path.split('/').pop() ?? '';
      const artifact = artifacts.get(contentId);
      if (!artifact) {
        await json(route, 404, { detail: 'Content not found' });
        return;
      }
      await json(route, 200, buildArtifactPayload(artifact));
      return;
    }

    if (method === 'POST' && path === '/api/tutor/session/start') {
      sessionCounter += 1;
      const sessionId = `session-e2e-${sessionCounter}`;
      const learnerId = typeof body.learnerId === 'string' ? body.learnerId : '';
      const graphId = typeof body.pdfId === 'string' ? body.pdfId : 'graph-task-e2e';
      const question = typeof body.question === 'string' ? body.question : 'question';
      const progress = learnerId ? ensureProgress(progressStore, learnerId, graphId) : null;
      const weakConcept = progress?.pendingReviewConceptIds[0];

      const steps = buildSteps(sessionId, weakConcept);
      for (const step of steps) {
        artifacts.set(step.content.contentArtifactId, {
          id: step.content.contentArtifactId,
          markdown: step.content.markdown,
        });
      }

      const session: TutorSessionState = {
        sessionId,
        learnerId,
        graphId,
        question,
        status: 'ready',
        currentStepIndex: -1,
        awaitingResponse: false,
        feedback: null,
        plan: {
          summary: `围绕 ${question} 的教学计划`,
          goals: ['理解概念', '迁移应用'],
          steps,
        },
        messages: [{ role: 'system', content: `session started: ${question}` }],
        learningSnapshot: {
          masteredConceptIds: progress?.masteredConceptIds ?? [],
          pendingReviewConceptIds: progress?.pendingReviewConceptIds ?? [],
          averageFeedbackRating: progress?.averageFeedbackRating ?? null,
          eventCount: progress?.eventCount ?? 0,
        },
        createdAt: nowIso(),
        updatedAt: nowIso(),
      };

      sessions.set(sessionId, session);
      await json(route, 200, buildSessionResponse(session));
      return;
    }

    if (method === 'POST' && /\/api\/tutor\/session\/[^/]+\/next$/.test(path)) {
      const sessionId = path.split('/')[4];
      const session = sessions.get(sessionId);
      if (!session) {
        await json(route, 404, { detail: 'Tutor session not found' });
        return;
      }
      if (session.awaitingResponse) {
        await json(route, 409, { detail: 'Current step requires learner response.' });
        return;
      }

      const nextIndex = session.currentStepIndex + 1;
      if (nextIndex >= session.plan.steps.length) {
        session.status = 'completed';
        session.awaitingResponse = false;
        session.currentStepIndex = session.plan.steps.length;
        session.feedback = '本轮学习完成。';
      } else {
        const step = session.plan.steps[nextIndex];
        session.currentStepIndex = nextIndex;
        session.awaitingResponse = step.requiresResponse;
        session.status = step.requiresResponse ? 'awaiting_response' : 'in_progress';
        session.feedback = null;
      }
      session.updatedAt = nowIso();
      await json(route, 200, buildSessionResponse(session));
      return;
    }

    if (method === 'POST' && /\/api\/tutor\/session\/[^/]+\/respond$/.test(path)) {
      const sessionId = path.split('/')[4];
      const session = sessions.get(sessionId);
      if (!session) {
        await json(route, 404, { detail: 'Tutor session not found' });
        return;
      }
      if (!session.awaitingResponse) {
        await json(route, 409, { detail: 'Current step does not require response.' });
        return;
      }

      const responseText = typeof body.response === 'string' ? body.response : '';
      session.messages.push({ role: 'user', content: responseText });
      session.messages.push({ role: 'assistant', content: '你的回答已经覆盖关键点，继续下一步。' });
      session.awaitingResponse = false;
      session.status = 'ready';
      session.feedback = '你的回答已经覆盖关键点，继续下一步。';
      session.updatedAt = nowIso();

      if (session.learnerId) {
        const progress = ensureProgress(progressStore, session.learnerId, session.graphId);
        const step = session.plan.steps[Math.max(session.currentStepIndex, 0)];
        progress.sessionId = session.sessionId;
        progress.currentStepId = step?.id ?? null;
        progress.eventCount += 1;
        progress.lastEventType = 'step_response';
        progress.lastActivityAt = nowIso();
      }

      await json(route, 200, buildSessionResponse(session));
      return;
    }

    if (method === 'POST' && /\/api\/tutor\/session\/[^/]+\/jump$/.test(path)) {
      const sessionId = path.split('/')[4];
      const session = sessions.get(sessionId);
      if (!session) {
        await json(route, 404, { detail: 'Tutor session not found' });
        return;
      }

      const targetStepId = typeof body.stepId === 'string' ? body.stepId : '';
      const targetIndex = session.plan.steps.findIndex((step) => step.id === targetStepId);
      if (targetIndex < 0) {
        await json(route, 404, { detail: 'stepId not found' });
        return;
      }

      const targetStep = session.plan.steps[targetIndex];
      session.currentStepIndex = targetIndex;
      session.awaitingResponse = targetStep.requiresResponse;
      session.status = targetStep.requiresResponse ? 'awaiting_response' : 'in_progress';
      session.feedback = `Jumped to ${targetStep.title}`;
      session.updatedAt = nowIso();
      await json(route, 200, buildSessionResponse(session));
      return;
    }

    if (method === 'GET' && path === '/api/learning/progress') {
      const learnerId = url.searchParams.get('learnerId') ?? '';
      const graphId = url.searchParams.get('graphId') ?? '';
      const progress = ensureProgress(progressStore, learnerId, graphId);
      await json(route, 200, { progress });
      return;
    }

    if (method === 'POST' && path === '/api/learning/track') {
      const learnerId = typeof body.learnerId === 'string' ? body.learnerId : '';
      const graphId = typeof body.graphId === 'string' ? body.graphId : '';
      const progress = ensureProgress(progressStore, learnerId, graphId);
      progress.sessionId = typeof body.sessionId === 'string' ? body.sessionId : progress.sessionId;
      progress.currentStepId = typeof body.stepId === 'string' ? body.stepId : progress.currentStepId;
      progress.eventCount += 1;
      progress.lastEventType = typeof body.eventType === 'string' ? body.eventType : 'content_viewed';
      progress.lastActivityAt = nowIso();

      const event = {
        id: `evt-${Date.now()}`,
        eventType: progress.lastEventType,
        timestamp: nowIso(),
        sessionId: progress.sessionId,
        stepId: progress.currentStepId,
        conceptId: typeof body.conceptId === 'string' ? body.conceptId : null,
        confidence: typeof body.confidence === 'number' ? body.confidence : null,
        masteryDelta: 0,
        metadata: {},
      };
      await json(route, 200, { progress, event });
      return;
    }

    if (method === 'POST' && path === '/api/learning/feedback') {
      const learnerId = typeof body.learnerId === 'string' ? body.learnerId : '';
      const graphId = typeof body.graphId === 'string' ? body.graphId : '';
      const conceptId = typeof body.conceptId === 'string' ? body.conceptId : 'concept-feedback';
      const rating = typeof body.rating === 'number' ? body.rating : 4;
      const difficulty = typeof body.difficulty === 'string' ? body.difficulty : 'appropriate';

      const progress = ensureProgress(progressStore, learnerId, graphId);
      progress.sessionId = typeof body.sessionId === 'string' ? body.sessionId : progress.sessionId;
      progress.currentStepId = typeof body.stepId === 'string' ? body.stepId : progress.currentStepId;
      progress.feedbackCount += 1;
      const previousTotal = (progress.averageFeedbackRating ?? 0) * (progress.feedbackCount - 1);
      progress.averageFeedbackRating = Number(((previousTotal + rating) / progress.feedbackCount).toFixed(2));
      progress.lastActivityAt = nowIso();

      if (difficulty === 'too_hard' || conceptId === 'concept-feedback') {
        if (!progress.pendingReviewConceptIds.includes(conceptId)) {
          progress.pendingReviewConceptIds.push(conceptId);
        }
      }

      const feedback = {
        id: `feedback-${Date.now()}`,
        learnerId,
        graphId,
        sessionId: progress.sessionId,
        stepId: progress.currentStepId,
        conceptId,
        rating,
        difficulty,
        comment: typeof body.comment === 'string' ? body.comment : null,
        metadata: {},
        createdAt: nowIso(),
      };

      progress.recentFeedback = [feedback, ...progress.recentFeedback].slice(0, 20);
      await json(route, 200, { progress, feedback });
      return;
    }

    await route.fallback();
  });
}

test.describe('Tutor Learning End-to-End', () => {
  test('start, advance, respond, feedback, and second-session personalization', async ({ page }) => {
    await mockTutorLearningApis(page);

    await page.goto('/tutor');

    const learnerId = 'learner-e2e';
    const graphId = 'graph-task-e2e';

    await page.getByPlaceholder('输入学习问题').fill('How does PID reduce steady-state error?');
    await page.getByPlaceholder('graph id').fill(graphId);
    await page.getByPlaceholder('learner id (用于学习闭环)').fill(learnerId);

    await page.getByRole('button', { name: '启动会话' }).click();
    await expect(page.getByText('状态: ready')).toBeVisible();

    const nextButton = page.locator('.tutor-page__actions').getByRole('button', {
      name: '下一步',
      exact: true,
    });

    await nextButton.click();
    await expect(page.getByText('当前步骤: 建立问题背景: PID Controller')).toBeVisible();

    await nextButton.click();
    await expect(page.getByText('当前步骤: 拆解核心概念: PID Controller')).toBeVisible();
    await expect(page.getByRole('button', { name: '提交回答' })).toBeVisible();

    await page.getByPlaceholder('请输入你对当前步骤的回答').fill('Integral action accumulates error and reduces steady-state offset.');
    await page.getByRole('button', { name: '提交回答' }).click();
    await expect(page.getByText('导师反馈: 你的回答已经覆盖关键点，继续下一步。')).toBeVisible();

    await page.locator('#feedback-difficulty').selectOption('too_hard');
    await page.getByRole('button', { name: '提交学习反馈' }).click();
    await expect(page.locator('.tutor-page__learning')).toContainText('feedback: 1');

    await page.getByPlaceholder('输入学习问题').fill('What should I practice next?');
    await page.getByRole('button', { name: '启动会话' }).click();

    await expect(page.locator('.tutor-page__learning')).toContainText('待复习 concept-pid');

    await page.getByRole('button', { name: /理解检查与迁移/ }).click();
    await expect(page.locator('.content-renderer')).toContainText(' 当前建议优先补练概念：concept-pid');
  });
});
