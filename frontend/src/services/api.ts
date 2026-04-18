import type {
  ContentGenerateRequest,
  ContentGenerateResponse,
  ContentInteractiveRequest,
  ContentTypedPayloadResponse,
  LearningFeedbackRequest,
  LearningFeedbackResponse,
  LearningProgressResponse,
  LearningTrackRequest,
  LearningTrackResponse,
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
      let message = `API Error: ${response.status}`;
      const contentType = response.headers.get('content-type') || '';

      try {
        if (contentType.includes('application/json')) {
          const payload = await response.json() as {
            detail?: string | { message?: string };
            message?: string;
          };

          if (typeof payload.detail === 'string' && payload.detail) {
            message = `API Error: ${payload.detail}`;
          } else if (payload.detail && typeof payload.detail === 'object' && payload.detail.message) {
            message = `API Error: ${payload.detail.message}`;
          } else if (typeof payload.message === 'string' && payload.message) {
            message = `API Error: ${payload.message}`;
          } else {
            message = `API Error: ${response.status}`;
          }
        } else {
          const text = (await response.text()).trim();
          if (text) {
            message = `API Error: ${text}`;
          }
        }
      } catch {
        message = `API Error: ${response.status}`;
      }

      throw new Error(message);
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

  // Learning Loop
  async trackLearningEvent(request: LearningTrackRequest): Promise<LearningTrackResponse> {
    return this.request<LearningTrackResponse>('/api/learning/track', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  async getLearningProgress(learnerId: string, graphId: string): Promise<LearningProgressResponse> {
    const params = new URLSearchParams({ learnerId, graphId });
    return this.request<LearningProgressResponse>(`/api/learning/progress?${params.toString()}`);
  }

  async submitLearningFeedback(request: LearningFeedbackRequest): Promise<LearningFeedbackResponse> {
    return this.request<LearningFeedbackResponse>('/api/learning/feedback', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }
}

export const apiClient = new APIClient(API_BASE_URL);
