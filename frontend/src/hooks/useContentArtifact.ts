import { useEffect, useState } from 'react';

import { apiClient } from '../services/api';
import type { ContentArtifact } from '../types/api';

interface UseContentArtifactResult {
  artifact: ContentArtifact | null;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

export function useContentArtifact(contentId: string | null | undefined): UseContentArtifactResult {
  const [artifact, setArtifact] = useState<ContentArtifact | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchArtifact = async () => {
    if (!contentId) {
      setArtifact(null);
      setError(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getContentArtifact(contentId);
      setArtifact(response.artifact);
    } catch (err) {
      setError(err as Error);
      setArtifact(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchArtifact();
  }, [contentId]);

  return {
    artifact,
    loading,
    error,
    refresh: fetchArtifact,
  };
}
