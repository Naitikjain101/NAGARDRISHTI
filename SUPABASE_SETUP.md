# Supabase Setup Guide for Urban Watch

Follow these exact steps to configure your Urban Watch instance to connect to Supabase.

## 1. Create Supabase Project
1. Go to [database.new](https://database.new) or your Supabase Dashboard.
2. Create a new organization and project.
3. Note your database region and create a strong database password.

## 2. Configure the Database Schema
1. Open the Supabase dashboard for your new project.
2. Navigate to the **SQL Editor** on the left sidebar.
3. Click **New Query**.
4. Open `supabase/schema.sql` from this repository, copy its contents, and paste it into the SQL Editor.
5. Click **Run**. This script will:
   - Enable the `postgis` extension.
   - Create all tables (`videos`, `incidents`, `vehicles`, `traffic_windows`, `road_segments`, `ai_models`).
   - Create spatial indexes for GIS.
   - Enable Row Level Security (RLS) policies.

## 3. Obtain Credentials
1. In the Supabase Dashboard, navigate to **Project Settings** (gear icon) > **API**.
2. Locate the **Project URL** (e.g., `https://xxxxxxxxxxxxxx.supabase.co`).
3. Locate the **`service_role` secret**. 
   > **WARNING**: Never share the `service_role` secret. It bypasses all Row Level Security.

## 4. Configure Environment Variables
1. In the root of the `Nagardristi2.0` repository, copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your credentials:
   ```ini
   SUPABASE_URL=https://your-project-id.supabase.co
   SUPABASE_SERVICE_ROLE_KEY=your-super-secret-service-role-key
   ```

## 5. Verify the Connection
1. Ensure your dependencies are installed (`pip install -r backend/requirements.txt`).
2. Start the FastAPI backend:
   ```bash
   cd backend
   uvicorn main:app --reload
   ```
3. Check the System Status API by navigating to `http://127.0.0.1:8000/api/system/status`. You should see `"status": "ok"` and non-zero counts if data exists.

## 6. Start the Command Center
Once the backend is connected to Supabase, start the React frontend:
```bash
cd frontend-react
npm run dev
```
Navigate to `http://localhost:5173` to view the Urban Watch Command Center.
