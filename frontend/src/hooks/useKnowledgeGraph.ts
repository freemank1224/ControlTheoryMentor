import { useState, useEffect } from 'react';
import { apiClient } from '@/services/api';
import type { GraphDataResponse } from '@/types/api';

export function useKnowledgeGraph(pdfId: string) {
  const [data, setData] = useState<GraphDataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    async function fetchGraph() {
      try {
        setLoading(true);
        const graph = await apiClient.getGraph(pdfId);
        setData(graph);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    if (pdfId) {
      fetchGraph();
    }
  }, [pdfId]);

  return { data, loading, error };
}
