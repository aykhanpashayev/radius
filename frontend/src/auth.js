import { Amplify } from 'aws-amplify';
import { signIn, signOut, getCurrentUser, fetchAuthSession } from 'aws-amplify/auth';

const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID;
const userPoolClientId = import.meta.env.VITE_COGNITO_CLIENT_ID;

if (userPoolId && userPoolClientId) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
        loginWith: { email: true },
      },
    },
  });
}

export { signOut, getCurrentUser, fetchAuthSession };

/**
 * Sign in and return true on success.
 * Throws with a user-friendly message on failure.
 */
export async function login(username, password) {
  const { isSignedIn, nextStep } = await signIn({ username, password });
  if (!isSignedIn) {
    // Handle force-change-password challenge (new admin-created users)
    if (nextStep?.signInStep === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED') {
      throw new Error('You must set a new password. Use the AWS CLI: aws cognito-idp admin-set-user-password --permanent');
    }
    throw new Error(`Sign-in incomplete: ${nextStep?.signInStep}`);
  }
  return true;
}

/**
 * Returns the current user's Cognito ID token string.
 * Returns null when Cognito is not configured (local dev without infra).
 * Throws 'Not authenticated' if configured but no active session.
 */
export async function getIdToken() {
  if (!userPoolId || !userPoolClientId) return null;
  const session = await fetchAuthSession({ forceRefresh: false });
  const token = session.tokens?.idToken?.toString();
  if (!token) throw new Error('Not authenticated');
  return token;
}
