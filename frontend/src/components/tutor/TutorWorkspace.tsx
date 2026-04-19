import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { apiClient } from '../../services/api';
import { useContentArtifact } from '../../hooks/useContentArtifact';
import { useKnowledgeGraph } from '../../hooks/useKnowledgeGraph';
import { ContentRenderer } from '../content/ContentRenderer';
import { KnowledgeGraph } from '../graph/KnowledgeGraph';
import type {
  ContentArtifact,
  FeedbackDifficulty,
  LearningProgress,
  TeachingStep,
  TutorSessionResponse,
} from '../../types/api';

import './TutorWorkspace.css';

const DEFAULT_TUTOR_GRAPH_ID = import.meta.env.VITE_DEFAULT_GRAPH_ID || '';

function messageRoleLabel(role: string): string {
  if (role === 'assistant') {
    return '导师';
  }
  if (role === 'system') {
    return '系统';
  }
  return '学员';
}

function currentGraphId(session: TutorSessionResponse | null, fallbackGraphId: string): string {
  const meta = session?.metadata;
  if (meta && typeof meta.pdfId === 'string') {
    return meta.pdfId;
  }
  return fallbackGraphId;
}

function normalizeLearnerId(value: string): string {
  return value.trim();
}

function toStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string');
}

function sessionPendingReview(session: TutorSessionResponse | null): string[] {
  const snapshot = session?.metadata?.learningSnapshot;
  if (!snapshot || typeof snapshot !== 'object') {
    return [];
  }
  const pending = (snapshot as Record<string, unknown>).pendingReviewConceptIds;
  return toStringArray(pending);
}

