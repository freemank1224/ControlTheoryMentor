import type {
  ContentGenerateRequest,
  ContentGenerateResponse,
  ContentInteractiveRequest,
  ContentTypedPayloadResponse,
  PDFUploadResponse,
  PDFStatusResponse,
  GraphDataResponse,
  TutorSessionJumpRequest,
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

  async backTutorSessionStep(sessionId: string): Promise<TutorSessionResponse> {
    return this.request<TutorSessionResponse>(`/api/tutor/session/${sessionId}/back`, {
      method: 'POST',
    });
  }

  async jumpTutorSessionStep(
    sessionId: string,
    request: TutorSessionJumpRequest,
  ): Promise<TutorSessionResponse> {
    return this.request<TutorSessionResponse>(`/api/tutor/session/${sessionId}/jump`, {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Content Artifacts
  async generateContent(request: ContentGenerateRequest): Promise<ContentGenerateResponse> {
    return this.request<ContentGenerateResponse>('/api/content/generate', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async generateInteractiveContent(request: ContentInteractiveRequest): Promise<ContentGenerateResponse> {
    return this.request<ContentGenerateResponse>('/api/content/interactive', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getContentArtifact(contentId: string): Promise<ContentGenerateResponse> {
    return this.request<ContentGenerateResponse>(`/api/content/${contentId}`);
  }

  async getContentMermaid(contentId: string): Promise<ContentTypedPayloadResponse> {
    return this.request<ContentTypedPayloadResponse>(`/api/content/${contentId}/mermaid`);
  }

  async getContentLatex(contentId: string): Promise<ContentTypedPayloadResponse> {
    return this.request<ContentTypedPayloadResponse>(`/api/content/${contentId}/latex`);
  }
}

export const apiClient = new APIClient(API_BASE_URL);
