import { useState, useRef, useEffect } from 'react';
import { apiClient } from '@/services/api';
import { useWebSocket } from '@/hooks/useWebSocket';

interface UploadCardProps {
  onUploadComplete?: (taskId: string, graphId: string) => void;
}

export function UploadCard({ onUploadComplete }: UploadCardProps) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [taskId, setTaskId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf')) {
      alert('请上传 PDF 文件');
      return;
    }

    setUploading(true);
    setProgress(0);
    setMessage('正在上传...');

    try {
      const result = await apiClient.uploadPDF(file);
      setTaskId(result.taskId);
      setMessage('处理中...');
    } catch (error) {
      setMessage('上传失败：' + (error as Error).message);
      setUploading(false);
    }
  };

  // Handle WebSocket connection separately
  useEffect(() => {
    if (taskId && uploading) {
      const ws = new WebSocket(`ws://localhost:8000/ws/graph/${taskId}`);

      ws.onopen = () => {
        console.log('WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'task.progress') {
            setProgress(data.data.percent || 0);
            setMessage(data.data.message || '处理中...');
          } else if (data.type === 'task.completed') {
            setProgress(100);
            setMessage('处理完成！');
            setUploading(false);
            onUploadComplete?.(taskId, data.data.graphId);
          } else if (data.type === 'task.failed') {
            setMessage('处理失败：' + data.data.error);
            setUploading(false);
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
        </div>
      )}
    </div>
  );
}
