import { ReactNode } from 'react';
import { Navbar } from './Navbar';

interface MainLayoutProps {
  children: ReactNode;
}

export function MainLayout({ children }: MainLayoutProps) {
  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: 'var(--bg-parchment)',
      color: 'var(--text-primary)'
    }}>
      <Navbar />
      <main>
        {children}
      </main>
    </div>
  );
}
