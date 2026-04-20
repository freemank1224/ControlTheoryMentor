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
    domainCompatibility?: GraphDomainCompatibility;
  };
}

export interface GraphDomainCompatibility {
  expectedDomain: string;
  detectedDomain: string;
  compatible: boolean;
  reason: string;
  strict: boolean;
  confidence: number;
  matchedKeywords?: string[];
  signalCount?: number;
  minSignalRequired?: number;
  documentTitles?: string[];
  introPreview?: string[];
  domainPromptSeed?: string;
}

export interface TutorSessionStart {
  question: string;
  pdfId: string;
  learnerId?: string;
  mode?: TutorMode;
  domainStrict?: boolean;
  context?: Record<string, unknown>;
  courseTypeStrategy?: CourseTypeStrategy;
  courseTypeOverride?: CourseType;
  courseType?: CourseType;
}

export type TutorMode = 'interactive' | 'tutorial' | 'quiz' | 'problem_solving';

export type CourseType = 'knowledge_learning' | 'problem_solving';

export type CourseTypeStrategy = 'auto' | 'manual' | 'override';

export interface CourseTypeDecision {
  decision: CourseType;
  confidence: number;
  signals: string[];
  overridden: boolean;
}

export interface TutorAnalyzeRequest {
  question: string;
  pdfId: string;
  learnerId?: string;
  mode?: TutorMode;
  context?: Record<string, unknown>;
  limit?: number;
  courseTypeStrategy?: CourseTypeStrategy;
  courseTypeOverride?: CourseType;
  courseType?: CourseType;
}

export interface TutorAnalyzeResponse {
  graphId: string;
  question: string;
  summary: string;
  relevantConcepts: Array<{
    node: { id: string; label: string };
    matchScore: number;
    summary: string;
    prerequisitesCount: number;
    relatedCount: number;
  }>;
  highlightedNodeIds: string[];
  evidencePassages: Array<{
    chunkId: string;
    conceptId: string;
    conceptLabel: string;
    sourceFile: string;
    sourceLocation?: string | null;
    pageStart?: number | null;
    pageEnd?: number | null;
    excerpt: string;
    score: number;
  }>;
  suggestedSession: Record<string, unknown>;
  metadata: {
    finalCourseType?: CourseType;
    autoDecision?: CourseTypeDecision;
    courseTypeDecision?: CourseTypeDecision;
    courseTypeStrategy?: CourseTypeStrategy;
    courseTypeOverride?: CourseType | null;
  } & Record<string, unknown>;
}

export type ContentArtifactType =
  | 'markdown'
  | 'mermaid'
  | 'latex'
  | 'image'
  | 'comic'
  | 'animation'
  | 'interactive';

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
  evidenceExcerpts?: string[];
  domainLabel?: string | null;
  domainConfidence?: number | null;
  sourceDocumentTitles?: string[];
  sourceIntroPreview?: string[];
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

export interface ModalityPlan {
  primary: ContentArtifactType;
  secondary: ContentArtifactType[];
  responseMode: ContentRequestResponseMode;
  interactionMode: string;
  rationale: string;
}

export interface CheckpointSpec {
  checkpointId: string;
  kind: string;
  prompt: string;
  expectedEvidence: string[];
  passThreshold: number;
  retryHint: string;
}

export interface TeachingStep {
  id: string;
  type: string;
  title: string;
  objective: string;
  content: TeachingStepContent;
  modalityPlan?: ModalityPlan;
  checkpointSpec?: CheckpointSpec | null;
  relatedTopics?: string[];
  requiresResponse?: boolean;
}

export interface TeachingPlan {
  summary: string;
  goals: string[];
  steps: TeachingStep[];
  planFinalized?: boolean;
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
  image?: Record<string, unknown> | null;
  comic?: Record<string, unknown> | null;
  animation?: Record<string, unknown> | null;
  interactive?: Record<string, unknown> | null;
  source: TeachingContentRequest;
  cacheKey: string;
  createdAt: string;
  updatedAt: string;
  metadata: Record<string, unknown>;
}

export interface ContentGenerationParams {
  style?: string;
  detail?: string;
  pace?: string;
  attempt?: number;
  imagePrompt?: string;
  imageTimeoutMs?: number;
}

export interface ContentGenerateRequest {
  contentRequest: TeachingContentRequest;
  forceRegenerate?: boolean;
  generationParams?: ContentGenerationParams;
}

export interface ContentInteractiveRequest {
  contentRequest: TeachingContentRequest;
  interactionMode?: string;
  generationParams?: ContentGenerationParams;
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

export type LearningEventType =
  | 'session_started'
  | 'step_started'
  | 'step_completed'
  | 'step_response'
  | 'content_viewed'
  | 'parameter_adjusted'
  | 'session_completed';

export type FeedbackDifficulty = 'too_easy' | 'appropriate' | 'too_hard';

export interface LearningEventRecord {
  id: string;
  eventType: LearningEventType;
  timestamp: string;
  sessionId?: string | null;
  stepId?: string | null;
  conceptId?: string | null;
  confidence?: number | null;
  masteryDelta: number;
  metadata: Record<string, unknown>;
}

export interface ConceptMasteryState {
  conceptId: string;
  score: number;
  level: 'not_started' | 'developing' | 'practicing' | 'mastered';
  updatedAt: string;
}

export interface LearningFeedbackEntry {
  id: string;
  learnerId: string;
  graphId: string;
  sessionId?: string | null;
  stepId?: string | null;
  conceptId?: string | null;
  rating: number;
  difficulty: FeedbackDifficulty;
  comment?: string | null;
  metadata: Record<string, unknown>;
  createdAt: string;
}

export interface LearningProgress {
  learnerId: string;
  graphId: string;
  sessionId?: string | null;
  currentStepId?: string | null;
  completedStepIds: string[];
  masteryByConcept: Record<string, number>;
  conceptMastery: ConceptMasteryState[];
  masteredConceptIds: string[];
  pendingReviewConceptIds: string[];
  feedbackCount: number;
  averageFeedbackRating?: number | null;
  eventCount: number;
  lastEventType?: LearningEventType | null;
  lastActivityAt: string;
  recentEvents: LearningEventRecord[];
  recentFeedback: LearningFeedbackEntry[];
  metadata: Record<string, unknown>;
}

export interface LearningTrackRequest {
  learnerId: string;
  graphId: string;
  sessionId?: string;
  stepId?: string;
  conceptId?: string;
  eventType: LearningEventType;
  masteryDelta?: number;
  confidence?: number;
  completedStep?: boolean;
  metadata?: Record<string, unknown>;
}

export interface LearningTrackResponse {
  progress: LearningProgress;
  event: LearningEventRecord;
}

export interface LearningProgressResponse {
  progress: LearningProgress;
}

export interface LearningFeedbackRequest {
  learnerId: string;
  graphId: string;
  sessionId?: string;
  stepId?: string;
  conceptId?: string;
  rating: number;
  difficulty: FeedbackDifficulty;
  comment?: string;
  metadata?: Record<string, unknown>;
}

export interface LearningFeedbackResponse {
  progress: LearningProgress;
  feedback: LearningFeedbackEntry;
}
