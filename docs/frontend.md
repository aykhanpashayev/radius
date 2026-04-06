# Frontend Documentation

The Radius dashboard is a React 18 + Vite SPA hosted on S3 and served via CloudFront. Authentication is handled by AWS Cognito — users must sign in before accessing any data.

---

## Prerequisites

- Node.js 18 or later
- npm (bundled with Node)

---

## Authentication

The dashboard uses AWS Amplify to authenticate against a Cognito User Pool. On every API request, the Cognito ID token is attached as the `Authorization` header. API Gateway validates the token via a `COGNITO_USER_POOLS` authorizer — unauthenticated requests receive a 401.

The login flow:
1. User visits the dashboard — unauthenticated users are redirected to `/login`
2. `Login.jsx` calls `signIn()` from `src/auth.js` (Amplify)
3. On success, the app navigates to `/` and all subsequent API calls include the JWT
4. Tokens expire after 1 hour; Amplify handles refresh automatically via the refresh token (7-day validity)

User accounts are admin-created only — there is no self-registration.

---

## Local Development

Install dependencies:

```bash
cd frontend
npm ci
```

Start the dev server:

```bash
npm run dev
```

The app will be available at `http://localhost:5173` by default.

---

## Environment Variables

| Variable | Description |
|---|---|
| `VITE_API_BASE_URL` | Base URL of the Radius API Gateway endpoint |
| `VITE_COGNITO_USER_POOL_ID` | Cognito User Pool ID (e.g. `us-east-1_XXXXXXXXX`) |
| `VITE_COGNITO_CLIENT_ID` | Cognito App Client ID |

To configure locally, copy the example file:

```bash
cp frontend/.env.example frontend/.env.local
```

Get the values from Terraform after deploying:

```bash
terraform -chdir=infra/envs/dev output -raw api_endpoint
terraform -chdir=infra/envs/dev output -raw cognito_user_pool_id
terraform -chdir=infra/envs/dev output -raw cognito_client_id
```

Vite only exposes variables prefixed with `VITE_` to the browser bundle. Never put secrets in these files.

---

## Production Build

For production, use `scripts/build-frontend.sh` which pulls config from SSM Parameter Store and writes `.env.production` automatically:

```bash
bash scripts/build-frontend.sh --env prod --region us-east-1
```

This requires AWS credentials with `ssm:GetParameter` on `/radius/prod/*`. Output is written to `frontend/dist/`.

For a manual build:

```bash
cd frontend
npm run build
```

---

## Error Boundary

The app is wrapped in an `ErrorBoundary` component (`src/components/ErrorBoundary.jsx`) at the root level. If any component throws an unhandled error, the boundary catches it and renders a fallback UI with a reload button instead of a blank screen. Errors are logged to the console — in production, wire `componentDidCatch` to an error tracking service like Sentry.

---

## S3 Deployment

Sync the build output to your S3 bucket:

```bash
aws s3 sync dist/ s3://YOUR_BUCKET_NAME --delete
```

The `--delete` flag removes any files in the bucket that are no longer in the local build, keeping the bucket in sync with the latest build.

---

## CloudFront Invalidation

After deploying to S3, invalidate the CloudFront cache so users get the latest assets:

```bash
aws cloudfront create-invalidation \
  --distribution-id YOUR_DIST_ID \
  --paths "/*"
```

---

## CloudFront Custom Error Response (SPA Routing)

The app uses React Router with `BrowserRouter`. Configure CloudFront to return `index.html` with a 200 status for 403 and 404 errors so client-side routing works on direct URL access and page refresh:

```hcl
custom_error_response {
  error_code         = 403
  response_code      = 200
  response_page_path = "/index.html"
}

custom_error_response {
  error_code         = 404
  response_code      = 200
  response_page_path = "/index.html"
}
```
