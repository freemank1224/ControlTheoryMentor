import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useKnowledgeGraph } from '@/hooks/useKnowledgeGraph';
import { apiClient } from '@/services/api';

vi.mock('@/services/api');

describe('useKnowledgeGraph', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch graph data', async () => {
    const mockGraphData = {
      elements: {
        nodes: [{ data: { id: 'c1', label: 'Test', type: 'concept' }}],
        edges: []
      }
    };

    vi.mocked(apiClient.getGraph).mockResolvedValue(mockGraphData);

    const { result } = renderHook(() => useKnowledgeGraph('pdf-123'));

    await waitFor(() => {
      expect(result.current.data).toEqual(mockGraphData);
      expect(result.current.loading).toBe(false);
    });
  });

  it('should handle loading state', () => {
    vi.mocked(apiClient.getGraph).mockImplementation(() => new Promise(() => {}));

    const { result } = renderHook(() => useKnowledgeGraph('pdf-123'));

    expect(result.current.loading).toBe(true);
  });

  it('should handle errors', async () => {
    vi.mocked(apiClient.getGraph).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useKnowledgeGraph('pdf-123'));

    await waitFor(() => {
      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.loading).toBe(false);
    });
  });
});
