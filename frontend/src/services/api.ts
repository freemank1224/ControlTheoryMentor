import type {
  PDFUploadResponse,
  PDFStatusResponse,
  GraphDataResponse,
  TutorSessionRespondRequest,
  TutorSessionResponse,
  TutorSessionStart
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

class APIClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.statusText}`);
    }

    return response.json();
  }

  // PDF Management
  async uploadPDF(file: File): Promise<PDFUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${this.baseURL}/api/pdf/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('上传失败');
    }

    return response.json();
  }

  async getPDFStatus(id: string): Promise<PDFStatusResponse> {
    return this.request<PDFStatusResponse>(`/api/pdf/${id}/status`);
  }

  // Knowledge Graph
  async getGraph(graphId: string): Promise<GraphDataResponse> {
    return this.request<GraphDataResponse>(`/api/graph/${graphId}`);
  }

  // AI Tutor
  async startTutorSession(request: TutorSessionStart): Promise<TutorSessionResponse> {
    return this.request<TutorSessionResponse>('/api/tutor/session/start', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getTutorSession(sessionId: string): Promise<TutorSessionResponse> {
    return this.request<TutorSessionResponse>(`/api/tutor/session/${sessionId}`);
  }

  async nextTutorSessionStep(sessionId: string): Promise<TutorSessionResponse> {
    return this.request<TutorSessionResponse>(`/api/tutor/session/${sessionId}/next`, {
      method: 'POST',
    });
  }

  async respondToTutorSession(
    sessionId: string,
    request: TutorSessionRespondRequest,
  ): Promise<TutorSessionResponse> {
    return this.request<TutorSessionResponse>(`/api/tutor/session/${sessionId}/respond`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }
}

export const apiClient = new APIClient(API_BASE_URL);
