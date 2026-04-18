/* @vitest-environment jsdom */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import { ContentRenderer } from './ContentRenderer';
import type { ContentArtifact } from '../../types/api';

const artifact: ContentArtifact = {
  id: 'content-123',
  status: 'ready',
  renderHint: 'markdown',
  targetContentTypes: ['markdown', 'latex'],
  markdown: '## Demo Step\n\nMarkdown body.',
  mermaid: null,
  latex: 'e(t)=r(t)-y(t)',
  interactive: null,
  source: {
    stage: 'concept',
    stepId: 'step-2',
    stepTitle: '拆解核心概念',
    objective: '目标',
    question: 'Question',
    graphId: 'graph-task-123',
    sessionMode: 'interactive',
    learnerLevel: 'beginner',
    responseMode: 'passive',
    primaryConceptId: null,
    conceptIds: ['concept-pid'],
    highlightedNodeIds: ['concept-pid'],
    evidencePassageIds: ['chunk-pid-1'],
    targetContentTypes: ['markdown', 'latex'],
    renderHint: 'markdown',
  },
  cacheKey: 'cache-key',
  createdAt: '2026-04-18T00:00:00+00:00',
  updatedAt: '2026-04-18T00:00:00+00:00',
  metadata: { store: 'memory-test' },
};

describe('ContentRenderer', () => {
  it('renders markdown content by default', () => {
    render(<ContentRenderer artifact={artifact} />);

    expect(screen.getByText('Demo Step')).toBeInTheDocument();
    expect(screen.getByText('Markdown body.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Markdown' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'LaTeX' })).toBeInTheDocument();
  });

  it('falls back to markdown placeholder when artifact is missing', () => {
    render(<ContentRenderer artifact={null} fallbackMarkdown="Fallback text" />);

    expect(screen.getByText('Fallback text')).toBeInTheDocument();
  });
});
