import { Component } from 'react';

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // In production, send this to an error tracking service (e.g. Sentry)
    console.error('Radius dashboard error:', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary" role="alert">
          <h2>Something went wrong</h2>
          <p>The dashboard encountered an unexpected error.</p>
          {this.state.error?.message && (
            <p className="error-boundary-detail">{this.state.error.message}</p>
          )}
          <button onClick={() => window.location.reload()}>
            Reload dashboard
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
