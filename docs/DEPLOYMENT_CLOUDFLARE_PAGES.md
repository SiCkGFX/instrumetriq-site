# Deploying to Cloudflare Pages

This guide explains how to deploy the Instrumetriq website to Cloudflare Pages using GitHub integration.

## Prerequisites

- A Cloudflare account (free tier works)
- GitHub repository with your site code
- The repository connected to your GitHub account

## Deployment Steps

### 1. Connect Your GitHub Repository

1. Log in to your [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Navigate to **Workers & Pages** in the left sidebar
3. Click **Create Application**
4. Select the **Pages** tab
5. Click **Connect to Git**
6. Authorize Cloudflare to access your GitHub account
7. Select the `instrumetriq-site` repository

### 2. Configure Build Settings

Use the following settings for your Astro site:

**Framework preset**: `Astro`

**Build command**:
```bash
npm run build
```

**Build output directory**:
```
dist
```

**Root directory**: `/` (leave as default)

**Environment variables** (optional):
- `NODE_VERSION`: `20` or `18` (recommended)

### 3. Deploy

1. Click **Save and Deploy**
2. Cloudflare will clone your repository and start the build
3. The first deployment usually takes 2-5 minutes
4. Once complete, you'll get a `*.pages.dev` URL

### 4. Custom Domain (Optional)

To use a custom domain:

1. Go to your Pages project settings
2. Navigate to **Custom domains**
3. Click **Set up a custom domain**
4. Enter your domain (e.g., `instrumetriq.com`)
5. Follow the DNS configuration instructions
6. Wait for DNS propagation (can take up to 24 hours)

## Automatic Deployments

Cloudflare Pages automatically deploys:

- **Production**: Every push to the `main` branch
- **Preview**: Every pull request (creates a unique preview URL)

This means you can review changes before merging to production.

## Build Configuration

### Node Version

If you need to specify a Node version, add it as an environment variable:

1. Go to **Settings** → **Environment variables**
2. Add variable: `NODE_VERSION` = `20`
3. Apply to **Production** and **Preview** environments

### Build Time Optimization

The site is static and builds are fast (usually < 30 seconds):

- No runtime dependencies
- Minimal JavaScript
- Pre-rendered at build time

## Performance

Cloudflare Pages provides:

- **Global CDN**: Fast delivery worldwide
- **Automatic HTTPS**: Free SSL certificates
- **HTTP/3 & Brotli**: Modern protocols enabled by default
- **Atomic deploys**: No partial updates, safe rollbacks

## Rollback

To rollback to a previous deployment:

1. Go to your Pages project
2. Click **Deployments** tab
3. Find the deployment you want to restore
4. Click **...** → **Rollback to this deployment**

## Environment-Specific Configuration

If you need different settings for preview vs. production:

1. Use environment variables in **Settings**
2. Create separate values for **Production** and **Preview**
3. Access them in your code via `import.meta.env`

## Troubleshooting

### Build Fails

Check the build logs in the Cloudflare dashboard:
- Verify Node version compatibility
- Ensure all dependencies are in `package.json`
- Check for TypeScript errors

### 404 Errors

Astro generates a 404.html automatically. If you see Cloudflare's default 404:
- Verify the build output directory is set to `dist`
- Check that the build completed successfully

### Slow Builds

- Builds should be fast (< 1 minute typically)
- If slow, check for large dependencies
- Consider optimizing imports

## Additional Resources

- [Cloudflare Pages Docs](https://developers.cloudflare.com/pages/)
- [Astro Deployment Guide](https://docs.astro.build/en/guides/deploy/cloudflare/)
- [Cloudflare Community](https://community.cloudflare.com/)

## Support

For deployment issues:
1. Check the Cloudflare build logs
2. Review the [Cloudflare status page](https://www.cloudflarestatus.com/)
3. Contact Cloudflare support through the dashboard
