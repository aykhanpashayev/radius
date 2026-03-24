# Frontend Documentation

The Radius dashboard is a React 18 + Vite SPA hosted on S3 and served via CloudFront.

---

## Prerequisites

- Node.js 18 or later
- npm (bundled with Node)

---

## Local Development

Install dependencies:

```bash
cd frontend
npm install
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
| `VITE_API_BASE_URL` | Base URL of the Radius API Gateway endpoint (e.g. `https://abc123.execute-api.us-east-1.amazonaws.com/dev`) |

To configure locally, copy the example file and fill in your value:

```bash
cp frontend/.env.example frontend/.env.local
```

Then edit `.env.local`:

```
VITE_API_BASE_URL=https://your-api-id.execute-api.us-east-1.amazonaws.com/dev
```

Vite only exposes variables prefixed with `VITE_` to the browser bundle. Never put secrets in these files.

---

## Production Build

```bash
cd frontend
npm run build
```

Output is written to `frontend/dist/`. This directory contains the static assets ready for deployment.

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

Replace `YOUR_DIST_ID` with your CloudFront distribution ID.

---

## CloudFront Custom Error Response (SPA Routing)

The app uses React Router with `BrowserRouter`, which relies on client-side routing. When a user navigates directly to a path like `/incidents` or refreshes the page, CloudFront will attempt to fetch that path from S3 and receive a 403 or 404 — because only `index.html` exists at the root.

To fix this, configure CloudFront to return `index.html` with a 200 status for 403 and 404 errors:

1. Open your CloudFront distribution in the AWS Console.
2. Go to the **Error Pages** tab.
3. Create a custom error response for **403**:
   - HTTP error code: `403`
   - Response page path: `/index.html`
   - HTTP response code: `200`
4. Repeat for **404** with the same settings.

React Router will then handle the route client-side once `index.html` loads.

You can also configure this in Terraform using the `custom_error_response` block on your `aws_cloudfront_distribution` resource:

```hcl
custom_error_response {
  error_code            = 403
  response_code         = 200
  response_page_path    = "/index.html"
}

custom_error_response {
  error_code            = 404
  response_code         = 200
  response_page_path    = "/index.html"
}
```
