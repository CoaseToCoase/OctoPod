# Colab Transcript Fetching Setup

## Overview

YouTube blocks transcript requests from cloud providers (AWS, GCP, Azure), which prevents GitHub Actions and Cloud Functions from fetching transcripts. Google Colab uses different IP addresses that work reliably.

## Workflow

1. **Colab**: Fetches transcripts, writes to GitHub
2. **GitHub Actions**: Picks up transcripts, analyzes, uploads to GCS, cleans up

## Setup Instructions

### 1. Get GitHub Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a name: `OctoPod Colab`
4. Select scopes: `repo` (full control of private repositories)
5. Click "Generate token"
6. **Copy the token** (you won't see it again)

### 2. Open Colab Notebook

1. Upload `colab_fetch_transcripts.ipynb` to Google Colab, or
2. Open directly: [Open in Colab](https://colab.research.google.com/github/CoaseToCoase/OctoPod/blob/master/colab_fetch_transcripts.ipynb)

### 3. Add GitHub Token to Colab Secrets

1. In Colab, click the **🔑 Secrets** icon in the left sidebar
2. Click **+ Add new secret**
3. Name: `GITHUB_TOKEN`
4. Value: Paste your GitHub token
5. Toggle "Notebook access" to ON

### 4. Run the Notebook

1. Click **Runtime** → **Run all**
2. The notebook will:
   - Clone the OctoPod repository
   - Find videos without transcripts
   - Fetch transcripts from YouTube
   - Commit results back to GitHub

### 5. Verify

Check the OctoPod repository - you should see a new commit with transcripts added.

## Usage

### Manual Run

Run the Colab notebook whenever you want to fetch transcripts (before GitHub Actions runs).

### Recommended Schedule

1. **Run Colab notebook** manually or via scheduled Colab (if available)
2. **GitHub Actions runs** automatically at 6 AM UTC daily
3. GitHub Actions will:
   - Pick up the transcripts from Colab
   - Analyze them with Claude
   - Upload results to GCS
   - Clean up data files (keep GitHub lean)

## Troubleshooting

**"No videos.json found"**
- Run `octopod --profile "Category Name" fetch --schedule` first to fetch videos

**"All videos have transcripts"**
- Great! Nothing to do. GitHub Actions will handle analysis.

**Git push fails**
- Check that GITHUB_TOKEN has `repo` scope
- Make sure the token is still valid

## Alternative: Scheduled Colab

If you have Colab Pro, you can schedule the notebook to run automatically before GitHub Actions (e.g., 5 AM UTC daily).
