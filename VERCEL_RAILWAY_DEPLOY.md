# Deploy with Vercel (Frontend) + Railway (Backend)

This is the best free option for Project Aegis Ghost.

## Architecture
- **Frontend**: Vercel (free, global CDN, SSL)
- **Backend**: Railway ($5/month or $5 credit on free tier)

---

## Step 1: Deploy Backend on Railway

### Option A: From Railway Dashboard
1. Go to https://railway.app/dashboard
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your repository
4. Add Environment Variables:
   ```
   PYTHONUNBUFFERED=1
   PORT=8000
   ```
5. Click **"Deploy"**

### Option B: Using Railway CLI
```bash
npm i -g @railway/cli
railway login
railway init
railway up
```

### Get Railway URL
After deployment, you'll get a URL like:
`https://aegis-ghost-production.up.railway.app`

---

## Step 2: Update Frontend API

Edit `frontend/src/services/api.js`:
```javascript
export const API_BASE_URL = "https://your-railway-app.up.railway.app";
```

Rebuild the frontend:
```bash
cd frontend
npm run build
```

---

## Step 3: Deploy Frontend on Vercel

### Option A: From Vercel Dashboard
1. Go to https://vercel.com/dashboard
2. Click **"Add New..."** → **"Project"**
3. Import your GitHub repository
4. Configure:
   - Framework Preset: `Create React App` (or `Other`)
   - Build Command: `npm run build` (or leave blank)
   - Output Directory: `build`
5. Click **"Deploy"**

### Option B: Using Vercel CLI
```bash
npm i -g vercel
cd frontend
vercel
```

### Get Vercel URL
After deployment, you'll get a URL like:
`https://aegis-ghost.vercel.app`

---

## Step 4: Test Your App

1. Open your Vercel URL
2. The frontend will communicate with Railway backend
3. All features should work!

---

## Pricing

| Platform | Free Tier |
|----------|-----------|
| Vercel | 100GB bandwidth/month, SSL, global CDN |
| Railway | $5 credit/month (enough for ~500 hours) |

---

## Troubleshooting

### CORS Errors
If frontend can't reach backend, add CORS headers in server.py:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-vercel-app.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Build Errors on Vercel
- Make sure `frontend/build/` folder exists
- Check that package.json has `"homepage": "."`

### Railway App Sleeps
Railway's free tier sleeps after 15 min of inactivity. To keep it awake:
- Set up a cron job to ping your app every 10 minutes
- Or upgrade to paid tier ($$5/month)

---

## Quick Commands Summary

```bash
# Build frontend
cd frontend
npm run build

# Deploy backend
railway up

# Deploy frontend
vercel --prod
```
