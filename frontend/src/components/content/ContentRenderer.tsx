import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import mermaid from 'mermaid';
import { BlockMath } from 'react-katex';
import 'katex/dist/katex.min.css';

import type { ContentArtifact, ContentArtifactType } from '../../types/api';

import './ContentRenderer.css';

interface ContentRendererProps {
  artifact: ContentArtifact | null;
  loading?: boolean;
  error?: string | null;
  fallbackMarkdown?: string;
}

function toLabel(type: ContentArtifactType): string {
  if (type === 'markdown') {
    return 'Markdown';
  }
  if (type === 'mermaid') {
    return 'Mermaid';
  }
  if (type === 'latex') {
    return 'LaTeX';
  }
  return 'Interactive';
}

function availableTypes(artifact: ContentArtifact | null): ContentArtifactType[] {
  if (!artifact) {
    return [];
  }

  const types: ContentArtifactType[] = [];
  if (artifact.markdown) {
    types.push('markdown');
  }
  if (artifact.mermaid) {
    types.push('mermaid');
  }
  if (artifact.latex) {
    types.push('latex');
  }
  if (artifact.interactive) {
    types.push('interactive');
  }
  return types;
}

export function ContentRenderer({ artifact, loading = false, error = null, fallbackMarkdown }: ContentRendererProps) {
  const types = useMemo(() => availableTypes(artifact), [artifact]);
  const [activeType, setActiveType] = useState<ContentArtifactType>('markdown');
  const [mermaidSvg, setMermaidSvg] = useState<string>('');
  const [mermaidError, setMermaidError] = useState<string | null>(null);

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: 'neutral',
      securityLevel: 'loose',
    });
  }, []);

  useEffect(() => {
    if (!artifact) {
      setActiveType('markdown');
      return;
    }

    if (types.length === 0) {
      setActiveType('markdown');
      return;
    }

    if (types.includes(artifact.renderHint)) {
      setActiveType(artifact.renderHint);
      return;
    }

    setActiveType(types[0]);
  }, [artifact, types]);

  useEffect(() => {
    let cancelled = false;

    async function renderMermaid() {
      if (activeType !== 'mermaid' || !artifact?.mermaid) {
        setMermaidSvg('');
        setMermaidError(null);
        return;
      }

      try {
        const renderId = `mermaid-${artifact.id.replace(/[^a-zA-Z0-9_-]/g, '')}`;
        const result = await mermaid.render(renderId, artifact.mermaid);
        if (!cancelled) {
          setMermaidSvg(result.svg);
          setMermaidError(null);
        }
      } catch (renderError) {
        if (!cancelled) {
          setMermaidError((renderError as Error).message);
          setMermaidSvg('');
        }
      }
    }

    void renderMermaid();

    return () => {
      cancelled = true;
    };
  }, [activeType, artifact?.id, artifact?.mermaid]);

  if (error) {
    return <div className="content-renderer content-renderer__error">内容加载失败: {error}</div>;
  }

  if (loading) {
    return <div className="content-renderer content-renderer__status">正在加载教学内容...</div>;
  }

  if (!artifact) {
    if (fallbackMarkdown) {
      return (
        <div className="content-renderer">
          <div className="content-renderer__body content-renderer__markdown">
            <ReactMarkdown>{fallbackMarkdown}</ReactMarkdown>
          </div>
        </div>
      );
    }
    return <div className="content-renderer content-renderer__empty">当前步骤暂无可渲染内容。</div>;
  }

  const renderMarkdown = artifact.markdown || fallbackMarkdown || '';

  return (
    <div className="content-renderer">
      <div className="content-renderer__tabs">
        {types.map((type) => (
          <button
            key={type}
            type="button"
            className={`content-renderer__tab ${activeType === type ? 'is-active' : ''}`}
            onClick={() => setActiveType(type)}
          >
            {toLabel(type)}
          </button>
        ))}
      </div>

      <div className="content-renderer__body">
        {activeType === 'markdown' && (
          <div className="content-renderer__markdown">
            <ReactMarkdown>{renderMarkdown}</ReactMarkdown>
          </div>
        )}

        {activeType === 'mermaid' && (
          <div>
            {mermaidError ? (
              <div className="content-renderer__error">Mermaid 渲染失败: {mermaidError}</div>
            ) : (
              <div dangerouslySetInnerHTML={{ __html: mermaidSvg }} />
            )}
          </div>
        )}

        {activeType === 'latex' && artifact.latex && (
          <div className="content-renderer__code">
            <BlockMath math={artifact.latex} />
          </div>
        )}

        {activeType === 'interactive' && artifact.interactive && (
          <div className="content-renderer__interactive">
            <strong>Interactive Placeholder</strong>
            <pre className="content-renderer__code">{JSON.stringify(artifact.interactive, null, 2)}</pre>
          </div>
        )}

        <div className="content-renderer__meta">
          状态: {artifact.status} | 更新时间: {new Date(artifact.updatedAt).toLocaleString()} | ID: {artifact.id}
        </div>
      </div>
    </div>
  );
}
