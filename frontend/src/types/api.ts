export interface PDFUploadResponse {
  id: string;
  taskId: string;
  filename: string;
  page_count: number;
  status: 'uploaded' | 'parsing' | 'completed' | 'failed';
}

export interface PDFStatusResponse {
  id: string;
  status: 'uploaded' | 'parsing' | 'completed' | 'failed';
  task_id?: string;
  task_status?: string;
  task_info?: Record<string, unknown>;
  graph_id?: string;
  task_error?: string;
}

export interface NodeData {
  id: string;
  label: string;
  type: string;
  description?: string;
}

export interface NodeElement {
  data: NodeData;
}

export interface EdgeData {
  id: string;
  source: string;
  target: string;
  label: string;
  relation?: string;
  confidence?: string;
}

export interface EdgeElement {
  data: EdgeData;
}

export interface GraphElements {
  nodes: NodeElement[];
  edges: EdgeElement[];
}

export interface GraphDataResponse {
  elements: GraphElements;
  metadata?: {
    graphId?: string;
    total_nodes?: number;
    total_edges?: number;
    reportPath?: string;
  };
}

export interface TutorSessionStart {
  question: string;
  pdfId: string;
  mode?: string;
  context?: Record<string, unknown>;
}

export interface TeachingStep {
  id: string;
  type: string;
  title: string;
  objective: string;
  content: Record<string, unknown>;
  relatedTopics?: string[];
  requiresResponse?: boolean;
}

export interface TeachingPlan {
  summary: string;
  goals: string[];
  steps: TeachingStep[];
}

export interface TutorSessionMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  metadata?: Record<string, unknown>;
}

export interface TutorSessionRespondRequest {
  response: string;
  metadata?: Record<string, unknown>;
}

export interface TutorSessionResponse {
  sessionId: string;
  plan: TeachingPlan;
  currentStep?: TeachingStep | null;
  currentStepIndex: number;
  status: string;
  messages: TutorSessionMessage[];
  canAdvance: boolean;
  needsUserResponse: boolean;
  feedback?: string | null;
  metadata?: Record<string, unknown>;
}
