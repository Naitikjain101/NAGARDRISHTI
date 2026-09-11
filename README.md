# Urban Watch — Phase 1

Urban Watch is an AI-powered urban surveillance and traffic analytics system.

## Phase 1: AI Detection Foundation

This phase establishes the core detection/tracking infrastructure:
- Multi-class object detection using pretrained YOLO models
- ByteTrack multi-object tracking
- Unique vehicle counting via track IDs
- Rolling-window traffic density calculation
- Timestamped JSON detection output

## Environment

Tested on:
- macOS with Apple Silicon (MPS)
- Python 3.9+
- PyTorch 2.8.0
- Ultralytics 8.4.41

## Setup

```bash
# Install dependencies
pip3 install -r requirements.txt

# Start backend
cd backend
uvicorn main:app --reload --port 8000

# Run tests
cd backend
python -m pytest tests/ -v
```

## Model Benchmarking

```bash
cd backend
python -m ai.benchmarking.benchmark_models
```

**NOTE:** Benchmarking requires test videos placed at:
- `backend/video/test_data/traffic_test.mp4`
- `backend/video/test_data/road_test.mp4`

Without test videos, benchmarking reports: `BENCHMARK NOT RUN — TEST VIDEO MISSING`

## Usage

1. Open `http://localhost:8000` in browser
2. Upload a traffic video
3. Click "Process with AI"
4. Video plays immediately (HTML5)
5. AI overlay appears after processing

## Project Structure

See `PROJECT_ARCHITECTURE.md` for full details.

## Model Policy

See `MODEL_POLICY.md` for model selection rules.

## Phase 1 Report

See `PHASE_1_REPORT.md` for benchmark results and model selection evidence.
