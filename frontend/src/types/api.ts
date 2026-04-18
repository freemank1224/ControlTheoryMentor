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
}

export interface TeachingStep {
  id: string;
  type: string;
  title: string;
  content: any;
}

export interface TutorSessionResponse {
  sessionId: string;
  plan: {
    steps: TeachingStep[];
  };
  currentStep?: string;
  status: string;
}
