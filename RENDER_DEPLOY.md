# Deploy to Render.com (Free)

This guide walks you through deploying Project Aegis Ghost to Render.com's free tier.

## Prerequisites

1. **GitHub Account** - Push your code to GitHub
2. **Render.com Account** - Sign up at https://render.com

## Deployment Steps

### Step 1: Prepare Your Code

Make sure these files are in your repository:

- ✅ `server.py` - Main application
- ✅ `requirements.txt` - Python dependencies  
- ✅ `Dockerfile` - Already exists
- ✅ Frontend built in `frontend/build/` - Already built

### Step 2: Push to GitHub

```bash
# Initialize git if not done
git init
git add .
git commit -m "Prepare for deployment"

# Create GitHub repo and push
git remote add origin https://github.com/YOUR_USERNAME/Project_Aegis_Ghost.git
git push -u origin main
```

### Step 3: Connect to Render

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub account
4. Select your `Project_Aegis_Ghost` repository
5. Configure the settings:

| Setting | Value |
|---------|-------|
| Name | `aegis-ghost` |
| Environment | `Python` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python -m uvicorn server:app --host 0.0.0.0 --port 10000` |
| Free Instance | ✅ Yes |

### Step 4: Set Environment Variables

In Render dashboard, go to **"Environment"** tab and add:

```
PYTHONUNBUFFERED=1
RATE_LIMIT_PER_MIN=120
MAX_UPLOAD_MB=15
DATA_RETENTION_DAYS=30
```

(Optional) Add your API keys:
```
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
DEEPAI_API_KEY=your_key_here
```

### Step 5: Deploy

Click **"Create Web Service"**

Wait 2-5 minutes for build and deploy. You'll get a URL like:
`https://aegis-ghost.onrender.com`

## Important Notes for Free Tier

### Limitations:
- **Sleep after 15 min** - Free instances sleep after 15 minutes of inactivity
- **750 hours/month** - That's about 24/25 usage
- **No persistent storage** - Uploaded files are lost on restart

### Fix for Sleep Issue:
Add a free uptime monitor like https://cron-job.org to ping your site every 14 minutes.

## After Deployment

Update your frontend API URL in:
- `frontend/src/services/api.js` - Change `API_BASE_URL` to your Render URL

Then rebuild and deploy:
```bash
cd frontend
npm run build
# Deploy the build folder to Render as Static Site
```

Or better - just update the frontend to use relative URLs so it works with any backend.

## Troubleshooting

### 502 Bad Gateway
- Check logs in Render dashboard
- Ensure start command is correct: `python -m uvicorn server:app --host 0.0.0.0 --port 10000`

### Import Errors
- Ensure `requirements.txt` has all dependencies
- Check Python version (use Python 3.11)

### File Upload Issues
- Free tier doesn't support large uploads well
- Consider using external storage like Cloudinary for files
