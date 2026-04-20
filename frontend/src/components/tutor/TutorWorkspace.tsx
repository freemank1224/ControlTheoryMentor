import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { apiClient } from '../../services/api';
import { useContentArtifact } from '../../hooks/useContentArtifact';
import { useKnowledgeGraph } from '../../hooks/useKnowledgeGraph';
import { ContentRenderer } from '../content/ContentRenderer';
import { KnowledgeGraph } from '../graph/KnowledgeGraph';
import type {
  ContentArtifact,
  GraphDomainCompatibility,
  TeachingStep,
  TutorSessionResponse,
} from '../../types/api';

import './TutorWorkspace.css';

const DEFAULT_TUTOR_GRAPH_ID = import.meta.env.VITE_DEFAULT_GRAPH_ID || '';
const GENERATION_STAGE_LABELS = [
  '检查上传资料',
  '理解学习目标',
  '规划课程结构',
  '生成第一节内容',
] as const;

type GenerationStageStatus = 'pending' | 'active' | 'done' | 'error';

interface GenerationStage {
  label: string;
  status: GenerationStageStatus;
}

function buildInitialGenerationStages(): GenerationStage[] {
  return GENERATION_STAGE_LABELS.map((label) => ({ label, status: 'pending' }));
}

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
  const [searchParams] = useSearchParams();
  const queryGraphId = searchParams.get('graphId') || '';
  const storedGraphId = window.localStorage.getItem('latestGraphId') || '';
  const initialGraphId = queryGraphId || DEFAULT_TUTOR_GRAPH_ID || storedGraphId;

  const [question, setQuestion] = useState('');
  const [graphId, setGraphId] = useState(initialGraphId);
  const [session, setSession] = useState<TutorSessionResponse | null>(null);
  const [responseText, setResponseText] = useState('');
  const [responseConfidence, setResponseConfidence] = useState('medium');
  const [overrideArtifact, setOverrideArtifact] = useState<ContentArtifact | null>(null);
  const [generationStages, setGenerationStages] = useState<GenerationStage[]>(buildInitialGenerationStages());
  const [subtitleLines, setSubtitleLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const subtitleFeedRef = useRef<HTMLDivElement | null>(null);
  const activeStageRef = useRef<number>(0);

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
  const highlightedNodes = useMemo(
    () => activeStep?.content?.graphHighlights ?? [],
    [activeStep],
  );
  const { data: graphData, loading: graphLoading, error: graphError } = useKnowledgeGraph(graphIdForView);
  const graphDomainCompatibility = useMemo<GraphDomainCompatibility | null>(() => {
    return graphData?.metadata?.domainCompatibility ?? null;
  }, [graphData]);
  const graphDomainMismatch = Boolean(
    graphDomainCompatibility && !graphDomainCompatibility.compatible,
  );
  const graphDomainMismatchBlocked = graphDomainMismatch;
  const completedStageCount = generationStages.filter((stage) => stage.status === 'done').length;
  const activeStage = generationStages.find((stage) => stage.status === 'active') ?? null;

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

  useEffect(() => {
    if (subtitleFeedRef.current) {
      subtitleFeedRef.current.scrollTop = subtitleFeedRef.current.scrollHeight;
    }
  }, [subtitleLines]);

  const appendSubtitleLine = (stageIndex: number, line: string) => {
    const prefix = stageIndex >= 0
      ? `【${stageIndex + 1}/${GENERATION_STAGE_LABELS.length}】 `
      : '';
    setSubtitleLines((previous) => [...previous, `${prefix}${line}`].slice(-24));
  };

  const resetGenerationProgress = () => {
    setGenerationStages(buildInitialGenerationStages());
    setSubtitleLines([]);
    activeStageRef.current = 0;
  };

  const updateStageStatus = (stageIndex: number, status: GenerationStageStatus, line?: string) => {
    setGenerationStages((previous) => {
      const next = [...previous];
      if (next[stageIndex]) {
        next[stageIndex] = {
          ...next[stageIndex],
          status,
        };
      }
      return next;
    });
    if (status === 'active') {
      activeStageRef.current = stageIndex;
    }
    if (line) {
      appendSubtitleLine(stageIndex, line);
    }
  };

  const startSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    resetGenerationProgress();
    if (graphDomainMismatchBlocked) {
      setError('当前你上传的 PDF 与预设的控制理论课程不相关，请先上传控制理论相关资料。');
      updateStageStatus(0, 'error', '检测到上传资料与控制理论课程不相关，请更换资料后重试。');
      return;
    }
    try {
      setLoading(true);
      setError(null);
      updateStageStatus(0, 'active', '正在检查上传资料是否可用于控制理论课程...');
      updateStageStatus(0, 'done', '资料检查通过。');

      updateStageStatus(1, 'active', '正在理解你的学习目标...');
      const result = await apiClient.startTutorSession({
        question,
        pdfId: graphId,
        mode: 'interactive',
        context: { learning_level: 'intermediate' },
        courseTypeStrategy: 'auto',
      });
      updateStageStatus(1, 'done', '学习目标理解完成。');

      updateStageStatus(2, 'active', '正在规划课程结构...');
      updateStageStatus(2, 'done', `已规划 ${Math.max(result.plan.steps.length, 1)} 个学习阶段。`);

      updateStageStatus(3, 'active', '正在生成第一节课程内容...');
      const hydrated = await apiClient.nextTutorSessionStep(result.sessionId);
      setSession(hydrated);
      setResponseText('');
      updateStageStatus(3, 'done', '课程已准备好，可以开始学习。');
      appendSubtitleLine(-1, '全部阶段已完成。');
    } catch (err) {
      setError((err as Error).message);
      updateStageStatus(activeStageRef.current, 'error', '当前阶段执行失败，请稍后重试。');
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
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setOverrideArtifact(null);
  }, [contentId]);

  const actionDisabled = loading || !session;

  return (
    <div className="tutor-page">
      <header className="tutor-page__hero">
        <h2 className="tutor-page__title">AI 导师</h2>
        <p className="tutor-page__subtitle">输入你的学习问题，系统会自动生成可学习的课程步骤，并实时展示生成进度。</p>
      </header>

      <form className="tutor-page__start" onSubmit={startSession}>
        <input
          className="tutor-page__input"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="输入学习问题"
          required
        />
        <button className="tutor-page__button" type="submit" disabled={loading || graphDomainMismatchBlocked}>
          {loading ? '处理中...' : '生成课程'}
        </button>
        <div className="tutor-page__helper">当前资料编号: {graphId || '未选择'}</div>
        {graphDomainCompatibility?.compatible && (
          <div className="tutor-page__domain-status tutor-page__domain-status--ok">
            资料检查通过：当前上传 PDF 与控制理论课程方向相关。
          </div>
        )}
        {graphDomainMismatch && (
          <div className="tutor-page__domain-status tutor-page__domain-status--warn">
            当前你上传的 PDF 与预设的控制理论课程不相关，请上传控制理论相关资料后再生成课程。
          </div>
        )}
      </form>

      {error && <div className="tutor-page__error">请求失败: {error}</div>}

      <div className="tutor-page__grid">
        <section className="tutor-page__panel">
          <div className="tutor-page__panel-header">
            <h3>{activeStep ? `当前步骤: ${activeStep.title}` : '会话展示区'}</h3>
          </div>
          <div className="tutor-page__panel-body">
            <div className="tutor-page__progress-board">
              <div className="tutor-page__progress-head">
                <strong>课程生成进度</strong>
                <span>{completedStageCount}/{generationStages.length}</span>
              </div>
              <div className="tutor-page__progress-now">
                {loading && activeStage
                  ? `当前阶段：${activeStage.label}`
                  : session
                    ? '课程准备完成，可开始学习或继续下一步。'
                    : '点击“生成课程”后，这里会实时显示后台进度。'}
              </div>
              <div className="tutor-page__subtitle-feed" ref={subtitleFeedRef}>
                {subtitleLines.length > 0 ? subtitleLines.map((line, index) => (
                  <div key={`${line}-${index}`} className="tutor-page__subtitle-line">{line}</div>
                )) : (
                  <div className="tutor-page__subtitle-empty">等待开始生成课程...</div>
                )}
              </div>
              <div className="tutor-page__stage-track">
                {generationStages.map((stage) => (
                  <span
                    key={stage.label}
                    className={`tutor-page__stage-chip tutor-page__stage-chip--${stage.status}`}
                  >
                    {stage.label}
                  </span>
                ))}
              </div>
            </div>

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
                          <p className="tutor-page__step-meta">点击查看该学习步骤</p>
                        </button>
                      );
                    })}
                  </div>

                  <div className="tutor-page__status">
                    学习进度：第 {Math.max(session.currentStepIndex + 1, 0)} / {session.plan.steps.length} 步
                  </div>

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
                <div className="tutor-page__status">点击“生成课程”后，这里会显示课程步骤和会话记录。</div>
              )}
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
