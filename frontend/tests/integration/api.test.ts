import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient } from '../../src/services/api';

// Mock fetch
global.fetch = vi.fn();

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should upload PDF', async () => {
    const mockFile = new File(['%PDF-1.4'], 'test.pdf', { type: 'application/pdf' });
    const mockResponse = {
      taskId: 'task-123',
      filename: 'test.pdf',
      status: 'processing'
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const result = await apiClient.uploadPDF(mockFile);
    expect(result.taskId).toBe('task-123');
    expect(result.filename).toBe('test.pdf');
  });

  it('should get PDF status', async () => {
    const mockResponse = {
      id: 'pdf-123',
      filename: 'test.pdf',
      status: 'completed',
      pageCount: 100,
      uploadTime: '2024-01-01T00:00:00Z'
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const result = await apiClient.getPDFStatus('pdf-123');
    expect(result.id).toBe('pdf-123');
    expect(result.status).toBe('completed');
  });

  it('should get graph data', async () => {
    const mockResponse = {
      elements: {
        nodes: [
          { data: { id: 'c1', label: 'Test', type: 'concept' }}
        ],
        edges: []
      }
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const result = await apiClient.getGraph('pdf-123');
    expect(result.elements.nodes).toHaveLength(1);
    expect(result.elements.nodes[0].data.label).toBe('Test');
  });

  it('should start tutor session', async () => {
    const mockRequest = {
      question: 'What is a PID controller?',
      pdfId: 'pdf-123',
      learnerId: 'learner-1',
      courseTypeStrategy: 'manual' as const,
      courseTypeOverride: 'problem_solving' as const,
    };

    const mockResponse = {
      sessionId: 'session-123',
      plan: { steps: [] },
      status: 'ready',
      metadata: {
        finalCourseType: 'problem_solving',
        autoDecision: {
          decision: 'knowledge_learning',
          confidence: 0.62,
          signals: ['keyword_knowledge:2'],
          overridden: false,
        },
      },
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const result = await apiClient.startTutorSession(mockRequest);
    expect(result.sessionId).toBe('session-123');
    expect(result.status).toBe('ready');
    expect(result.metadata?.finalCourseType).toBe('problem_solving');
  });

  it('should start tutor session with mixed legacy and new contract fields', async () => {
    const mockRequest = {
      question: 'Explain PID controllers',
      pdfId: 'pdf-123',
      courseTypeStrategy: 'manual' as const,
      courseTypeOverride: 'knowledge_learning' as const,
      courseType: 'problem_solving' as const,
    };

    const mockResponse = {
      sessionId: 'session-mixed-1',
      plan: { steps: [] },
      status: 'ready',
      metadata: {
        finalCourseType: 'knowledge_learning',
      },
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await apiClient.startTutorSession(mockRequest);
    expect(result.sessionId).toBe('session-mixed-1');
    expect(result.metadata?.finalCourseType).toBe('knowledge_learning');

    const fetchCall = (global.fetch as any).mock.calls[0];
    const payload = JSON.parse(fetchCall[1].body as string);
    expect(payload.courseTypeStrategy).toBe('manual');
    expect(payload.courseTypeOverride).toBe('knowledge_learning');
    expect(payload.courseType).toBe('problem_solving');
  });

  it('should analyze tutor question with strategy and override', async () => {
    const mockResponse = {
      graphId: 'graph-task-123',
      question: 'Given G(s)=1/(s+1), calculate Kp',
      summary: 'analysis',
      relevantConcepts: [],
      highlightedNodeIds: [],
      evidencePassages: [],
      suggestedSession: {},
      metadata: {
        finalCourseType: 'knowledge_learning',
        autoDecision: {
          decision: 'problem_solving',
          confidence: 0.88,
          signals: ['numeric_pattern'],
          overridden: false,
        },
      },
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await apiClient.analyzeTutorQuestion({
      question: 'Given G(s)=1/(s+1), calculate Kp',
      pdfId: 'graph-task-123',
      courseTypeStrategy: 'override',
      courseTypeOverride: 'knowledge_learning',
    });

    expect(result.metadata.finalCourseType).toBe('knowledge_learning');
    expect(result.metadata.autoDecision?.decision).toBe('problem_solving');
  });

  it('should get learning progress', async () => {
    const mockResponse = {
      progress: {
        learnerId: 'learner-1',
        graphId: 'graph-task-123',
        completedStepIds: [],
        masteryByConcept: {},
        conceptMastery: [],
        masteredConceptIds: [],
        pendingReviewConceptIds: ['concept-pid'],
        feedbackCount: 0,
        averageFeedbackRating: null,
        eventCount: 1,
        lastEventType: 'content_viewed',
        lastActivityAt: '2026-04-19T00:00:00Z',
        recentEvents: [],
        recentFeedback: [],
        metadata: { store: 'memory-test' },
      },
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await apiClient.getLearningProgress('learner-1', 'graph-task-123');
    expect(result.progress.learnerId).toBe('learner-1');
    expect(result.progress.pendingReviewConceptIds).toContain('concept-pid');
  });

  it('should track learning event', async () => {
    const mockResponse = {
      progress: {
        learnerId: 'learner-1',
        graphId: 'graph-task-123',
        completedStepIds: [],
        masteryByConcept: { 'concept-pid': 0.42 },
        conceptMastery: [],
        masteredConceptIds: [],
        pendingReviewConceptIds: ['concept-pid'],
        feedbackCount: 0,
        averageFeedbackRating: null,
        eventCount: 2,
        lastEventType: 'step_response',
        lastActivityAt: '2026-04-19T00:00:00Z',
        recentEvents: [],
        recentFeedback: [],
        metadata: { store: 'memory-test' },
      },
      event: {
        id: 'evt-1',
        eventType: 'step_response',
        timestamp: '2026-04-19T00:00:00Z',
        masteryDelta: 0.04,
        metadata: {},
      },
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await apiClient.trackLearningEvent({
      learnerId: 'learner-1',
      graphId: 'graph-task-123',
      sessionId: 'session-1',
      stepId: 'step-2',
      conceptId: 'concept-pid',
      eventType: 'step_response',
      confidence: 0.7,
    });

    expect(result.event.eventType).toBe('step_response');
    expect(result.progress.eventCount).toBe(2);
  });

  it('should submit learning feedback', async () => {
    const mockResponse = {
      progress: {
        learnerId: 'learner-1',
        graphId: 'graph-task-123',
        completedStepIds: [],
        masteryByConcept: {},
        conceptMastery: [],
        masteredConceptIds: [],
        pendingReviewConceptIds: ['concept-pid'],
        feedbackCount: 1,
        averageFeedbackRating: 4,
        eventCount: 2,
        lastEventType: 'step_response',
        lastActivityAt: '2026-04-19T00:00:00Z',
        recentEvents: [],
        recentFeedback: [],
        metadata: { store: 'memory-test' },
      },
      feedback: {
        id: 'feedback-1',
        learnerId: 'learner-1',
        graphId: 'graph-task-123',
        rating: 4,
        difficulty: 'appropriate',
        metadata: {},
        createdAt: '2026-04-19T00:00:00Z',
      },
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await apiClient.submitLearningFeedback({
      learnerId: 'learner-1',
      graphId: 'graph-task-123',
      sessionId: 'session-1',
      stepId: 'step-2',
      conceptId: 'concept-pid',
      rating: 4,
      difficulty: 'appropriate',
      comment: 'Good pacing',
    });

    expect(result.feedback.rating).toBe(4);
    expect(result.progress.feedbackCount).toBe(1);
  });

  it('should handle API errors', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      statusText: 'Not Found'
    });

    await expect(apiClient.getPDFStatus('invalid')).rejects.toThrow();
  });
});
