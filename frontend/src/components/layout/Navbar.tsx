export function Navbar() {
  return (
    <nav style={{
      position: 'sticky',
      top: 0,
      zIndex: 100,
      backgroundColor: 'var(--bg-warm-sand)',
      borderBottom: '1px solid var(--border-warm)',
      padding: '0.75rem 1.5rem',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between'
    }}>
      <div style={{
        fontFamily: 'Georgia, serif',
        fontSize: '1.25rem',
        fontWeight: 500,
        color: 'var(--text-primary)'
      }}>
        控制理论导师
      </div>

      <div style={{
        display: 'flex',
        gap: '1.5rem',
        fontFamily: 'Inter, sans-serif',
        fontSize: '1rem',
        color: 'var(--text-secondary)'
      }}>
        <a href="/upload" style={{ textDecoration: 'none', color: 'inherit' }}>
          教材管理
        </a>
        <a href="/tutor" style={{ textDecoration: 'none', color: 'inherit' }}>
          AI 导师
        </a>
      </div>
    </nav>
  );
}
