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
  mode?: TutorMode;
  context?: Record<string, unknown>;
}

export type TutorMode = 'interactive' | 'tutorial' | 'quiz' | 'problem_solving';

export type ContentArtifactType = 'markdown' | 'mermaid' | 'latex' | 'interactive';

export type ContentRequestResponseMode = 'passive' | 'interactive';

export interface TutorEvidencePassage {
  chunkId: string;
  conceptId: string;
  conceptLabel: string;
  sourceFile: string;
  sourceLocation?: string | null;
  pageStart?: number | null;
  pageEnd?: number | null;
  excerpt: string;
  score: number;
}

export interface TeachingContentRequest {
  stage: string;
  stepId: string;
  stepTitle: string;
  objective: string;
  question: string;
  graphId: string;
  sessionMode: TutorMode;
  learnerLevel: string;
  responseMode: ContentRequestResponseMode;
  primaryConceptId?: string | null;
  conceptIds: string[];
  highlightedNodeIds: string[];
  evidencePassageIds: string[];
  targetContentTypes: ContentArtifactType[];
  renderHint: ContentArtifactType;
}

export interface TeachingStepContent {
  markdown?: string;
  guidingQuestion?: string;
  prompt?: string;
  nextActions?: string[];
  graphHighlights?: string[];
  evidencePassages?: TutorEvidencePassage[];
  contentRequest?: TeachingContentRequest;
  contentArtifactId?: string | null;
  contentArtifactStatus?: string | null;
  contentArtifactUpdatedAt?: string | null;
}

export interface TeachingStep {
  id: string;
  type: string;
  title: string;
  objective: string;
  content: TeachingStepContent;
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

export interface TutorSessionJumpRequest {
  stepIndex?: number;
  stepId?: string;
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

export type ContentArtifactStatus = 'ready' | 'pending' | 'failed';

export interface ContentArtifact {
  id: string;
  status: ContentArtifactStatus;
  renderHint: ContentArtifactType;
  targetContentTypes: ContentArtifactType[];
  markdown?: string | null;
  mermaid?: string | null;
  latex?: string | null;
  interactive?: Record<string, unknown> | null;
  source: TeachingContentRequest;
  cacheKey: string;
  createdAt: string;
  updatedAt: string;
  metadata: Record<string, unknown>;
}

export interface ContentGenerateRequest {
  contentRequest: TeachingContentRequest;
  forceRegenerate?: boolean;
}

export interface ContentInteractiveRequest {
  contentRequest: TeachingContentRequest;
  interactionMode?: string;
}

export interface ContentGenerateResponse {
  artifact: ContentArtifact;
  cacheHit: boolean;
}

export interface ContentTypedPayloadResponse {
  id: string;
  type: ContentArtifactType;
  status: ContentArtifactStatus;
  content: string;
  metadata: Record<string, unknown>;
}
