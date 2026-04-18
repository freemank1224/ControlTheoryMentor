import { FormEvent, useMemo, useState } from 'react';

import { apiClient } from '../../services/api';
import { useContentArtifact } from '../../hooks/useContentArtifact';
import { useKnowledgeGraph } from '../../hooks/useKnowledgeGraph';
import { ContentRenderer } from '../content/ContentRenderer';
import { KnowledgeGraph } from '../graph/KnowledgeGraph';
import type { TeachingStep, TutorMode, TutorSessionResponse } from '../../types/api';

import './TutorWorkspace.css';

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

export function TutorWorkspace() {
  const [question, setQuestion] = useState('How does PID reduce steady-state error?');
  const [graphId, setGraphId] = useState('graph-task-123');
  const [mode, setMode] = useState<TutorMode>('interactive');
  const [session, setSession] = useState<TutorSessionResponse | null>(null);
  const [responseText, setResponseText] = useState('');
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

  const graphIdForView = currentGraphId(session, graphId);
  const highlightedNodes = useMemo(
    () => activeStep?.content?.graphHighlights ?? [],
    [activeStep],
  );
  const { data: graphData, loading: graphLoading, error: graphError } = useKnowledgeGraph(graphIdForView);

  const startSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    try {
      setLoading(true);
      setError(null);
      const result = await apiClient.startTutorSession({
        question,
        pdfId: graphId,
        mode,
        context: { learning_level: 'intermediate' },
      });
      setSession(result);
      setResponseText('');
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
      setResponseText('');
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
      setResponseText('');
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
      setResponseText('');
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
      });
      setSession(result);
      setResponseText('');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const actionDisabled = loading || !session;

  return (
    <div className="tutor-page">
      <header className="tutor-page__hero">
        <h2 className="tutor-page__title">AI 导师</h2>
        <p className="tutor-page__subtitle">P3 内容生成与渲染链路：session step to content artifact to ContentRenderer</p>
      </header>

      <form className="tutor-page__start" onSubmit={startSession}>
        <input
          className="tutor-page__input"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="输入学习问题"
          required
        />
        <input
          className="tutor-page__input"
          value={graphId}
          onChange={(event) => setGraphId(event.target.value)}
          placeholder="graph id"
          required
        />
        <select
          className="tutor-page__select"
          value={mode}
          onChange={(event) => setMode(event.target.value as TutorMode)}
        >
          <option value="interactive">interactive</option>
          <option value="tutorial">tutorial</option>
          <option value="quiz">quiz</option>
          <option value="problem_solving">problem_solving</option>
        </select>
        <button className="tutor-page__button" type="submit" disabled={loading}>
          {loading ? '处理中...' : '启动会话'}
        </button>
      </form>

      {error && <div className="tutor-page__error">请求失败: {error}</div>}

      <div className="tutor-page__grid">
        <section className="tutor-page__panel">
          <div className="tutor-page__panel-header">
            <h3>{activeStep ? `当前步骤: ${activeStep.title}` : '内容渲染区'}</h3>
          </div>
          <div className="tutor-page__panel-body">
            <ContentRenderer
              artifact={artifact}
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

        <aside className="tutor-page__panel">
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
          </div>
        </aside>
      </div>

      <section className="tutor-page__panel" style={{ marginTop: '0.9rem' }}>
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
    </div>
  );
}
