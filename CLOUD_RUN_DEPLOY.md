# Deploy to Google Cloud Run

This guide walks you through deploying Project Aegis Ghost to Google Cloud Run.

## Prerequisites

1. **Google Cloud Account** - Sign up at https://cloud.google.com
2. **Google Cloud SDK** - Install from https://cloud.google.com/sdk/docs/install
3. **Docker** - Install Docker Desktop

## Quick Deploy (5 minutes)

### Step 1: Authenticate with Google Cloud

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

### Step 2: Enable Required APIs

```bash
gcloud services enable cloudrun.googleapis.com containerregistry.googleapis.com
```

### Step 3: Create a .dockerignore File

Create a `.dockerignore` file in the project root to exclude unnecessary files:

```
# Git
.git
.gitignore

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info
dist
build

# Virtual environments
venv
env
.venv

# IDE
.vscode
.idea
*.swp
*.swo

# Frontend build (already built)
frontend/node_modules
frontend/build

# Data and logs
data/audit
data/output_stego
data/secure_tmp
*.log

# Documentation
*.md
!README.md

# OS
.DS_Store
Thumbs.db
```

### Step 4: Deploy to Cloud Run

```bash
# Build and deploy in one command
gcloud run deploy aegis-ghost \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --port 3000 \
  --set-env-vars PYTHONUNBUFFERED=1,RATE_LIMIT_PER_MIN=120,MAX_UPLOAD_MB=15
```

Or manually:

```bash
# Build the container
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/aegis-ghost

# Deploy to Cloud Run
gcloud run deploy aegis-ghost \
  --image gcr.io/YOUR_PROJECT_ID/aegis-ghost \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 3000
```

## Environment Variables

Set these in Cloud Run console or via `--set-env-vars`:

| Variable | Default | Description |
|----------|---------|-------------|
| `PYTHONUNBUFFERED` | 1 | Enable unbuffered output |
| `RATE_LIMIT_PER_MIN` | 120 | API rate limit |
| `MAX_UPLOAD_MB` | 15 | Max upload size |
| `DATA_RETENTION_DAYS` | 30 | Data retention period |
| `GEMINI_API_KEY` | - | (Optional) Gemini API key |
| `OPENAI_API_KEY` | - | (Optional) OpenAI API key |
| `DEEPAI_API_KEY` | - | (Optional) DeepAI API key |

## Cost Estimation

- **Cloud Run**: ~$0.00024 per vCPU-second + ~$0.00002 per GB-second
- **Cloud Storage**: ~$0.020 per GB/month for any uploaded files
- **Estimated cost**: $5-25/month for moderate usage

## Important Notes

1. **Stateless**: Cloud Run instances are stateless. Uploaded files will be lost on restart unless you use Cloud Storage
2. **Session**: For production, add Redis/SQL for session management
3. **Security**: Add authentication (`--auth-unauthenticated=false`) for production
4. **HTTPS**: Cloud Run automatically provides HTTPS

## Troubleshooting

### Image too large
```bash
# Optimize Docker build
docker build --target builder -t aegis-ghost .
```

### Memory issues
Increase memory in Cloud Run settings to 1GB or more.

### Missing dependencies
Ensure `requirements.txt` is complete. Install locally first:
```bash
pip install -r requirements.txt
```
