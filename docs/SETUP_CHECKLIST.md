# Setup Checklist - Agent Enterprise Pack

Use this checklist to ensure your development environment and CI/CD pipelines are properly configured.

## 📋 Local Development Setup

### Prerequisites
- [ ] Python 3.11+ installed
- [ ] Git installed
- [ ] Docker installed (optional, for containerized dev)
- [ ] GCP account created (for Vertex AI)

### UV Installation
- [ ] Install UV: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] Verify installation: `uv --version`
- [ ] Add UV to PATH (if needed)

### Project Setup
- [ ] Clone repository: `git clone <repo-url>`
- [ ] Navigate to project: `cd agent-enterprise-pack`
- [ ] Install dependencies: `uv sync --all-extras`
- [ ] Copy environment file: `cp .env.example .env`
- [ ] Edit `.env` with your values
- [ ] Generate JWT secret: `openssl rand -hex 32`

### Verify Installation
- [ ] Run tests: `make test` or `uv run pytest`
- [ ] Check linting: `make lint`
- [ ] Format code: `make format`
- [ ] Build Docker image: `make docker-build`
- [ ] Run application: `uv run python main.py`
- [ ] Test health endpoint: `curl http://localhost:8080/health`

---

## 🔧 GitHub Repository Setup

### Repository Configuration
- [ ] Create GitHub repository
- [ ] Push code to GitHub
- [ ] Set repository visibility (public/private)
- [ ] Add repository description
- [ ] Add topics/tags (python, ai, agents, google-adk)

### Branch Protection
- [ ] Enable branch protection for `main`
- [ ] Require PR reviews before merging
- [ ] Require status checks to pass
- [ ] Enable "Require branches to be up to date"
- [ ] Enable "Include administrators"

### GitHub Secrets
Navigate to: **Settings → Secrets and variables → Actions**

#### Required for CI (Basic)
- [ ] No secrets needed - CI works out of the box!

#### Required for CD (Deployment)
- [ ] `GCP_SA_KEY` - Service account JSON key
- [ ] `GCP_PROJECT_ID` - Your GCP project ID
- [ ] `GCP_REGION` - Deployment region (e.g., us-central1)
- [ ] `REDIS_URL` - Production Redis connection string

#### Optional
- [ ] `SLACK_WEBHOOK_URL` - Slack notifications
- [ ] `PYPI_API_TOKEN` - PyPI package publishing
- [ ] `CODECOV_TOKEN` - Codecov integration

---

## ☁️ Google Cloud Setup

### Enable APIs
```bash
gcloud services enable \
  run.googleapis.com \
  containerregistry.googleapis.com \
  aiplatform.googleapis.com \
  cloudmonitoring.googleapis.com \
  cloudtrace.googleapis.com
```

- [ ] Cloud Run API enabled
- [ ] Container Registry API enabled
- [ ] Vertex AI API enabled
- [ ] Cloud Monitoring API enabled
- [ ] Cloud Trace API enabled

### Create Service Account
```bash
gcloud iam service-accounts create agent-enterprise-ci \
  --display-name="Agent Enterprise CI/CD"
```

- [ ] Service account created
- [ ] Grant `roles/run.admin` permission
- [ ] Grant `roles/storage.admin` permission
- [ ] Grant `roles/aiplatform.user` permission
- [ ] Create and download JSON key
- [ ] Add key to GitHub secrets as `GCP_SA_KEY`

### Create Redis Instance
```bash
gcloud redis instances create agent-cache \
  --size=1 \
  --region=us-central1 \
  --redis-version=redis_7_0
```

- [ ] Redis instance created
- [ ] Note connection host and port
- [ ] Add connection string to GitHub secrets as `REDIS_URL`

### Create Secrets in Secret Manager
```bash
# JWT Secret
echo -n "$(openssl rand -hex 32)" | \
  gcloud secrets create jwt-secret --data-file=-

# Grant access
gcloud secrets add-iam-policy-binding jwt-secret \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

- [ ] JWT secret created in Secret Manager
- [ ] Service account has access to secrets
- [ ] (Optional) Slack webhook secret created

---

## 🚀 CI/CD Verification

### Test CI Pipeline
- [ ] Create feature branch: `git checkout -b test/ci-setup`
- [ ] Make a small change (e.g., update README)
- [ ] Commit: `git commit -m "test: verify CI pipeline"`
- [ ] Push: `git push origin test/ci-setup`
- [ ] Create Pull Request
- [ ] Verify CI workflow runs
- [ ] Check all jobs pass (lint, test, security, docker)
- [ ] Verify PR checks run
- [ ] Merge PR if all checks pass

### Test CD Pipeline (Optional)
- [ ] Ensure all GitHub secrets are configured
- [ ] Create version tag: `git tag -a v0.1.0 -m "Test release"`
- [ ] Push tag: `git push origin v0.1.0`
- [ ] Verify CD workflow runs
- [ ] Check Docker image builds and pushes to GCR
- [ ] Verify deployment to Cloud Run
- [ ] Test deployed service health endpoint
- [ ] Check Slack notification (if configured)

### Test Release Pipeline (Optional)
- [ ] Configure PyPI API token
- [ ] Create release tag: `git tag -a v1.0.0 -m "Release v1.0.0"`
- [ ] Push tag: `git push origin v1.0.0`
- [ ] Verify GitHub release created
- [ ] Check package published to PyPI
- [ ] Test installation: `pip install agent-enterprise-pack`

---

## 📊 Monitoring Setup

### Cloud Monitoring
- [ ] Navigate to Cloud Monitoring console
- [ ] Verify traces appearing in Cloud Trace
- [ ] Check metrics in Cloud Monitoring
- [ ] Review logs in Cloud Logging
- [ ] Set up alerting policies (optional)

### Codecov (Optional)
- [ ] Sign up at codecov.io
- [ ] Connect GitHub repository
- [ ] Add `CODECOV_TOKEN` to GitHub secrets
- [ ] Verify coverage reports uploading
- [ ] Add coverage badge to README

### Status Badges
Add to README.md:
```markdown
![CI](https://github.com/YOUR_ORG/agent-enterprise-pack/workflows/CI/badge.svg)
![CD](https://github.com/YOUR_ORG/agent-enterprise-pack/workflows/CD/badge.svg)
```

- [ ] CI badge added to README
- [ ] CD badge added to README
- [ ] Coverage badge added (if using Codecov)

---

## ✅ Final Verification

### Local Development
- [ ] Can run tests locally: `make test`
- [ ] Can run application locally: `uv run python main.py`
- [ ] Can build Docker image: `make docker-build`
- [ ] Can run with Docker Compose: `docker-compose up`

### CI/CD
- [ ] CI runs on every push
- [ ] PR checks validate pull requests
- [ ] CD deploys on tag push
- [ ] Deployments are successful
- [ ] Health checks pass

### Documentation
- [ ] README.md is up to date
- [ ] CONTRIBUTING.md reviewed
- [ ] Setup guides accessible
- [ ] Team members can follow setup instructions

---

## 🎉 You're All Set!

Congratulations! Your Agent Enterprise Pack is now fully configured with:
- ✅ UV package manager for fast dependency management
- ✅ Comprehensive test suite
- ✅ Automated CI/CD pipelines
- ✅ Production deployment to Cloud Run
- ✅ Monitoring and observability

### Next Steps:
1. Start developing features
2. Write tests for new code
3. Create pull requests
4. Let CI/CD handle the rest!

### Need Help?
- Check `docs/SETUP_GUIDE.md` for detailed instructions
- Review `docs/QUICK_REFERENCE.md` for command reference
- Open an issue on GitHub for support

