export default function App() {
  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--bg-parchment)' }}>
      <header style={{ padding: '1rem 2rem', borderBottom: '1px solid var(--border-warm)' }}>
        <h1 style={{
          fontFamily: 'Georgia, serif',
          fontSize: '1.5rem',
          color: 'var(--text-primary)'
        }}>
          控制理论导师
        </h1>
      </header>
      <main style={{ padding: '2rem' }}>
        <p>系统初始化中...</p>
      </main>
    </div>
  );
}
