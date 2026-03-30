import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { getCurrentUser } from '../auth';

export default function RequireAuth({ children }) {
  const [status, setStatus] = useState('checking'); // checking | authed | unauthed

  useEffect(() => {
    getCurrentUser()
      .then(() => setStatus('authed'))
      .catch(() => setStatus('unauthed'));
  }, []);

  if (status === 'checking') return null; // avoid flash
  if (status === 'unauthed') return <Navigate to="/login" replace />;
  return children;
}
