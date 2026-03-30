import { Amplify } from 'aws-amplify';
import { signIn, signOut, getCurrentUser, fetchAuthSession } from 'aws-amplify/auth';

const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID;
const userPoolClientId = import.meta.env.VITE_COGNITO_CLIENT_ID;

// Only configure Amplify when Cognito env vars are present.
// Without them the app still loads — API calls will fail with 401
// until credentials are configured.
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

export { signIn, signOut, getCurrentUser, fetchAuthSession };

/**
 * Returns the current user's Cognito ID token string for use as
 * the Authorization header on API requests.
 * Returns null when Cognito is not configured (local dev without infra).
 */
export async function getIdToken() {
  if (!userPoolId || !userPoolClientId) {
    return null;
  }
  const session = await fetchAuthSession();
  const token = session.tokens?.idToken?.toString();
  if (!token) throw new Error('Not authenticated');
  return token;
}
