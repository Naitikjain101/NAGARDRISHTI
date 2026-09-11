# Urban Watch Production Runbook

This runbook outlines the steps to securely deploy the Urban Watch Command Center into a production environment using Docker and Supabase.

## 1. Prerequisites

- **Docker & Docker Compose**: Installed on the target server.
- **Supabase**: A Supabase project initialized with the Urban Watch schema.
- **Models**: The Ultralytics `.pt` weight files placed in `backend/weights/`.

## 2. Environment Configuration

Create a `.env` file in the repository root (see `.env.example`).

```bash
# FRONTEND
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_public_anon_key
VITE_API_BASE_URL=https://api.yourdomain.com

# BACKEND
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_secret_service_key
FRONTEND_ORIGIN=https://yourdomain.com
```

**Security Warning**: Never expose `SUPABASE_SERVICE_ROLE_KEY` to the client browser. It must only be injected into the backend Docker container.

## 3. Database Initialization

Navigate to your Supabase SQL Editor and execute `backend/db/schema.sql`. This will:
1. Create all relational tables (`ai_jobs`, `incidents`, `buses`, etc.).
2. Initialize the `urban_watch_evidence` private storage bucket.
3. Lock down writes using Row Level Security (RLS) while allowing public scoped reads via Signed URLs.

## 4. Production Deployment

To launch the multi-container stack:

```bash
docker-compose up -d --build
```

### Services Started:
- **frontend** (Port 80): Nginx serving the highly optimized React/Vite SPA.
- **backend** (Port 8000): FastAPI worker nodes ready to process AI jobs.

## 5. Local Development vs Production

### Local Mac (Apple Silicon MPS) Development
Docker on Mac cannot natively passthrough the MPS hardware accelerator for PyTorch. For optimal local development speed, run the backend natively:

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Run frontend locally:
```bash
cd frontend-react
npm install
npm run dev
```

### Production (Linux / CUDA)
In a production Linux environment with NVIDIA GPUs, Docker can easily passthrough CUDA resources. Update `docker-compose.yml` to include `deploy: resources: reservations: devices` to map the GPU into the `backend` container.

## 6. Storage & Cleanup Policies

- **Videos**: Uploaded temporarily to local disk during active OpenCV parsing, then securely pushed to Supabase `urban_watch_evidence`. Local disk is cleaned on failure or deletion.
- **Incident Evidence**: Result JSONs and frames are kept permanently in Supabase unless explicitly deleted.

## 7. Health Checks

Production load balancers (e.g. AWS ALB, NGINX) should ping:
`GET /health`
This endpoint verifies FastAPI availability, PyTorch hardware attachment, and Supabase database connectivity.

## 8. Backup & Rollback
Supabase provides automated daily backups via PITR (Point-In-Time-Recovery). No local backup cronjobs are required for the database layer. Container rollbacks can be executed simply by pinning to previous Docker tags.
