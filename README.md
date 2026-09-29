<div align="center">

<img src="docs/banner.jpg" alt="NagarDrishti Banner" width="100%" />

# 🏙️ NagarDrishti

### *AI-Powered Mobile Urban Intelligence Platform Using Public Transport Fleet*

[![SIH 2024](https://img.shields.io/badge/SIH-Problem_Statement_26124-orange?style=for-the-badge&logo=hackthebox)](https://www.sih.gov.in/)
[![Smart Automation](https://img.shields.io/badge/Category-Smart_Automation-blue?style=for-the-badge&logo=robot)]()
[![Team](https://img.shields.io/badge/Team-HackDynasty-cyan?style=for-the-badge&logo=teamspeak)]()

[![React](https://img.shields.io/badge/React_19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript_6-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?style=flat-square&logo=pytorch&logoColor=white)](https://pytorch.org/)
[![YOLO](https://img.shields.io/badge/YOLOv8%2F11-00FFFF?style=flat-square&logo=yolo&logoColor=black)](https://docs.ultralytics.com/)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com/)

**"Every Bus. Every Road. One Intelligent City."**

[🚀 Live Demo](https://nagardrishti-nine.vercel.app) · [📖 Documentation](#-architecture)

</div>

---

## 📋 Table of Contents

- [Problem Statement](#-problem-statement)
- [The Gap in Existing Solutions](#-the-gap-in-existing-solutions)
- [Our Solution — NagarDrishti](#-our-solution--nagardrishti)
- [Six Intelligence Layers](#-six-intelligence-layers)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Platform Features (Command Center)](#-platform-features-command-center)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Deployment](#-deployment)
- [Feasibility & Business Model](#-feasibility--business-model)
- [Impact & Benefits](#-impact--benefits)
- [Comparison with Existing Solutions](#-comparison-with-existing-solutions)
- [Research & References](#-research--references)
- [Team](#-team)

---

## 🔴 Problem Statement

> **SIH Problem Statement 26124** — *AI-Powered Mobile Urban Intelligence Platform Using Public Transport Fleet* (Smart Automation)

Today, Indian cities already have **CCTV cameras, public buses, GPS systems, and traffic infrastructure**. But most of these systems work **independently** — they tell us what's happening at a particular location, but they don't continuously understand the city.

### The Real Challenges

- 🛣️ **Road Inspection**: Still largely **manual and periodic**. PWD teams can only cover limited roads per day.
- 📹 **Fixed CCTV**: Creates **coverage gaps** — cameras only see where they are installed.
- 📱 **Citizen Complaints**: **Reactive**, not proactive. Issues are reported only after they cause problems.
- 🗺️ **Incident Data**: **Scattered** across departments with no unified intelligence layer.
- 🚗 **Hit-and-Run Cases**: Identifying and tracking vehicles across the city is extremely difficult.
- 🌊 **Waterlogging**: Detected only after roads are flooded, causing traffic disruption.
- 🚦 **Traffic Congestion**: Understood through isolated sensors, not city-wide pattern analysis.

> **The problem is not the lack of data. The problem is converting continuous urban data into actionable intelligence.**

---

## ❌ The Gap in Existing Solutions

| Approach | Limitation |
|----------|-----------|
| **Manual Road Inspection** | Resource-intensive, periodic (quarterly at best), subjective assessment |
| **Fixed CCTV Networks** | Location-bound, expensive to scale, no AI-driven analysis |
| **Individual AI Tools** | Detect specific objects (e.g., potholes) but lack a unified city-wide intelligence layer |
| **Citizen Reporting Apps** | Reactive, inconsistent quality, no automated verification |

**No existing solution treats the city's entire bus fleet as a continuous, mobile AI sensing network.**

---

## ✅ Our Solution — NagarDrishti

<div align="center">

> *Instead of building another expensive camera network, we turn existing public transport buses into mobile AI sensing units.*

</div>

**NagarDrishti** (नगरदृष्टि — "City Vision") is an end-to-end AI-powered platform that converts video feeds from **existing public transport buses** into **geospatial urban intelligence**. Every bus becomes a continuously moving sensor for the city.

### Key Innovation

```mermaid
graph LR
    A[🚌 Existing Bus Fleet] --> B[📹 Onboard Cameras]
    B --> C[🤖 Edge AI Processing]
    C --> D[🗺️ GIS Intelligence]
    D --> E[📊 Command Center]
```

- **Zero new infrastructure** — we use cameras on buses that already traverse every road in the city.
- **Continuous coverage** — buses operate 18+ hours/day, covering hundreds of routes.
- **Multi-modal intelligence** — potholes, waterlogging, traffic, safety, and incidents from a single video stream.
- **Edge-first architecture** — we transmit intelligence and evidence, not raw video.

---

## 🧠 Six Intelligence Layers

NagarDrishti covers the **complete problem statement** through six interconnected intelligence layers:

### 1. 🛣️ Road Intelligence
> Potholes, damaged roads, and waterlogging detection
- **YOLO-based pothole detection** with custom-trained models.
- **YOLOv8-Segmentation** for area-based waterlogging detection.
- Temporal validation to filter false positives.

### 2. 🏗️ Infrastructure Intelligence
> Missing dividers, zebra crossings, and damaged signs
- Object detection for urban infrastructure elements.
- Gap analysis by comparing expected vs. observed infrastructure.

### 3. 🚗 Traffic Intelligence
> Vehicle detection, classification, counting, and density
- **YOLO vehicle detection** with 80+ class support.
- **ByteTrack multi-object tracking** for maintaining vehicle identities.
- Real-time density estimation and congestion scoring.

### 4. 🚶 Safety Intelligence
> Vulnerable pedestrian and school-zone risk detection
- Pedestrian detection in high-risk zones.
- Helmet compliance detection for two-wheelers.

### 5. 🚨 Incident Intelligence
> Rash driving and hit-and-run tracking with evidence
- Vehicle tracking with unique ID persistence.
- GPS-timestamped evidence collection.
- Incident deduplication across multiple observations.

### 6. 📊 Mobility Intelligence
> Fleet-wide congestion heatmaps and route-delay analysis
- City-wide congestion heatmaps.
- Historical pattern analysis for urban planning.

---

## 🏗 Architecture

<div align="center">
<img src="docs/architecture.jpg" alt="NagarDrishti Architecture" width="100%" />
</div>

### Data Flow

1. **Capture & Ingest** — Bus cameras provide video; GPS provides location.
2. **Edge AI Detection** — YOLO performs object detection, ByteTrack maintains identities.
3. **Validation & Intelligence** — Temporal validation, geometric checks, and deduplication.
4. **GIS & Incident Creation** — Geospatial records with evidence, confidence, and status.
5. **Command Centre** — Central platform visualizes incidents on interactive GIS maps.

---

## 🛠 Tech Stack

**AI & Computer Vision:**
- [Ultralytics YOLO v8/v11](https://docs.ultralytics.com/) — Object detection & Segmentation.
- [ByteTrack](https://github.com/ifzhang/ByteTrack) — Multi-object tracking.
- [OpenCV](https://opencv.org/) & [PyTorch](https://pytorch.org/) — Processing & Deep Learning.

**Backend:**
- [FastAPI](https://fastapi.tiangolo.com/) — Async Python API.
- [Supabase (PostgreSQL)](https://supabase.com/) — Database, Storage, and Auth.
- [PostGIS](https://postgis.net/) — Geospatial queries.

**Frontend:**
- [React 19](https://react.dev/) & [TypeScript](https://www.typescriptlang.org/) — UI Framework.
- [Tailwind CSS](https://tailwindcss.com/) & [Lucide](https://lucide.dev/) — Styling and Icons.
- [Leaflet](https://leafletjs.com/) — Interactive GIS mapping.
- [Vite](https://vite.dev/) — Build tool.

---

## 🖥 Platform Features (Command Center)

NagarDrishti features a comprehensive dashboard with **14 pages**:

- 🏠 **Command Center**: Central dashboard with live city-wide map.
- 📹 **Live Monitoring**: Real-time video playback synced with GIS map.
- 🎬 **Video Analysis**: Process videos and review detection overlays.
- 🗺️ **Fleet Replay**: Multi-bus synchronized replay.
- 🛣️ **Road Intelligence**: Pothole and waterlogging heatmaps.
- 🚗 **Traffic Intelligence**: Real-time traffic density and classification.
- 🚨 **Incidents**: Full incident management workflow.
- 🔧 **Maintenance**: Task lifecycle linked to incidents.
- 🧪 **Pothole Lab**: Model benchmarking and retraining workflow.

---

## 📁 Project Structure

```text
NagarDrishti/
├── 🔧 backend/                          # FastAPI Backend
│   ├── ai/                              # AI Detection Engine (YOLO, ByteTrack, etc.)
│   ├── api/                             # REST API Routes
│   ├── db/                              # Database schema and Supabase client
│   ├── main.py                          # FastAPI application entry point
│   └── requirements.txt                 # Backend dependencies
│
├── 🎨 frontend-react/                   # React Frontend
│   ├── src/                             # Source code (components, pages, api, hooks)
│   ├── package.json                     # Frontend dependencies & scripts
│   ├── tailwind.config.js               # Tailwind CSS configuration
│   └── vite.config.ts                   # Vite bundler configuration
│
├── 🤗 huggingface_space/                # HuggingFace deployment code
│   └── app.py
│
├── 📄 docs/                             # Documentation assets (images)
├── 🐳 docker-compose.yml               # Multi-container deployment config
├── 📋 .env.example                      # Environment variables template
└── 📝 README.md                         # This file
```

---

## 🚀 Getting Started

### Prerequisites
- **Python** ≥ 3.10
- **Node.js** ≥ 18
- **Supabase** project (free tier works)

### 1. Clone & Configure
```bash
git clone https://github.com/Naitikjain101/Nagardrishti-pvt.git
cd Nagardrishti-pvt
cp .env.example .env
```
*Edit `.env` with your Supabase credentials and URLs.*

### 2. Database Setup
Run `backend/db/schema.sql` in your Supabase SQL Editor to set up tables, RLS policies, and PostGIS.

### 3. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Frontend Setup
```bash
cd frontend-react
npm install
npm run dev
```
The frontend runs at `http://localhost:5173`.

---

## 🌐 Deployment

We use a modern cloud stack for deployment:

- **Frontend**: [Vercel](https://nagardrishti-nine.vercel.app)
- **Backend**: Render
- **Database & Storage**: Supabase
- **ML Models**: Hugging Face Spaces

*For self-hosting, use the included Docker Compose setup:*
```bash
docker-compose up -d --build
```

---

## 💼 Feasibility & Business Model

### Deployment Strategy
1. **Phase 1: Pilot (1-5 buses)** — Validate AI accuracy.
2. **Phase 2: Expansion (10-50)** — Cover major corridors.
3. **Phase 3: City-Wide (100+)** — Full urban intelligence coverage.

### Revenue Streams (B2G)
- Municipal SaaS Licensing
- Managed Analytics & Reporting
- Deployment & System Integration Services

**Target Customers:** Municipal Corporations, Transport Departments, Traffic Police, PWD, NHAI.

---

## 📈 Impact & Benefits

| Benefit | Impact |
|---------|--------|
| 🔍 **Earlier Detection** | Potholes and waterlogging detected within hours instead of weeks |
| 🗺️ **Continuous Coverage** | Mobile sensing eliminates fixed-camera coverage gaps |
| 🚦 **Traffic Intelligence** | Identify congestion patterns and bottlenecks across the city |
| 🚨 **Faster Response** | Automated incident creation with GPS location and evidence |
| 💰 **Cost Efficiency** | 10-50x cheaper than deploying a dedicated camera network |

> A **bus** is not just public transport — it's a **continuously moving urban sensor**.

---

## 📊 Comparison with Existing Solutions

| Feature | Manual Inspection | Fixed CCTV | Individual AI Tools | **NagarDrishti** |
|---------|:-:|:-:|:-:|:-:|
| **Pothole Detection** | Periodic | Not designed for | Single model only | **Continuous + validated** |
| **Waterlogging** | Reactive only | Limited view | No temporal validation | **Segmentation + severity** |
| **Vehicle Tracking** | Not possible | Single camera | No cross-camera | **ByteTrack + fleet-wide** |
| **City-Wide Coverage** | Very limited | Location-bound | Not applicable | **Every route, every day** |
| **Cost Efficiency** | High labour cost | Very expensive | Per-model licensing | **Reuses existing infra** |

---

## 📚 Research & References

- [**YOLOv8 - Ultralytics**](https://github.com/ultralytics/ultralytics) (Jocher et al., 2023)
- [**ByteTrack: Multi-Object Tracking**](https://arxiv.org/abs/2110.06864) (Zhang et al., ECCV 2022)
- [**RDD2022: Road Damage Detection Dataset**](https://github.com/sekilab/RoadDamageDetector/) (Arya et al., 2022)

---

## 👥 Team

<div align="center">

### 🏆 Team HackDynasty
*Smart India Hackathon 2024 — Problem Statement 26124*

<br/>
<br/>

🌆 *"When thousands of buses move through a city every day, they are no longer just transporting people. They are continuously sensing the city."*

Made with ❤️ by **Team HackDynasty** 🇮🇳

</div>
