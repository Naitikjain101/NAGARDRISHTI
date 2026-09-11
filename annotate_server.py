#!/usr/bin/env python3
"""
NagarDristi — Multi-Model Annotation Tool (Phase 10)

Supports:
  • Waterlogging  — polygon segmentation (YOLO seg format)
  • Pothole       — bounding box detection  (YOLO detect format)

Run: python3 annotate_server.py
Then open: http://localhost:7777
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

# ── Dataset roots ────────────────────────────────────────────────────────────
DATA_ROOT = Path(__file__).parent / "backend" / "data"

MODELS = {
    "waterlogging": {
        "label": "Waterlogging",
        "icon": "🌊",
        "task": "segment",          # polygon masks
        "class_id": 0,
        "class_name": "waterlogging",
        "color": "#6366f1",
        "dataset": DATA_ROOT / "waterlogging" / "yolo_dataset_v2",
        "raw_dir": DATA_ROOT / "waterlogging" / "raw",
        "splits": ["train", "val"],
    },
    "pothole": {
        "label": "Pothole",
        "icon": "🕳️",
        "task": "detect",           # bounding boxes
        "class_id": 0,
        "class_name": "pothole",
        "color": "#f59e0b",
        "dataset": DATA_ROOT / "pothole" / "yolo_dataset_v2",
        "raw_dir": DATA_ROOT / "pothole" / "raw",
        "splits": ["train", "val"],
    },
}

app = FastAPI(title="NagarDristi Annotation Tool")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Helpers ───────────────────────────────────────────────────────────────────
NEGATIVE_MARKER = "# negative\n"  # Written by user clicking 'No Detection'. Empty file = pending placeholder.


def get_images(model_key: str, split: str) -> list[dict]:
    cfg = MODELS[model_key]
    img_dir = cfg["dataset"] / "images" / split
    lbl_dir = cfg["dataset"] / "labels" / split
    if not img_dir.exists():
        return []
    images = []
    for f in sorted(img_dir.glob("*.jpg")):
        lbl_path = lbl_dir / (f.stem + ".txt")
        if lbl_path.exists():
            content = lbl_path.read_text().strip()
            if content == "# negative":
                status = "negative"   # user explicitly marked — counts as done
            elif content:
                status = "annotated"  # has real YOLO coords — counts as done
            else:
                status = "pending"    # empty placeholder from build script — NOT done
        else:
            status = "pending"
        images.append({
            "filename": f.name,
            "split": split,
            "model": model_key,
            "status": status,
        })
    return images


# ── API ───────────────────────────────────────────────────────────────────────
@app.get("/api/models")
def list_models():
    result = {}
    for k, cfg in MODELS.items():
        all_imgs = []
        for s in cfg["splits"]:
            all_imgs.extend(get_images(k, s))
        done = sum(1 for i in all_imgs if i["status"] in ("annotated", "negative"))
        result[k] = {
            "label": cfg["label"], "icon": cfg["icon"],
            "task": cfg["task"], "color": cfg["color"],
            "total": len(all_imgs), "done": done,
        }
    return result


@app.get("/api/images/{model_key}")
def list_images(model_key: str, split: str = ""):
    if model_key not in MODELS:
        raise HTTPException(404, "Unknown model")
    cfg = MODELS[model_key]
    all_imgs = []
    splits = [split] if split else cfg["splits"]
    for s in splits:
        all_imgs.extend(get_images(model_key, s))
    done = sum(1 for i in all_imgs if i["status"] in ("annotated", "negative"))
    return {"images": all_imgs, "total": len(all_imgs), "done": done}


@app.get("/api/image/{model_key}/{split}/{filename}")
def serve_image(model_key: str, split: str, filename: str):
    if model_key not in MODELS:
        raise HTTPException(404, "Unknown model")
    img_path = MODELS[model_key]["dataset"] / "images" / split / filename
    if not img_path.exists():
        raise HTTPException(404, "Image not found")
    return Response(content=img_path.read_bytes(), media_type="image/jpeg")


@app.get("/api/annotation/{model_key}/{split}/{filename}")
def get_annotation(model_key: str, split: str, filename: str):
    if model_key not in MODELS:
        raise HTTPException(404)
    cfg = MODELS[model_key]
    stem = Path(filename).stem
    lbl_path = cfg["dataset"] / "labels" / split / (stem + ".txt")
    if not lbl_path.exists():
        return {"shapes": [], "status": "pending"}
    content = lbl_path.read_text().strip()
    if not content or content == "# negative":
        return {"shapes": [], "status": "negative" if content == "# negative" else "pending"}

    shapes = []
    if cfg["task"] == "segment":
        for line in content.splitlines():
            if line.startswith("#"):
                continue  # skip comment lines (e.g. # negative marker)
            parts = line.strip().split()
            if len(parts) < 7:
                continue
            pts = [float(x) for x in parts[1:]]
            shapes.append({"type": "polygon", "points": [[pts[i], pts[i+1]] for i in range(0, len(pts)-1, 2)]})
    else:
        for line in content.splitlines():
            if line.startswith("#"):
                continue
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            cx, cy, bw, bh = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            shapes.append({"type": "bbox", "cx": cx, "cy": cy, "w": bw, "h": bh})
    return {"shapes": shapes, "status": "annotated"}


class SaveRequest(BaseModel):
    model_key: str
    split: str
    filename: str
    shapes: list   # polygons or bboxes
    is_negative: bool = False


@app.post("/api/annotation")
def save_annotation(req: SaveRequest):
    if req.model_key not in MODELS:
        raise HTTPException(404)
    cfg = MODELS[req.model_key]
    stem = Path(req.filename).stem
    lbl_dir = cfg["dataset"] / "labels" / req.split
    lbl_dir.mkdir(parents=True, exist_ok=True)
    lbl_path = lbl_dir / (stem + ".txt")

    if req.is_negative or not req.shapes:
        lbl_path.write_text(NEGATIVE_MARKER)  # Explicit marker — distinguishable from empty placeholder
        return {"status": "saved_negative"}

    lines = []
    if cfg["task"] == "segment":
        for shape in req.shapes:
            if shape.get("type") != "polygon" or len(shape.get("points", [])) < 3:
                continue
            coords = " ".join(f"{x:.6f} {y:.6f}" for x, y in shape["points"])
            lines.append(f"0 {coords}")
    else:
        for shape in req.shapes:
            if shape.get("type") != "bbox":
                continue
            lines.append(f"0 {shape['cx']:.6f} {shape['cy']:.6f} {shape['w']:.6f} {shape['h']:.6f}")

    lbl_path.write_text("\n".join(lines) + "\n")
    return {"status": "saved", "count": len(lines)}


class ExtractRequest(BaseModel):
    model_key: str
    video_path: str
    split: str = "train"
    interval: int = 20


@app.post("/api/extract")
def extract_frames(req: ExtractRequest):
    """Extract frames from a video into the dataset."""
    if req.model_key not in MODELS:
        raise HTTPException(404, "Unknown model")
    import cv2
    cfg = MODELS[req.model_key]
    vid = Path(req.video_path)
    if not vid.exists():
        raise HTTPException(404, f"Video not found: {vid}")

    img_dir = cfg["dataset"] / "images" / req.split
    img_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(vid))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    prefix = vid.stem.replace(" ", "_")[:30]
    saved = 0
    fi = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if fi % req.interval == 0:
            out = img_dir / f"{prefix}_f{fi:06d}.jpg"
            if not out.exists():
                cv2.imwrite(str(out), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
                saved += 1
        fi += 1
    cap.release()
    return {"saved": saved, "total_video_frames": total, "split": req.split, "model": req.model_key}


@app.get("/api/raw_videos/{model_key}")
def list_raw_videos(model_key: str):
    if model_key not in MODELS:
        raise HTTPException(404)
    raw_dir = MODELS[model_key]["raw_dir"]
    if not raw_dir.exists():
        return {"videos": []}
    videos = []
    for f in sorted(raw_dir.glob("*.mp4")):
        videos.append({"name": f.name, "path": str(f), "size_mb": f.stat().st_size // (1024*1024)})
    return {"videos": videos}


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE

# ═══════════════════════════════════════════════════════════════════════════════
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NagarDristi — Annotation Studio</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
:root{
  --bg:#080a10;--surface:#0f1219;--surface2:#161b27;--surface3:#1d2235;
  --border:#232840;--accent:#6366f1;--accent2:#22d3ee;--gold:#f59e0b;
  --success:#10b981;--danger:#ef4444;--text:#e2e8f0;--muted:#64748b;
  --sidebar-w:300px;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column;overflow:hidden}

/* ── Header ── */
.header{height:54px;background:var(--surface);border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 18px;gap:14px;flex-shrink:0;z-index:10}
.logo{font-size:15px;font-weight:800;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.header-sep{width:1px;height:22px;background:var(--border)}
.model-tabs{display:flex;gap:6px}
.model-tab{display:flex;align-items:center;gap:6px;padding:6px 14px;border-radius:8px;border:1px solid var(--border);background:transparent;color:var(--muted);font-size:13px;font-weight:500;cursor:pointer;transition:all 0.2s}
.model-tab:hover{background:var(--surface2);color:var(--text)}
.model-tab.active{color:white;border-color:transparent}
.model-tab.wl.active{background:linear-gradient(135deg,#4f46e5,#7c3aed)}
.model-tab.ph.active{background:linear-gradient(135deg,#d97706,#f59e0b)}
.progress-wrap{margin-left:auto;display:flex;align-items:center;gap:10px}
.prog-label{font-size:12px;color:var(--muted)}
.prog-bar{width:160px;height:5px;background:var(--border);border-radius:99px;overflow:hidden}
.prog-fill{height:100%;border-radius:99px;transition:width 0.4s ease}
.prog-fill.wl{background:linear-gradient(90deg,var(--accent),var(--accent2))}
.prog-fill.ph{background:linear-gradient(90deg,#d97706,#fbbf24)}

/* ── Layout ── */
.layout{display:flex;flex:1;overflow:hidden}

/* ── Sidebar ── */
.sidebar{width:var(--sidebar-w);background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden}
.sidebar-top{padding:12px 14px;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:8px}
.sidebar-top h3{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.07em}
.filter-row{display:flex;gap:4px}
.ftab{flex:1;padding:5px 4px;border:1px solid var(--border);border-radius:6px;background:transparent;color:var(--muted);font-size:11px;cursor:pointer;text-align:center;transition:all 0.15s}
.ftab.active{border-color:var(--accent);color:white;background:rgba(99,102,241,.2)}
.split-row{display:flex;gap:4px}
.stab{flex:1;padding:5px 4px;border:1px solid var(--border);border-radius:6px;background:transparent;color:var(--muted);font-size:11px;cursor:pointer;text-align:center;transition:all 0.15s}
.stab.active{border-color:var(--accent2);color:white;background:rgba(34,211,238,.15)}
.video-btn{padding:7px 12px;border-radius:7px;border:1px dashed var(--border);background:transparent;color:var(--muted);font-size:12px;cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:6px;justify-content:center}
.video-btn:hover{border-color:var(--accent);color:var(--accent);background:rgba(99,102,241,.08)}

.img-list{flex:1;overflow-y:auto;padding:6px}
.img-list::-webkit-scrollbar{width:3px}
.img-list::-webkit-scrollbar-thumb{background:var(--border);border-radius:99px}
.img-item{display:flex;align-items:center;gap:8px;padding:7px 8px;border-radius:8px;cursor:pointer;margin-bottom:2px;border:1px solid transparent;transition:all .15s}
.img-item:hover{background:var(--surface2)}
.img-item.active{background:rgba(99,102,241,.12);border-color:rgba(99,102,241,.35)}
.img-thumb{width:46px;height:30px;object-fit:cover;border-radius:4px;background:var(--border);flex-shrink:0}
.img-meta{flex:1;min-width:0}
.img-name{font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--text)}
.img-sub{font-size:10px;color:var(--muted)}
.sdot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
.sdot.pending{background:var(--muted)}
.sdot.annotated{background:var(--success)}
.sdot.negative{background:var(--gold)}

/* ── Main ── */
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.canvas-head{padding:10px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;flex-shrink:0;background:var(--surface)}
.cf-name{font-size:13px;font-weight:500;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.badge{padding:2px 8px;border-radius:99px;font-size:10px;font-weight:600}
.badge.train{background:rgba(99,102,241,.2);color:var(--accent)}
.badge.val{background:rgba(34,211,238,.15);color:var(--accent2)}
.head-btns{display:flex;gap:6px;flex-shrink:0}
.btn{padding:6px 13px;border-radius:7px;border:none;font-size:12px;font-weight:500;cursor:pointer;transition:all .2s;display:flex;align-items:center;gap:5px}
.btn:hover{filter:brightness(1.1);transform:translateY(-1px)}
.btn:disabled{opacity:.35;cursor:not-allowed;transform:none!important}
.btn-ghost{background:var(--surface2);color:var(--text);border:1px solid var(--border)}
.btn-save{background:var(--success);color:#fff}
.btn-neg{background:var(--gold);color:#000}
.btn-danger{background:var(--danger);color:#fff}
.btn-accent{background:var(--accent);color:#fff}

.canvas-wrap{flex:1;display:flex;align-items:center;justify-content:center;background:#04050a;position:relative;overflow:hidden}
#cnv{cursor:crosshair;display:block;max-width:100%;max-height:100%}
.empty{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;height:100%;color:var(--muted);text-align:center}
.empty svg{opacity:.2}
.empty p{font-size:14px}
.empty small{font-size:12px;opacity:.7}

.toolbar{padding:9px 18px;background:var(--surface);border-top:1px solid var(--border);display:flex;align-items:center;gap:10px;flex-shrink:0}
.tbtn{padding:5px 11px;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--muted);font-size:12px;cursor:pointer;transition:all .15s}
.tbtn:hover,.tbtn.active{background:var(--surface2);color:var(--text);border-color:var(--accent)}
.tsep{width:1px;height:20px;background:var(--border)}
.tcount{font-size:12px;font-weight:600;color:var(--accent2);margin-left:2px}
.thint{margin-left:auto;font-size:11px;color:var(--muted)}
.kbd{display:inline-block;padding:1px 5px;border:1px solid var(--border);border-radius:4px;font-size:10px;color:var(--muted)}

/* ── Video extract modal ── */
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:100;align-items:center;justify-content:center}
.modal-bg.open{display:flex}
.modal{background:var(--surface2);border:1px solid var(--border);border-radius:14px;width:520px;padding:28px;display:flex;flex-direction:column;gap:16px}
.modal h2{font-size:16px;font-weight:700}
.modal label{font-size:12px;color:var(--muted);margin-bottom:4px;display:block}
.modal input,.modal select{width:100%;padding:9px 12px;background:var(--surface);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:13px;outline:none}
.modal input:focus,.modal select:focus{border-color:var(--accent)}
.modal-btns{display:flex;gap:8px;justify-content:flex-end}
.vid-list{max-height:160px;overflow-y:auto;border:1px solid var(--border);border-radius:8px;padding:4px}
.vid-item{padding:8px 10px;border-radius:6px;cursor:pointer;font-size:12px;transition:all .15s;display:flex;justify-content:space-between;align-items:center}
.vid-item:hover{background:var(--surface3)}
.vid-item.selected{background:rgba(99,102,241,.15);color:var(--accent)}
.vid-size{color:var(--muted);font-size:11px}

/* ── Toast ── */
.toast{position:fixed;bottom:20px;right:20px;padding:11px 18px;border-radius:10px;font-size:13px;font-weight:500;z-index:9999;transform:translateY(70px);opacity:0;transition:all .3s cubic-bezier(.34,1.56,.64,1)}
.toast.show{transform:translateY(0);opacity:1}
.toast.s{background:var(--success);color:#fff}
.toast.e{background:var(--danger);color:#fff}
.toast.i{background:var(--accent);color:#fff}
</style>
</head>
<body>
<!-- HEADER -->
<div class="header">
  <span class="logo">⚡ NagarDristi</span>
  <div class="header-sep"></div>
  <div class="model-tabs">
    <button class="model-tab wl active" onclick="switchModel('waterlogging')">🌊 Waterlogging</button>
    <button class="model-tab ph" onclick="switchModel('pothole')">🕳️ Pothole</button>
  </div>
  <div class="progress-wrap">
    <span class="prog-label" id="progLabel">0/0 done</span>
    <div class="prog-bar"><div class="prog-fill wl" id="progFill" style="width:0%"></div></div>
    <span class="prog-label" id="progPct">0%</span>
  </div>
</div>

<div class="layout">
  <!-- SIDEBAR -->
  <div class="sidebar">
    <div class="sidebar-top">
      <h3 id="sideTitle">Waterlogging Frames</h3>
      <div class="filter-row">
        <button class="ftab active" onclick="setFilter('all',this)">All</button>
        <button class="ftab" onclick="setFilter('pending',this)">Pending</button>
        <button class="ftab" onclick="setFilter('annotated',this)">Annotated</button>
        <button class="ftab" onclick="setFilter('negative',this)">Negative</button>
      </div>
      <div class="split-row">
        <button class="stab active" onclick="setSplit('all',this)">All</button>
        <button class="stab" onclick="setSplit('train',this)">Train</button>
        <button class="stab" onclick="setSplit('val',this)">Val</button>
      </div>
      <button class="video-btn" onclick="openExtractModal()">＋ Extract frames from video</button>
    </div>
    <div class="img-list" id="imgList"></div>
  </div>

  <!-- MAIN -->
  <div class="main">
    <div class="canvas-head">
      <span class="cf-name" id="cfName">Select an image →</span>
      <span class="badge" id="cfBadge"></span>
      <div class="head-btns">
        <button class="btn btn-ghost" onclick="prevImg()">← Prev</button>
        <button class="btn btn-ghost" onclick="nextImg()">Next →</button>
        <button class="btn btn-neg" onclick="markNegative()" title="N">✗ No Detection</button>
        <button class="btn btn-save" onclick="saveAnnotation()" title="Ctrl+S">✓ Save &amp; Next</button>
      </div>
    </div>

    <div class="canvas-wrap" id="cWrap">
      <div class="empty" id="emptyState">
        <svg width="60" height="60" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
        <p>Pick an image from the sidebar</p>
        <small>Polygon draw for waterlogging · Bounding box for pothole</small>
      </div>
      <canvas id="cnv" style="display:none"></canvas>
    </div>

    <div class="toolbar">
      <button class="tbtn active" id="tbDraw" onclick="setTool('draw')">✏️ Draw</button>
      <button class="tbtn" id="tbSel" onclick="setTool('select')">↖ Select</button>
      <div class="tsep"></div>
      <button class="tbtn" onclick="undoLast()">↩ Undo <span class="kbd">Z</span></button>
      <button class="tbtn" id="tbClose" onclick="closePoly()">⬡ Close <span class="kbd">↵</span></button>
      <button class="tbtn" onclick="clearAll()">🗑 Clear</button>
      <div class="tsep"></div>
      <span class="tcount" id="shapeCount">0 shapes</span>
      <span class="thint" id="toolHint">Click to add points · Enter to close · Z to undo</span>
    </div>
  </div>
</div>

<!-- VIDEO EXTRACT MODAL -->
<div class="modal-bg" id="extractModal">
  <div class="modal">
    <h2>📹 Extract Frames from Video</h2>
    <div>
      <label>Videos in raw/ folder</label>
      <div class="vid-list" id="vidList">Loading...</div>
    </div>
    <div>
      <label>Or enter full video path</label>
      <input type="text" id="vidPath" placeholder="/path/to/video.mp4">
    </div>
    <div style="display:flex;gap:10px">
      <div style="flex:1">
        <label>Target split</label>
        <select id="extractSplit"><option value="train">train</option><option value="val">val</option></select>
      </div>
      <div style="flex:1">
        <label>Frame interval (every Nth frame)</label>
        <input type="number" id="extractInterval" value="20" min="5" max="120">
      </div>
    </div>
    <div class="modal-btns">
      <button class="btn btn-ghost" onclick="closeExtractModal()">Cancel</button>
      <button class="btn btn-accent" onclick="doExtract()">Extract Frames</button>
    </div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
// ═══ State ═══════════════════════════════════════════════════════════════════
let curModel = 'waterlogging';
let curTask  = 'segment';    // 'segment' or 'detect'
let modelColor = '#6366f1';

let allImages = [], filteredImages = [];
let curFilter = 'all', curSplit = 'all';
let curIdx = -1, curImg = null;

let shapes    = [];   // saved shapes
let curPoly   = [];   // in-progress polygon (segment only)
let curBbox   = null; // in-progress bbox drag (detect only) {x0,y0,x1,y1}
let isDragging = false;
let dragStart  = null;
let selectedIdx = -1;
let tool = 'draw';

let img = new Image(), imgLoaded = false;
let cw = 0, ch = 0;  // canvas pixel dims
let mx = 0, my = 0;  // mouse pos on canvas

const cnv = document.getElementById('cnv');
const ctx = cnv.getContext('2d');

// ═══ Init ════════════════════════════════════════════════════════════════════
async function init() {
  await loadModelMeta();
  await refreshImages();
  if (filteredImages.length > 0) selectImage(0);
}

async function loadModelMeta() {
  const data = await fetch('/api/models').then(r=>r.json());
  const m = data[curModel];
  curTask   = m.task;
  modelColor = m.color;
  document.getElementById('sideTitle').textContent = m.label + ' Frames';
  // Update toolbar hint
  document.getElementById('toolHint').textContent = curTask==='segment'
    ? 'Click to place points · Enter/dbl-click to close · Z to undo'
    : 'Click-drag to draw bounding box · Z to undo';
  document.getElementById('tbClose').style.display = curTask==='segment' ? '' : 'none';

  const fill = document.getElementById('progFill');
  fill.className = 'prog-fill ' + (curModel==='waterlogging'?'wl':'ph');

  updateProgress(m.done, m.total);
}

function updateProgress(done, total) {
  const pct = total>0 ? Math.round(done/total*100) : 0;
  document.getElementById('progLabel').textContent = done+'/'+total+' done';
  document.getElementById('progPct').textContent = pct+'%';
  document.getElementById('progFill').style.width = pct+'%';
}

// ═══ Model switch ════════════════════════════════════════════════════════════
async function switchModel(m) {
  curModel = m;
  curIdx = -1; curImg = null;
  shapes=[]; curPoly=[]; curBbox=null;
  imgLoaded = false;
  cnv.style.display = 'none';
  document.getElementById('emptyState').style.display = '';
  document.querySelectorAll('.model-tab').forEach(t=>t.classList.remove('active'));
  event.currentTarget.classList.add('active');
  await loadModelMeta();
  await refreshImages();
  if (filteredImages.length>0) selectImage(0);
}

// ═══ Image list ══════════════════════════════════════════════════════════════
async function refreshImages() {
  const url = curSplit==='all'
    ? `/api/images/${curModel}`
    : `/api/images/${curModel}?split=${curSplit}`;
  const data = await fetch(url).then(r=>r.json());
  allImages = data.images;
  updateProgress(data.done, data.total);
  applyFilter();
}

function applyFilter() {
  if (curFilter==='all') filteredImages = [...allImages];
  else filteredImages = allImages.filter(i=>i.status===curFilter);
  renderList();
}

function setFilter(f, el) {
  curFilter=f;
  document.querySelectorAll('.ftab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  applyFilter();
}

function setSplit(s, el) {
  curSplit=s;
  document.querySelectorAll('.stab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  refreshImages().then(()=>{ if(filteredImages.length>0&&curIdx<0) selectImage(0); });
}

function renderList() {
  const list = document.getElementById('imgList');
  list.innerHTML='';
  filteredImages.forEach((im, i)=>{
    const d = document.createElement('div');
    d.className='img-item'+(i===curIdx?' active':'');
    d.onclick=()=>selectImage(i);
    d.innerHTML=`<img class="img-thumb" src="/api/image/${curModel}/${im.split}/${im.filename}" loading="lazy">
      <div class="img-meta"><div class="img-name">${im.filename.substring(0,30)}</div><div class="img-sub">${im.split}</div></div>
      <div class="sdot ${im.status}"></div>`;
    list.appendChild(d);
  });
}

// ═══ Image selection ═════════════════════════════════════════════════════════
async function selectImage(idx) {
  if (idx<0||idx>=filteredImages.length) return;
  curIdx=idx; curImg=filteredImages[idx];
  shapes=[]; curPoly=[]; curBbox=null; selectedIdx=-1;

  document.getElementById('cfName').textContent = curImg.filename;
  const badge = document.getElementById('cfBadge');
  badge.textContent = curImg.split;
  badge.className = 'badge '+curImg.split;

  // Load existing annotation
  const ann = await fetch(`/api/annotation/${curModel}/${curImg.split}/${curImg.filename}`).then(r=>r.json());
  if (ann.shapes) shapes = ann.shapes.map(s=>({...s, points: s.points ? [...s.points] : undefined}));

  imgLoaded=false;
  img=new Image();
  img.onload=()=>{ imgLoaded=true; setupCanvas(); redraw(); };
  img.src=`/api/image/${curModel}/${curImg.split}/${curImg.filename}`;
  cnv.style.display='block';
  document.getElementById('emptyState').style.display='none';
  renderList();
  updateShapeCount();
}

function setupCanvas() {
  const wrap = document.getElementById('cWrap');
  const maxW = wrap.clientWidth-30, maxH = wrap.clientHeight-30;
  const scale = Math.min(maxW/img.naturalWidth, maxH/img.naturalHeight, 2);
  cw = Math.round(img.naturalWidth*scale);
  ch = Math.round(img.naturalHeight*scale);
  cnv.width=cw; cnv.height=ch;
}

// ═══ Draw ═════════════════════════════════════════════════════════════════════
function redraw() {
  if (!imgLoaded) return;
  ctx.clearRect(0,0,cw,ch);
  ctx.drawImage(img,0,0,cw,ch);

  const color = modelColor;

  // Completed shapes
  shapes.forEach((sh, si)=>{
    if (sh.type==='polygon') {
      const pts = sh.points;
      if (pts.length<2) return;
      ctx.beginPath();
      pts.forEach(([nx,ny],i)=>{ i===0?ctx.moveTo(nx*cw,ny*ch):ctx.lineTo(nx*cw,ny*ch); });
      ctx.closePath();
      ctx.fillStyle = hexAlpha(color, si===selectedIdx?0.4:0.2);
      ctx.fill();
      ctx.strokeStyle = si===selectedIdx ? color : hexAlpha(color,0.85);
      ctx.lineWidth=2; ctx.stroke();
      pts.forEach(([nx,ny])=>{ ctx.beginPath(); ctx.arc(nx*cw,ny*ch,4,0,Math.PI*2); ctx.fillStyle=color; ctx.fill(); });
      if (si===selectedIdx) drawDelHandle(pts,color);
    } else if (sh.type==='bbox') {
      const x=(sh.cx-sh.w/2)*cw, y=(sh.cy-sh.h/2)*ch, w=sh.w*cw, h=sh.h*ch;
      ctx.strokeStyle = si===selectedIdx ? color : hexAlpha(color,0.85);
      ctx.lineWidth=2; ctx.strokeRect(x,y,w,h);
      ctx.fillStyle=hexAlpha(color, si===selectedIdx?0.3:0.15);
      ctx.fillRect(x,y,w,h);
      if (si===selectedIdx) {
        ctx.beginPath(); ctx.arc(x+w+4,y-4,8,0,Math.PI*2);
        ctx.fillStyle='#ef4444'; ctx.fill();
        ctx.fillStyle='#fff'; ctx.font='bold 11px Inter'; ctx.textAlign='center'; ctx.textBaseline='middle';
        ctx.fillText('×',x+w+4,y-4);
      }
    }
  });

  // In-progress polygon
  if (curTask==='segment' && curPoly.length>0) {
    ctx.beginPath();
    curPoly.forEach(([nx,ny],i)=>{ i===0?ctx.moveTo(nx*cw,ny*ch):ctx.lineTo(nx*cw,ny*ch); });
    ctx.lineTo(mx,my);
    ctx.strokeStyle='#22d3ee'; ctx.lineWidth=1.5; ctx.setLineDash([5,4]); ctx.stroke(); ctx.setLineDash([]);
    curPoly.forEach(([nx,ny])=>{ ctx.beginPath(); ctx.arc(nx*cw,ny*ch,4,0,Math.PI*2); ctx.fillStyle='#22d3ee'; ctx.fill(); });
    if (curPoly.length>2) {
      const [fx,fy]=curPoly[0];
      if (Math.hypot(mx-fx*cw,my-fy*ch)<18) {
        ctx.beginPath(); ctx.arc(fx*cw,fy*ch,9,0,Math.PI*2);
        ctx.strokeStyle='#22d3ee'; ctx.lineWidth=2; ctx.stroke();
      }
    }
  }

  // In-progress bbox
  if (curTask==='detect' && isDragging && curBbox) {
    const {x0,y0,x1,y1}=curBbox;
    const bx=Math.min(x0,x1),by=Math.min(y0,y1),bw=Math.abs(x1-x0),bh=Math.abs(y1-y0);
    ctx.strokeStyle=color; ctx.lineWidth=2; ctx.setLineDash([5,4]); ctx.strokeRect(bx,by,bw,bh);
    ctx.fillStyle=hexAlpha(color,0.15); ctx.fillRect(bx,by,bw,bh); ctx.setLineDash([]);
  }
}

function drawDelHandle(pts, color) {
  const xs=pts.map(p=>p[0]*cw), ys=pts.map(p=>p[1]*ch);
  const dx=Math.max(...xs)+4, dy=Math.min(...ys)-4;
  ctx.beginPath(); ctx.arc(dx,dy,8,0,Math.PI*2); ctx.fillStyle='#ef4444'; ctx.fill();
  ctx.fillStyle='#fff'; ctx.font='bold 11px Inter'; ctx.textAlign='center'; ctx.textBaseline='middle';
  ctx.fillText('×',dx,dy);
}

function hexAlpha(hex, a) {
  const r=parseInt(hex.slice(1,3),16),g=parseInt(hex.slice(3,5),16),b=parseInt(hex.slice(5,7),16);
  return `rgba(${r},${g},${b},${a})`;
}

// ═══ Canvas events ═══════════════════════════════════════════════════════════
cnv.addEventListener('mousemove', e=>{
  const r=cnv.getBoundingClientRect(); mx=e.clientX-r.left; my=e.clientY-r.top;
  if (curTask==='segment' && curPoly.length>0) redraw();
  if (curTask==='detect' && isDragging) { curBbox.x1=mx; curBbox.y1=my; redraw(); }
});

cnv.addEventListener('mousedown', e=>{
  if (!imgLoaded) return;
  const r=cnv.getBoundingClientRect(); const x=e.clientX-r.left, y=e.clientY-r.top;
  if (curTask==='detect' && tool==='draw') {
    isDragging=true; curBbox={x0:x,y0:y,x1:x,y1:y};
  }
});

cnv.addEventListener('mouseup', e=>{
  if (!imgLoaded) return;
  const r=cnv.getBoundingClientRect(); const x=e.clientX-r.left, y=e.clientY-r.top;

  if (curTask==='detect' && isDragging) {
    isDragging=false;
    if (curBbox && Math.abs(curBbox.x1-curBbox.x0)>6 && Math.abs(curBbox.y1-curBbox.y0)>6) {
      const bx=Math.min(curBbox.x0,curBbox.x1), by=Math.min(curBbox.y0,curBbox.y1);
      const bw=Math.abs(curBbox.x1-curBbox.x0), bh=Math.abs(curBbox.y1-curBbox.y0);
      const cx=(bx+bw/2)/cw, cy=(by+bh/2)/ch, nw=bw/cw, nh=bh/ch;
      shapes.push({type:'bbox', cx, cy, w:nw, h:nh});
      updateShapeCount();
    }
    curBbox=null; redraw(); return;
  }
});

cnv.addEventListener('click', e=>{
  if (!imgLoaded || curTask==='detect') return;
  const r=cnv.getBoundingClientRect(); const x=e.clientX-r.left, y=e.clientY-r.top;
  const nx=x/cw, ny=y/ch;

  if (tool==='select') {
    if (selectedIdx>=0) {
      const sh=shapes[selectedIdx];
      if (sh.type==='polygon') {
        const xs=sh.points.map(p=>p[0]*cw), ys=sh.points.map(p=>p[1]*ch);
        const dx=Math.max(...xs)+4, dy=Math.min(...ys)-4;
        if (Math.hypot(x-dx,y-dy)<10) { shapes.splice(selectedIdx,1); selectedIdx=-1; updateShapeCount(); redraw(); return; }
      } else {
        const sx=(sh.cx-sh.w/2)*cw, sy=(sh.cy-sh.h/2)*ch, sw=sh.w*cw;
        if (Math.hypot(x-(sx+sw+4), y-(sy-4))<10) { shapes.splice(selectedIdx,1); selectedIdx=-1; updateShapeCount(); redraw(); return; }
      }
    }
    selectedIdx=-1;
    for (let i=shapes.length-1;i>=0;i--) {
      const sh=shapes[i];
      if (sh.type==='polygon' && ptInPoly(nx,ny,sh.points)) { selectedIdx=i; break; }
      if (sh.type==='bbox') {
        if (nx>=sh.cx-sh.w/2&&nx<=sh.cx+sh.w/2&&ny>=sh.cy-sh.h/2&&ny<=sh.cy+sh.h/2) { selectedIdx=i; break; }
      }
    }
    redraw(); return;
  }

  if (tool==='draw' && curTask==='segment') {
    if (curPoly.length>2) {
      const [fx,fy]=curPoly[0];
      if (Math.hypot(x-fx*cw,y-fy*ch)<18) { closePoly(); return; }
    }
    curPoly.push([nx,ny]); redraw();
  }
});

cnv.addEventListener('dblclick', ()=>{ if (curTask==='segment' && curPoly.length>2) closePoly(); });

function ptInPoly(px,py,poly){
  let inside=false;
  for(let i=0,j=poly.length-1;i<poly.length;j=i++){
    const [xi,yi]=poly[i],[xj,yj]=poly[j];
    if(((yi>py)!==(yj>py))&&(px<(xj-xi)*(py-yi)/(yj-yi)+xi)) inside=!inside;
  }
  return inside;
}

// ═══ Tools ═══════════════════════════════════════════════════════════════════
function setTool(t){
  tool=t;
  if(t!=='draw') curPoly=[];
  document.getElementById('tbDraw').classList.toggle('active',t==='draw');
  document.getElementById('tbSel').classList.toggle('active',t==='select');
  redraw();
}

function closePoly(){
  if(curPoly.length<3){ toast('Need at least 3 points','e'); return; }
  shapes.push({type:'polygon',points:[...curPoly]});
  curPoly=[]; updateShapeCount(); redraw();
}

function undoLast(){
  if(curPoly.length>0){ curPoly.pop(); redraw(); }
  else if(shapes.length>0){ shapes.pop(); updateShapeCount(); redraw(); }
}

function clearAll(){ shapes=[]; curPoly=[]; curBbox=null; selectedIdx=-1; isDragging=false; updateShapeCount(); redraw(); }

function updateShapeCount(){
  const n=shapes.length;
  const word = curTask==='segment'?'polygon':'bbox';
  document.getElementById('shapeCount').textContent = n+' '+word+(n!==1?'s':'');
}

// ═══ Save ════════════════════════════════════════════════════════════════════
async function saveAnnotation(){
  if (!curImg) return;
  if (curTask==='segment' && curPoly.length>2) closePoly();
  const body={model_key:curModel,split:curImg.split,filename:curImg.filename,shapes,is_negative:false};
  const res=await fetch('/api/annotation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await res.json();
  toast('Saved '+data.count+' shape(s)!','s');
  await refreshImages(); nextImg();
}

async function markNegative(){
  if (!curImg) return;
  shapes=[]; curPoly=[];
  const body={model_key:curModel,split:curImg.split,filename:curImg.filename,shapes:[],is_negative:true};
  await fetch('/api/annotation',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  toast('Marked as negative','i');
  await refreshImages(); nextImg();
}

function prevImg(){ if(curIdx>0) selectImage(curIdx-1); }
function nextImg(){ if(curIdx<filteredImages.length-1) selectImage(curIdx+1); }

// ═══ Video extract modal ══════════════════════════════════════════════════════
let selectedVidPath = null;

async function openExtractModal(){
  document.getElementById('extractModal').classList.add('open');
  const data=await fetch(`/api/raw_videos/${curModel}`).then(r=>r.json());
  const list=document.getElementById('vidList');
  if (!data.videos.length){ list.innerHTML='<div style="padding:12px;color:var(--muted);font-size:12px">No videos in raw/ folder yet. Enter path below.</div>'; return; }
  list.innerHTML='';
  data.videos.forEach(v=>{
    const d=document.createElement('div');
    d.className='vid-item';
    d.onclick=()=>{ selectedVidPath=v.path; document.getElementById('vidPath').value=v.path; document.querySelectorAll('.vid-item').forEach(x=>x.classList.remove('selected')); d.classList.add('selected'); };
    d.innerHTML=`<span>${v.name}</span><span class="vid-size">${v.size_mb}MB</span>`;
    list.appendChild(d);
  });
}

function closeExtractModal(){ document.getElementById('extractModal').classList.remove('open'); }

async function doExtract(){
  const path = document.getElementById('vidPath').value.trim();
  const split = document.getElementById('extractSplit').value;
  const interval = parseInt(document.getElementById('extractInterval').value)||20;
  if (!path){ toast('Enter a video path','e'); return; }
  toast('Extracting frames…','i');
  closeExtractModal();
  const res=await fetch('/api/extract',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model_key:curModel,video_path:path,split,interval})});
  const data=await res.json();
  toast(`✓ Extracted ${data.saved} frames into ${split}!`,'s');
  await refreshImages();
}

// ═══ Keyboard ════════════════════════════════════════════════════════════════
document.addEventListener('keydown', e=>{
  if(e.target.tagName==='INPUT'||e.target.tagName==='SELECT') return;
  if(e.key==='z'||e.key==='Z') undoLast();
  if(e.key==='Enter'){ if(curTask==='segment') closePoly(); }
  if(e.key==='ArrowRight') nextImg();
  if(e.key==='ArrowLeft') prevImg();
  if(e.key==='Escape'){ curPoly=[]; curBbox=null; isDragging=false; selectedIdx=-1; redraw(); }
  if(e.key==='n'||e.key==='N') markNegative();
  if((e.metaKey||e.ctrlKey)&&e.key==='s'){ e.preventDefault(); saveAnnotation(); }
});

// ═══ Toast ═══════════════════════════════════════════════════════════════════
function toast(msg,type='i'){
  const t=document.getElementById('toast');
  t.textContent=msg; t.className='toast '+type+' show';
  setTimeout(()=>t.classList.remove('show'),2500);
}

window.addEventListener('resize',()=>{ if(imgLoaded){ setupCanvas(); redraw(); } });
init();
</script>
</body>
</html>"""

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*65)
    print("  ⚡ NagarDristi — Multi-Model Annotation Studio")
    print("="*65)
    for k, cfg in MODELS.items():
        rd = cfg["raw_dir"]
        ds = cfg["dataset"]
        total = sum(len(list((ds/"images"/s).glob("*.jpg"))) for s in cfg["splits"] if (ds/"images"/s).exists())
        raw   = len(list(rd.glob("*.mp4"))) if rd.exists() else 0
        print(f"  {cfg['icon']} {cfg['label']:15} frames={total:4d}  raw_videos={raw}")

    print()
    print("  Opening: http://localhost:7777")
    print("="*65 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=7777, log_level="warning")
