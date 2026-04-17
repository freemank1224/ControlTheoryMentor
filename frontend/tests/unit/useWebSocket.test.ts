import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '@/hooks/useWebSocket';

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', class MockWebSocket {
      url: string;
      readyState: number = 0;

      constructor(url: string) {
        this.url = url;
        setTimeout(() => {
          this.readyState = 1;
          this.onopen?.(new Event('open'));
        }, 0);
      }

      send = vi.fn();
      close = vi.fn();
      onopen: ((event: Event) => void) | null = null;
      onmessage: ((event: MessageEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onclose: ((event: CloseEvent) => void) | null = null;
    });
  });

  it('should connect to WebSocket', async () => {
    const { result } = renderHook(() => useWebSocket('ws://localhost:8000/ws/test'));

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 10));
    });

    expect(result.current.status).toBe('connected');
  });

  it('should handle incoming messages', async () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() =>
      useWebSocket('ws://localhost:8000/ws/test', { onMessage })
    );

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 10));
      // Simulate message
      const ws = (global as any).WebSocket.mock.instances[0];
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({ type: 'task.progress', data: { percent: 50 } })
      }));
    });

    expect(onMessage).toHaveBeenCalledWith({ type: 'task.progress', data: { percent: 50 } });
  });
});
