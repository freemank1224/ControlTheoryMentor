import { useState, useRef, useEffect } from 'react';
import { apiClient } from '../../services/api';

interface UploadCardProps {
  onUploadComplete?: (taskId: string, graphId: string) => void;
}

interface TaskProgressDetails {
  stage?: string;
  stageLabel?: string;
  stageIndex?: number;
  stageTotal?: number;
  currentFile?: string;
  currentFileIndex?: number;
  totalFiles?: number;
  currentChunkIndex?: number;
  totalChunks?: number;
  sourceLocation?: string;
  cachedFiles?: number;
  pendingFiles?: number;
  semanticCacheHits?: number;
  semanticCacheMisses?: number;
}

function resolveWebSocketUrl(taskId: string): string {
  const explicitWsBase = import.meta.env.VITE_WS_BASE_URL;
  if (explicitWsBase) {
    return `${explicitWsBase.replace(/\/$/, '')}/ws/graph/${taskId}`;
  }

  const apiBase = import.meta.env.VITE_API_BASE_URL;
  if (apiBase) {
    const wsBase = apiBase.replace(/^http/, 'ws').replace(/\/$/, '');
    return `${wsBase}/ws/graph/${taskId}`;
  }

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/graph/${taskId}`;
}

export function UploadCard({ onUploadComplete }: UploadCardProps) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [completedGraphId, setCompletedGraphId] = useState<string | null>(null);
  const [completedTaskId, setCompletedTaskId] = useState<string | null>(null);
  const [progressDetails, setProgressDetails] = useState<TaskProgressDetails>({});
  const [pdfId, setPdfId] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const completedTaskRef = useRef<string | null>(null);

  const applyProgressUpdate = (data: Record<string, unknown>) => {
    setProgress(typeof data.percent === 'number' ? data.percent : 0);
    setMessage(typeof data.message === 'string' ? data.message : '处理中...');
    setProgressDetails({
      stage: typeof data.stage === 'string' ? data.stage : undefined,
      stageLabel: typeof data.stageLabel === 'string' ? data.stageLabel : undefined,
      stageIndex: typeof data.stageIndex === 'number' ? data.stageIndex : undefined,
      stageTotal: typeof data.stageTotal === 'number' ? data.stageTotal : undefined,
      currentFile: typeof data.currentFile === 'string' ? data.currentFile : undefined,
      currentFileIndex: typeof data.currentFileIndex === 'number' ? data.currentFileIndex : undefined,
      totalFiles: typeof data.totalFiles === 'number' ? data.totalFiles : undefined,
      currentChunkIndex: typeof data.currentChunkIndex === 'number' ? data.currentChunkIndex : undefined,
      totalChunks: typeof data.totalChunks === 'number' ? data.totalChunks : undefined,
      sourceLocation: typeof data.sourceLocation === 'string' ? data.sourceLocation : undefined,
      cachedFiles: typeof data.cachedFiles === 'number' ? data.cachedFiles : undefined,
      pendingFiles: typeof data.pendingFiles === 'number' ? data.pendingFiles : undefined,
      semanticCacheHits: typeof data.semanticCacheHits === 'number' ? data.semanticCacheHits : undefined,
      semanticCacheMisses: typeof data.semanticCacheMisses === 'number' ? data.semanticCacheMisses : undefined,
    });
  };

  const handleTaskCompleted = (activeTaskId: string, graphId: string) => {
    if (completedTaskRef.current === activeTaskId) {
      return;
    }

    const resolvedGraphId = graphId || activeTaskId;
    window.localStorage.setItem('latestGraphId', resolvedGraphId);
    window.localStorage.setItem('latestTaskId', activeTaskId);

    completedTaskRef.current = activeTaskId;
    setProgress(100);
    setMessage('处理完成！');
    setErrorMessage(null);
    setCompletedTaskId(activeTaskId);
    setCompletedGraphId(resolvedGraphId);
    setProgressDetails({
      stage: 'completed',
      stageLabel: '处理完成'
    });
    setUploading(false);
    onUploadComplete?.(activeTaskId, resolvedGraphId);
  };

  const handleTaskFailed = (error: string) => {
    setErrorMessage('处理失败：' + error);
    setUploading(false);
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf')) {
      alert('请上传 PDF 文件');
      return;
    }

    setErrorMessage(null);
    setUploading(true);
    setProgress(0);
    setPdfId(null);
    setTaskId(null);
    setCompletedGraphId(null);
    setCompletedTaskId(null);
    completedTaskRef.current = null;
    setMessage('正在上传...');
    setProgressDetails({
      stage: 'upload',
      stageLabel: '上传文件'
    });

    try {
      const result = await apiClient.uploadPDF(file);
      setPdfId(result.id);
      setTaskId(result.taskId);
      setMessage('处理中...');
    } catch (error) {
      setErrorMessage('上传失败：' + (error as Error).message);
      setUploading(false);
    }

    event.target.value = '';
  };

  // Handle WebSocket connection separately
  useEffect(() => {
    if (taskId && uploading) {
      const wsUrl = resolveWebSocketUrl(taskId);
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'task.progress') {
            applyProgressUpdate(data.data);
          } else if (data.type === 'task.completed') {
            handleTaskCompleted(taskId, data.data.graphId || taskId);
          } else if (data.type === 'task.failed') {
            handleTaskFailed(data.data.error);
          }
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.onclose = () => {
        console.log('WebSocket closed');
      };

      return () => {
        ws.close();
      };
    }
  }, [taskId, uploading, onUploadComplete]);

  useEffect(() => {
    if (!pdfId || !taskId || !uploading) {
      return;
    }

    let cancelled = false;

    const pollStatus = async () => {
      try {
        const status = await apiClient.getPDFStatus(pdfId);
        if (cancelled) {
          return;
        }

        const taskInfo = status.task_info;
        if (status.task_status === 'SUCCESS') {
          handleTaskCompleted(taskId, status.graph_id || (typeof taskInfo?.graph_id === 'string' ? taskInfo.graph_id : taskId));
          return;
        }

        if (status.task_status === 'FAILURE') {
          handleTaskFailed(typeof status.task_error === 'string' ? status.task_error : '解析任务失败');
          return;
        }

        if (taskInfo && typeof taskInfo === 'object') {
          applyProgressUpdate(taskInfo as Record<string, unknown>);
        }
      } catch (error) {
        console.error('Failed to poll PDF status:', error);
        const message = error instanceof Error ? error.message : '无法获取任务状态';
        handleTaskFailed(`状态查询失败：${message}`);
      }
    };

    pollStatus();
    const intervalId = window.setInterval(pollStatus, 2000);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [pdfId, taskId, uploading]);

  return (
    <div style={{
      backgroundColor: 'var(--bg-ivory)',
      border: '1px solid var(--border-cream)',
      borderRadius: 'var(--card-radius)',
      padding: '2rem',
      maxWidth: '500px',
      margin: '0 auto'
    }}>
      <h2 style={{
        fontFamily: 'Georgia, serif',
        fontSize: '1.5rem',
        color: 'var(--text-primary)',
        marginBottom: '1.5rem'
      }}>
        上传教材 PDF
      </h2>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        onChange={handleFileSelect}
        disabled={uploading}
        style={{ display: 'none' }}
      />

      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
        style={{
          width: '100%',
          padding: '0.75rem',
          backgroundColor: uploading ? 'var(--bg-warm-sand)' : 'var(--accent-terracotta)',
          color: uploading ? 'var(--text-secondary)' : 'var(--bg-ivory)',
          border: 'none',
          borderRadius: 'var(--btn-radius)',
          fontSize: '1rem',
          cursor: uploading ? 'not-allowed' : 'pointer',
          fontFamily: 'Inter, sans-serif'
        }}
      >
        {uploading ? '处理中...' : '选择 PDF 文件'}
      </button>

      {uploading && (
        <div style={{ marginTop: '1rem' }}>
          <div style={{
            width: '100%',
            height: '4px',
            backgroundColor: 'var(--border-cream)',
            borderRadius: '2px',
            overflow: 'hidden'
          }}>
            <div style={{
              width: `${progress}%`,
              height: '100%',
              backgroundColor: 'var(--accent-terracotta)',
              transition: 'width 0.3s ease'
            }} />
          </div>
          <p style={{
            marginTop: '0.5rem',
            fontSize: '0.875rem',
            color: 'var(--text-secondary)',
            fontFamily: 'Inter, sans-serif'
          }}>
            {message} ({progress}%)
          </p>

          <div style={{
            marginTop: '0.75rem',
            padding: '0.75rem 1rem',
            backgroundColor: 'var(--bg-warm-sand)',
            borderRadius: 'var(--btn-radius)',
            fontSize: '0.875rem',
            color: 'var(--text-primary)',
            lineHeight: 1.5,
            fontFamily: 'Inter, sans-serif'
          }}>
            <div><strong>当前阶段：</strong>{progressDetails.stageLabel || '处理中'}</div>
            {typeof progressDetails.stageIndex === 'number' && typeof progressDetails.stageTotal === 'number' && (
              <div>阶段进度：{progressDetails.stageIndex}/{progressDetails.stageTotal}</div>
            )}
            {progressDetails.currentFile && (
              <div>当前文件：{progressDetails.currentFile}</div>
            )}
            {typeof progressDetails.currentFileIndex === 'number' && typeof progressDetails.totalFiles === 'number' && (
              <div>文件进度：{progressDetails.currentFileIndex}/{progressDetails.totalFiles}</div>
            )}
            {typeof progressDetails.currentChunkIndex === 'number' && typeof progressDetails.totalChunks === 'number' && (
              <div>分块进度：{progressDetails.currentChunkIndex}/{progressDetails.totalChunks}</div>
            )}
            {progressDetails.sourceLocation && (
              <div>当前位置：{progressDetails.sourceLocation}</div>
            )}
            {typeof progressDetails.cachedFiles === 'number' && typeof progressDetails.pendingFiles === 'number' && (
              <div>抽取计划：缓存命中 {progressDetails.cachedFiles}，待处理 {progressDetails.pendingFiles}</div>
            )}
            {typeof progressDetails.semanticCacheHits === 'number' && typeof progressDetails.semanticCacheMisses === 'number' && (
              <div>抽取结果：缓存命中 {progressDetails.semanticCacheHits}，新抽取 {progressDetails.semanticCacheMisses}</div>
            )}
            {taskId && <div>任务 ID：{taskId}</div>}
          </div>
        </div>
      )}

      {!uploading && errorMessage && (
        <div style={{
          marginTop: '1rem',
          padding: '0.75rem 1rem',
          borderRadius: 'var(--btn-radius)',
          backgroundColor: '#FDECEC',
          border: '1px solid #E6B8B8',
          color: '#8A2F2F',
          fontSize: '0.875rem',
          lineHeight: 1.5,
          fontFamily: 'Inter, sans-serif'
        }}>
          <strong>处理失败</strong>
          <div>{errorMessage}</div>
          {progress > 0 && <div>失败前进度：{progress}%</div>}
          {taskId && <div>任务 ID：{taskId}</div>}
        </div>
      )}

      {!uploading && !errorMessage && completedGraphId && (
        <div style={{
          marginTop: '1rem',
          padding: '0.75rem 1rem',
          borderRadius: 'var(--btn-radius)',
          backgroundColor: '#ECF8F0',
          border: '1px solid #B7DEC4',
          color: '#1D5E35',
          fontSize: '0.875rem',
          lineHeight: 1.5,
          fontFamily: 'Inter, sans-serif'
        }}>
          <strong>解析完成</strong>
          <div>graphId: {completedGraphId}</div>
          {completedTaskId && <div>taskId: {completedTaskId}</div>}
          <div style={{ marginTop: '0.5rem' }}>
            <a
              href={`/tutor?graphId=${encodeURIComponent(completedGraphId)}`}
              style={{ color: '#1D5E35', textDecoration: 'underline', fontWeight: 600 }}
            >
              进入导师页面并自动带入该图谱
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
