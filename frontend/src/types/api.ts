export interface PDFUploadResponse {
  taskId: string;
  filename: string;
  status: 'processing' | 'completed' | 'failed';
}

export interface PDFStatusResponse {
  id: string;
  filename: string;
  status: 'processing' | 'completed' | 'failed';
  pageCount?: number;
  uploadTime: string;
  graphId?: string;
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
  source: string;
  target: string;
  label: string;
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
