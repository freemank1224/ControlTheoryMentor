import { useState } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MainLayout } from './components/layout/MainLayout';
import { UploadCard } from './components/upload/UploadCard';
import { KnowledgeGraph } from './components/graph/KnowledgeGraph';
import { TutorWorkspace } from './components/tutor/TutorWorkspace';
import { useKnowledgeGraph } from './hooks/useKnowledgeGraph';

function HomePage() {
  const [currentGraphId, setCurrentGraphId] = useState<string | null>(null);

  const handleUploadComplete = (_taskId: string, graphId: string) => {
    setCurrentGraphId(graphId);
  };

  const { data: graphData, loading, error } = useKnowledgeGraph(currentGraphId || '');

  return (
    <div style={{ padding: '2rem' }}>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>系统初始化中...</p>
      <div style={{ marginBottom: '2rem' }}>
        <UploadCard onUploadComplete={handleUploadComplete} />
      </div>

      {loading && <p>加载知识图谱中...</p>}
      {error && <p style={{ color: 'red' }}>错误: {error.message}</p>}
      {graphData && (
        <div>
          <h2 style={{ fontFamily: 'Georgia, serif', marginBottom: '1rem' }}>
            知识图谱
          </h2>
          <KnowledgeGraph data={graphData} />
        </div>
      )}
    </div>
  );
}

function UploadPage() {
  return (
    <div style={{ padding: '2rem' }}>
      <UploadCard />
    </div>
  );
}

function TutorPage() {
  return <TutorWorkspace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <MainLayout>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/tutor" element={<TutorPage />} />
        </Routes>
      </MainLayout>
    </BrowserRouter>
  );
}
