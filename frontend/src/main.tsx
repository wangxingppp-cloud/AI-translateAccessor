import { Component, StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App';

// Error boundary to show React errors in the UI instead of a blank screen
class ErrorBoundary extends Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          height: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#0f1117',
          color: '#e1e1e6',
          fontFamily: 'system-ui, sans-serif',
          padding: '40px',
        }}>
          <h1 style={{ color: '#ef4444', marginBottom: '16px' }}>React 渲染错误</h1>
          <pre style={{
            background: '#1a1b23',
            padding: '20px',
            borderRadius: '8px',
            maxWidth: '700px',
            overflow: 'auto',
            fontSize: '13px',
            lineHeight: '1.6',
          }}>
            {this.state.error?.message}
            {'\n\n'}
            {this.state.error?.stack}
          </pre>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
