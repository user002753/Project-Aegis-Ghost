# Deploy to Railway.com

Railway is a modern deployment platform that handles Python apps with complex dependencies (like dlib, face_recognition) better than Render.

## Prerequisites
1. **GitHub Account** - Code pushed to GitHub
2. **Railway Account** - Sign up at https://railway.app

## Deployment Steps

### Step 1: Push Code to GitHub
```bash
git remote add origin https://github.com/user002753/New-Project.git
git add .
git commit -m "Prepare for Railway deployment"
git push -u origin main
```

### Step 2: Deploy on Railway

**Option A: From Railway Dashboard**
1. Go to https://railway.app/dashboard
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Select your `New-Project` repository
5. Railway will auto-detect Python and install dependencies
6. Add Environment Variables:
   - `PYTHONUNBUFFERED=1`
   - `PORT=8000`
   - `GEMINI_API_KEY=your_key_here` (optional)
7. Click **"Deploy"**

**Option B: Using Railway CLI**
```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Init project
railway init

# Deploy
railway up
```

### Step 3: Configure Start Command

In Railway dashboard, under the **Settings** tab:
- Start Command: `python -m uvicorn server:app --host 0.0.0.0 --port $PORT`

### Step 4: Set Environment Variables

Add these in Railway dashboard → Variables:
```
PYTHONUNBUFFERED=1
PORT=8000
# Optional API keys:
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key
```

## Pricing
- **Free Tier**: $5 credit/month (~500 hours)
- **Paid**: Starts at $5/month for always-on

## After Deployment
1. Get your Railway URL (e.g., `https://aegis-ghost-production.up.railway.app`)
2. Update frontend API URL in `frontend/src/services/api.js` if needed
3. Rebuild frontend: `cd frontend && npm run build`

## Troubleshooting

### Build Fails
- Check Build Logs in Railway dashboard
- Make sure `requirements.txt` is correct

### App Crashes
- Check Runtime Logs
- Ensure `PORT` environment variable is used

### Database/Storage Issues
- Railway's free tier doesn't persist files - use external storage
- For persistent data, add a PostgreSQL or MySQL plugin

## Advantages over Render
✅ Better Python package support (including dlib)
✅ Simpler UI
✅ Better error logs
✅ Automatic/SSL