export function TutorWorkspace() {
  const [searchParams] = useSearchParams();
  const queryGraphId = searchParams.get('graphId') || '';
  const storedGraphId = window.localStorage.getItem('latestGraphId') || '';
  const initialGraphId = queryGraphId || DEFAULT_TUTOR_GRAPH_ID || storedGraphId;

  const [question, setQuestion] = useState('');
  const [graphId, setGraphId] = useState(initialGraphId);
  const [learnerId, setLearnerId] = useState('');
  const [session, setSession] = useState<TutorSessionResponse | null>(null);
  const [responseText, setResponseText] = useState('');
  const [responseConfidence, setResponseConfidence] = useState('medium');
  const [feedbackRating, setFeedbackRating] = useState(4);
  const [feedbackDifficulty, setFeedbackDifficulty] = useState<FeedbackDifficulty>('appropriate');
  const [feedbackComment, setFeedbackComment] = useState('');
  const [overrideArtifact, setOverrideArtifact] = useState<ContentArtifact | null>(null);
  const [learningProgress, setLearningProgress] = useState<LearningProgress | null>(null);
  const [latestTrackedStepKey, setLatestTrackedStepKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeStep = session?.currentStep ?? null;
  const contentId = activeStep?.content?.contentArtifactId ?? null;
  const {
    artifact,
    loading: contentLoading,
    error: contentError,
    refresh: refreshContent,
  } = useContentArtifact(contentId);
  const displayedArtifact = overrideArtifact ?? artifact;

  const graphIdForView = currentGraphId(session, graphId);
  const normalizedLearnerId = normalizeLearnerId(learnerId);
  const highlightedNodes = useMemo(
    () => activeStep?.content?.graphHighlights ?? [],
    [activeStep],
  );
  const pendingReviewFromSession = useMemo(() => sessionPendingReview(session), [session]);
  const pendingReviewConcepts = useMemo(() => {
    if (learningProgress?.pendingReviewConceptIds.length) {
      return learningProgress.pendingReviewConceptIds;
    }
    return pendingReviewFromSession;
  }, [learningProgress, pendingReviewFromSession]);
  const { data: graphData, loading: graphLoading, error: graphError } = useKnowledgeGraph(graphIdForView);

  useEffect(() => {
    if (queryGraphId && queryGraphId !== graphId) {
      setGraphId(queryGraphId);
    }
  }, [queryGraphId, graphId]);

  useEffect(() => {
    if (graphId) {
      window.localStorage.setItem('latestGraphId', graphId);
    }
  }, [graphId]);

  const refreshLearningProgress = async (
    targetSession: TutorSessionResponse | null,
    explicitGraphId?: string,
  ) => {
    if (!normalizedLearnerId) {
      setLearningProgress(null);
      return;
    }
    const targetGraphId = explicitGraphId ?? currentGraphId(targetSession, graphId);
    const result = await apiClient.getLearningProgress(normalizedLearnerId, targetGraphId);
    setLearningProgress(result.progress);
  };

  const startSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      setLoading(true);
      setError(null);
      const context: Record<string, unknown> = { learning_level: 'intermediate' };
      if (normalizedLearnerId) {
        context.learnerId = normalizedLearnerId;
      }
      const result = await apiClient.startTutorSession({
        question,
        pdfId: graphId,
        learnerId: normalizedLearnerId || undefined,
        mode: 'interactive',
        context,
        courseTypeStrategy: 'auto',
      });
      const hydrated = await apiClient.nextTutorSessionStep(result.sessionId);
      setSession(hydrated);
      setLatestTrackedStepKey(null);
      setResponseText('');
      await refreshLearningProgress(hydrated);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const runNext = async () => {
    if (!session) {
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const result = await apiClient.nextTutorSessionStep(session.sessionId);
      setSession(result);
      setOverrideArtifact(null);
      setResponseText('');
      await refreshLearningProgress(result);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const runBack = async () => {
    if (!session) {
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const result = await apiClient.backTutorSessionStep(session.sessionId);
      setSession(result);
      setOverrideArtifact(null);
      setResponseText('');
      await refreshLearningProgress(result);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const jumpToStep = async (step: TeachingStep) => {
    if (!session) {
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const result = await apiClient.jumpTutorSessionStep(session.sessionId, { stepId: step.id });
      setSession(result);
      setOverrideArtifact(null);
      setResponseText('');
      await refreshLearningProgress(result);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const submitResponse = async () => {
    if (!session || !responseText.trim()) {
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const result = await apiClient.respondToTutorSession(session.sessionId, {
        response: responseText.trim(),
        metadata: { confidence: responseConfidence },
      });
      setSession(result);
      setResponseText('');
      await refreshLearningProgress(result);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const submitLearningFeedback = async () => {
    if (!session || !normalizedLearnerId) {
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const conceptId = activeStep?.relatedTopics?.[0];
      const result = await apiClient.submitLearningFeedback({
        learnerId: normalizedLearnerId,
        graphId: graphIdForView,
        sessionId: session.sessionId,
        stepId: activeStep?.id,
        conceptId,
        rating: feedbackRating,
        difficulty: feedbackDifficulty,
        comment: feedbackComment.trim() || undefined,
        metadata: {
          stepType: activeStep?.type,
          source: 'tutor_workspace',
        },
      });
      setLearningProgress(result.progress);
      setFeedbackComment('');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setOverrideArtifact(null);
  }, [contentId]);

  useEffect(() => {
    if (!session || !activeStep || !normalizedLearnerId) {
      return;
    }

    const stepTrackingKey = `${normalizedLearnerId}:${session.sessionId}:${activeStep.id}`;
    if (stepTrackingKey === latestTrackedStepKey) {
      return;
    }
    setLatestTrackedStepKey(stepTrackingKey);

    const conceptId = activeStep.relatedTopics?.[0];
    void apiClient
      .trackLearningEvent({
        learnerId: normalizedLearnerId,
        graphId: graphIdForView,
        sessionId: session.sessionId,
        stepId: activeStep.id,
        conceptId,
        eventType: 'content_viewed',
        metadata: {
          source: 'tutor_workspace',
          stepType: activeStep.type,
        },
      })
      .then((result) => {
        setLearningProgress(result.progress);
      })
      .catch(() => {
        // Non-blocking telemetry path.
      });
  }, [
    activeStep,
    graphIdForView,
    latestTrackedStepKey,
    normalizedLearnerId,
    session,
  ]);

  useEffect(() => {
    if (!normalizedLearnerId || session) {
      return;
    }
    void refreshLearningProgress(null, graphId);
  }, [graphId, normalizedLearnerId, session]);

  const actionDisabled = loading || !session;

  return (
    <div className="tutor-page">
      <header className="tutor-page__hero">
        <h2 className="tutor-page__title">AI 导师</h2>
        <p className="tutor-page__subtitle">拿到图谱后，只需提问一次，系统会自动判别问题类型并生成课程内容。</p>
      </header>

      <form className="tutor-page__start" onSubmit={startSession}>
        <input
          className="tutor-page__input"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="输入学习问题"
          required
        />
        <button className="tutor-page__button" type="submit" disabled={loading}>
          {loading ? '处理中...' : '生成课程'}
        </button>
        <div className="tutor-page__helper">当前图谱: {graphId || '未选择'}</div>

        <details className="tutor-page__advanced">
          <summary>高级设置（可选）</summary>
          <div className="tutor-page__advanced-body">
            <input
              className="tutor-page__input"
              value={graphId}
              onChange={(event) => setGraphId(event.target.value)}
              placeholder="graph id"
              required
            />
            <input
              className="tutor-page__input"
              value={learnerId}
              onChange={(event) => setLearnerId(event.target.value)}
              placeholder="learner id (用于学习闭环)"
            />
            <button
              className="tutor-page__button tutor-page__button--ghost"
              type="button"
              disabled={!normalizedLearnerId || loading}
              onClick={() => void refreshLearningProgress(session)}
            >
              刷新学习进度
            </button>
          </div>
        </details>
      </form>

      {error && <div className="tutor-page__error">请求失败: {error}</div>}

      <div className="tutor-page__grid">
        <section className="tutor-page__panel">
          <div className="tutor-page__panel-header">
            <h3>{activeStep ? `当前步骤: ${activeStep.title}` : '会话展示区'}</h3>
          </div>
          <div className="tutor-page__panel-body">
            <ContentRenderer
              artifact={displayedArtifact}
              loading={contentLoading}
              error={contentError?.message ?? null}
              fallbackMarkdown={activeStep?.content?.markdown}
            />

            <div className="tutor-page__actions">
              <button
                className="tutor-page__button tutor-page__button--ghost"
                type="button"
                disabled={actionDisabled}
                onClick={runBack}
              >
                上一步
              </button>
              <button
                className="tutor-page__button"
                type="button"
                disabled={actionDisabled || session?.canAdvance === false}
                onClick={runNext}
              >
                下一步
              </button>
              <button
                className="tutor-page__button tutor-page__button--ghost"
                type="button"
                disabled={!contentId || contentLoading}
                onClick={() => void refreshContent()}
              >
                刷新内容
              </button>
            </div>

            {session?.needsUserResponse && (
              <div className="tutor-page__response">
                <textarea
                  className="tutor-page__textarea"
                  rows={4}
                  value={responseText}
                  onChange={(event) => setResponseText(event.target.value)}
                  placeholder="请输入你对当前步骤的回答"
                />
                <div className="tutor-page__response-meta">
                  <label htmlFor="response-confidence">自评信心:</label>
                  <select
                    id="response-confidence"
                    className="tutor-page__select tutor-page__select--compact"
                    value={responseConfidence}
                    onChange={(event) => setResponseConfidence(event.target.value)}
                  >
                    <option value="low">low</option>
                    <option value="medium">medium</option>
                    <option value="high">high</option>
                  </select>
                </div>
                <button
                  className="tutor-page__button"
                  type="button"
                  disabled={loading || !responseText.trim()}
                  onClick={submitResponse}
                >
                  提交回答
                </button>
              </div>
            )}

            {session?.feedback && <div className="tutor-page__status">导师反馈: {session.feedback}</div>}
          </div>
        </section>

        <aside className="tutor-page__side">
          <section className="tutor-page__panel">
            <div className="tutor-page__panel-header">
              <h3>会话编排</h3>
            </div>
            <div className="tutor-page__panel-body">
              {session ? (
                <>
                  <div className="tutor-page__step-list">
                    {session.plan.steps.map((step) => {
                      const isActive = session.currentStep?.id === step.id;
                      return (
                        <button
                          key={step.id}
                          type="button"
                          className={`tutor-page__step-item ${isActive ? 'is-active' : ''}`}
                          onClick={() => void jumpToStep(step)}
                        >
                          <p className="tutor-page__step-title">{step.title}</p>
                          <p className="tutor-page__step-meta">
                            {step.type} | artifact: {step.content.contentArtifactStatus ?? 'none'}
                          </p>
                        </button>
                      );
                    })}
                  </div>

                  <div className="tutor-page__status">状态: {session.status} | 步骤索引: {session.currentStepIndex}</div>

                  <div className="tutor-page__messages">
                    {session.messages.slice(-6).map((message, index) => (
                      <div key={`${message.role}-${index}`} className="tutor-page__message">
                        <strong>{messageRoleLabel(message.role)}</strong>
                        <div>{message.content}</div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="tutor-page__status">启动会话后，这里会显示 step plan 和会话消息。</div>
              )}

              <div className="tutor-page__learning">
                <h4>学习闭环状态</h4>
                {learningProgress ? (
                  <>
                    <div className="tutor-page__learning-metrics">
                      <span>event: {learningProgress.eventCount}</span>
                      <span>feedback: {learningProgress.feedbackCount}</span>
                      <span>avg rating: {learningProgress.averageFeedbackRating ?? '-'}</span>
                    </div>
                    <div className="tutor-page__badge-list">
                      {pendingReviewConcepts.map((conceptId) => (
                        <span key={conceptId} className="tutor-page__badge tutor-page__badge--warn">
                          待复习 {conceptId}
                        </span>
                      ))}
                      {learningProgress.masteredConceptIds.map((conceptId) => (
                        <span key={conceptId} className="tutor-page__badge tutor-page__badge--ok">
                          已掌握 {conceptId}
                        </span>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="tutor-page__learning-empty">
                    输入 learner id 后可查看学习状态。当前会话仍可运行，但不会记录个性化进度。
                  </p>
                )}

                <div className="tutor-page__feedback-form">
                  <h5>本步骤反馈</h5>
                  <div className="tutor-page__feedback-row">
                    <label htmlFor="feedback-rating">评分</label>
                    <select
                      id="feedback-rating"
                      className="tutor-page__select tutor-page__select--compact"
                      value={feedbackRating}
                      onChange={(event) => setFeedbackRating(Number(event.target.value))}
                    >
                      <option value={5}>5</option>
                      <option value={4}>4</option>
                      <option value={3}>3</option>
                      <option value={2}>2</option>
                      <option value={1}>1</option>
                    </select>
                    <label htmlFor="feedback-difficulty">难度</label>
                    <select
                      id="feedback-difficulty"
                      className="tutor-page__select tutor-page__select--compact"
                      value={feedbackDifficulty}
                      onChange={(event) => setFeedbackDifficulty(event.target.value as FeedbackDifficulty)}
                    >
                      <option value="too_easy">too_easy</option>
                      <option value="appropriate">appropriate</option>
                      <option value="too_hard">too_hard</option>
                    </select>
                  </div>
                  <textarea
                    className="tutor-page__textarea"
                    rows={3}
                    value={feedbackComment}
                    onChange={(event) => setFeedbackComment(event.target.value)}
                    placeholder="可选：描述你觉得难/易的原因"
                  />
                  <button
                    className="tutor-page__button tutor-page__button--ghost"
                    type="button"
                    disabled={!session || !normalizedLearnerId || loading}
                    onClick={submitLearningFeedback}
                  >
                    提交学习反馈
                  </button>
                </div>
              </div>
            </div>
          </section>

          <section className="tutor-page__panel">
            <div className="tutor-page__panel-header">
              <h3>知识图谱高亮</h3>
            </div>
            <div className="tutor-page__panel-body">
              {graphLoading && <div className="tutor-page__status">图谱加载中...</div>}
              {graphError && <div className="tutor-page__error">图谱加载失败: {graphError.message}</div>}
              {graphData && (
                <div className="tutor-page__graph">
                  <KnowledgeGraph data={graphData} highlightedNodes={highlightedNodes} />
                </div>
              )}
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
