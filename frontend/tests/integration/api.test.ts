import { describe, it, expect, vi, beforeEach } from 'vitest';
import { apiClient } from '@/services/api';

// Mock fetch
global.fetch = vi.fn();

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should upload PDF', async () => {
    const mockFile = new File(['%PDF-1.4'], 'test.pdf', { type: 'application/pdf' });
    const mockResponse = {
      taskId: 'task-123',
      filename: 'test.pdf',
      status: 'processing'
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const result = await apiClient.uploadPDF(mockFile);
    expect(result.taskId).toBe('task-123');
    expect(result.filename).toBe('test.pdf');
  });

  it('should get PDF status', async () => {
    const mockResponse = {
      id: 'pdf-123',
      filename: 'test.pdf',
      status: 'completed',
      pageCount: 100,
      uploadTime: '2024-01-01T00:00:00Z'
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const result = await apiClient.getPDFStatus('pdf-123');
    expect(result.id).toBe('pdf-123');
    expect(result.status).toBe('completed');
  });

  it('should get graph data', async () => {
    const mockResponse = {
      elements: {
        nodes: [
          { data: { id: 'c1', label: 'Test', type: 'concept' }}
        ],
        edges: []
      }
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const result = await apiClient.getGraph('pdf-123');
    expect(result.elements.nodes).toHaveLength(1);
    expect(result.elements.nodes[0].data.label).toBe('Test');
  });

  it('should start tutor session', async () => {
    const mockRequest = {
      question: 'What is a PID controller?',
      pdfId: 'pdf-123'
    };

    const mockResponse = {
      sessionId: 'session-123',
      plan: { steps: [] },
      status: 'ready'
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse
    });

    const result = await apiClient.startTutorSession(mockRequest);
    expect(result.sessionId).toBe('session-123');
    expect(result.status).toBe('ready');
  });

  it('should handle API errors', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: false,
      statusText: 'Not Found'
    });

    await expect(apiClient.getPDFStatus('invalid')).rejects.toThrow();
  });
});
