import { useState, useEffect } from 'react';
import { apiClient } from '../services/api';
import type { GraphDataResponse } from '../types/api';

export function useKnowledgeGraph(pdfId: string) {
  const [data, setData] = useState<GraphDataResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!pdfId) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }

    async function fetchGraph() {
      try {
        setLoading(true);
        setError(null);
        const graph = await apiClient.getGraph(pdfId);
        setData(graph);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    }

    fetchGraph();
  }, [pdfId]);

  return { data, loading, error };
}
