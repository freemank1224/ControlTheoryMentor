function App() {
  return (
    <div className="app-container">
      <header className="app-header">
        <div className="container">
          <h1>控制理论导师</h1>
          <p className="subtitle">AI 驱动的个性化学习系统</p>
        </div>
      </header>

      <main className="app-main">
        <div className="container">
          <div className="welcome-section">
            <h2>欢迎来到控制理论学习平台</h2>
            <p>基于知识的自适应学习系统，助您掌握现代控制理论</p>

            <div className="feature-grid">
              <div className="feature-card">
                <div className="feature-icon">📚</div>
                <h3>知识图谱</h3>
                <p>系统化的控制理论知识体系</p>
              </div>

              <div className="feature-card">
                <div className="feature-icon">🎯</div>
                <h3>自适应学习</h3>
                <p>根据您的进度动态调整学习路径</p>
              </div>

              <div className="feature-card">
                <div className="feature-icon">💡</div>
                <h3>AI 导师</h3>
                <p>智能问答和概念讲解</p>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
