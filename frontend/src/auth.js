import { signIn, signOut, getCurrentUser, fetchAuthSession } from 'aws-amplify/auth';

// Amplify is configured in main.jsx before the app renders.
// This module only exports auth helpers.

export { signOut, getCurrentUser, fetchAuthSession };

/**
 * Sign in and return true on success.
 * Throws with a user-friendly message on failure.
 */
export async function login(username, password) {
  const { isSignedIn, nextStep } = await signIn({ username, password });
  if (!isSignedIn) {
    if (nextStep?.signInStep === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED') {
      throw new Error('You must set a permanent password first. Run: aws cognito-idp admin-set-user-password --permanent');
    }
    throw new Error(`Sign-in incomplete: ${nextStep?.signInStep}`);
  }
  return true;
}

/**
 * Returns the current user's Cognito ID token for API requests.
 * Returns null when Cognito env vars are not set (local dev without infra).
 */
export async function getIdToken() {
  const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID;
  if (!userPoolId) return null;
  const session = await fetchAuthSession({ forceRefresh: false });
  const token = session.tokens?.idToken?.toString();
  if (!token) throw new Error('Not authenticated');
  return token;
}
