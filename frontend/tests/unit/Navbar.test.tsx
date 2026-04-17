import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Navbar } from '@/components/layout/Navbar';

describe('Navbar', () => {
  it('should render logo and navigation', () => {
    render(<Navbar />);
    expect(screen.getByText('控制理论导师')).toBeInTheDocument();
  });

  it('should render navigation links', () => {
    render(<Navbar />);
    expect(screen.getByText('教材管理')).toBeInTheDocument();
    expect(screen.getByText('AI 导师')).toBeInTheDocument();
  });
});
