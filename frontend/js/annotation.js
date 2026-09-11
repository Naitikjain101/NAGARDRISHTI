const API_BASE = 'http://localhost:8000/api/waterlogging/annotations';
const DATASET_BASE = 'http://localhost:8000/dataset';

// State
let frames = [];
let currentFrameIndex = -1;
let currentImageData = null; // Contains status, annotations list
let imageObj = new Image();

// History for Undo/Redo
let history = [];
let historyIndex = -1;

// Canvas state
let canvas, ctx;
let cw, ch;
let scale = 1;
let offsetX = 0;
let offsetY = 0;
let isPanning = false;
let panStart = { x: 0, y: 0 };
let currentPolygon = []; // Array of [x, y] normalized

// State Machine
let editorState = 'IDLE'; // 'IDLE', 'DRAWING', 'EDITING'
let selectedPolyIdx = -1; // -1 means none selected
let hoveredVertex = null; // { polyIdx, vIdx }
let draggingVertex = null; // { polyIdx, vIdx }

document.addEventListener("DOMContentLoaded", () => {
    canvas = document.getElementById("annotationCanvas");
    ctx = canvas.getContext("2d");
    
    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();
    
    initEvents();
    loadFrames();
});

function resizeCanvas() {
    const wrapper = document.getElementById("canvasWrapper");
    cw = wrapper.clientWidth;
    ch = wrapper.clientHeight;
    canvas.width = cw;
    canvas.height = ch;
    render();
}

function initEvents() {
    // Toolbar
    document.getElementById("btnPrev").addEventListener("click", () => navigate(-1));
    document.getElementById("btnNext").addEventListener("click", () => navigate(1));
    document.getElementById("btnUndo").addEventListener("click", undo);
    document.getElementById("btnRedo").addEventListener("click", redo);
    document.getElementById("btnDeletePoly").addEventListener("click", deleteSelectedPolygon);
    document.getElementById("btnSave").addEventListener("click", saveAnnotation);
    document.getElementById("btnExport").addEventListener("click", exportYOLO);
    
    document.querySelectorAll(".btn-status").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const status = e.target.getAttribute("data-status");
            setStatus(status);
        });
    });

    document.getElementById("filterFrames").addEventListener("input", (e) => {
        const val = e.target.value.toLowerCase();
        document.querySelectorAll(".frame-item").forEach(el => {
            const txt = el.innerText.toLowerCase();
            el.style.display = txt.includes(val) ? "flex" : "none";
        });
    });

    // Canvas Mouse Events
    canvas.addEventListener("mousedown", onMouseDown);
    canvas.addEventListener("mousemove", onMouseMove);
    canvas.addEventListener("mouseup", onMouseUp);
    canvas.addEventListener("wheel", onWheel);
    canvas.addEventListener("contextmenu", e => e.preventDefault());
    
    // Keyboard
    window.addEventListener("keydown", (e) => {
        if (e.target.tagName === "INPUT") return;
        
        const key = e.key.toLowerCase();
        if (key === 'a') setStatus('ANNOTATED');
        if (key === 'n') setStatus('NO_WATERLOGGING');
        if (key === 'd') setStatus('DIFFICULT');
        if (key === 'x') setStatus('SKIPPED');
        if (key === 's') saveAnnotation();
        if (e.key === 'ArrowLeft') navigate(-1);
        if (e.key === 'ArrowRight') navigate(1);
        if (key === 'delete' || key === 'backspace') deleteSelectedPolygon();
        if (e.key === '0') fitImage();
        
        if (key === 'z' && (e.ctrlKey || e.metaKey)) {
            if (e.shiftKey) redo();
            else undo();
            e.preventDefault();
        }
    });
}

// --- API ---

async function loadFrames() {
    try {
        const res = await fetch(`${API_BASE}/frames`);
        const data = await res.json();
        frames = data.frames || [];
        renderFrameList();
        updateStats();
    } catch (e) {
        console.error("Failed to load frames", e);
    }
}

async function loadFrame(index) {
    if (index < 0 || index >= frames.length) return;
    
    // Save current before switching
    if (currentFrameIndex !== -1 && currentImageData) {
        saveAnnotation(true);
    }
    
    currentFrameIndex = index;
    const frame = frames[index];
    
    // UI Update
    document.querySelectorAll('.frame-item').forEach(el => el.classList.remove('active'));
    const el = document.getElementById(`frame-${index}`);
    if (el) {
        el.classList.add('active');
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    document.getElementById("lblFrameInfo").innerText = `${frame.image_path} (${index + 1}/${frames.length})`;
    
    // Fetch data
    try {
        const res = await fetch(`${API_BASE}/${frame.image_path}?t=${Date.now()}`);
        if (!res.ok) throw new Error("Not found");
        currentImageData = await res.json();
        // Ensure status property exists for frontend state machine
        if (!currentImageData.status) {
            currentImageData.status = currentImageData.annotation_status || 'PENDING';
        }
    } catch (e) {
        // Mock if not exists
        currentImageData = {
            image: frame.image_path,
            image_width: 854,
            image_height: 480,
            status: frame.annotation_status || 'PENDING',
            annotations: []
        };
    }
    
    // Init state
    currentPolygon = [];
    clearHistory();
    saveHistoryState();
    updateStatusButtons();
    
    // Load image
    imageObj.onload = () => {
        fitImage();
    };
    imageObj.src = `${DATASET_BASE}/${frame.image_path}`;
}

async function saveAnnotation(silent = false) {
    if (!currentImageData || currentFrameIndex === -1) return;
    const frame = frames[currentFrameIndex];
    
    try {
        const res = await fetch(`${API_BASE}/${frame.image_path}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(currentImageData)
        });
        
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(`HTTP ${res.status} — ${errText}`);
        }
        
        // Update local manifest cache
        const finalStatus = currentImageData.status || 'PENDING';
        frame.annotation_status = finalStatus;
        const badge = document.querySelector(`#frame-${currentFrameIndex} .badge`);
        if (badge) {
            badge.className = `badge ${finalStatus.toLowerCase().replace('_', '')}`;
            badge.innerText = finalStatus;
        }
        updateStats();
        
        if (!silent) {
            const btn = document.getElementById("btnSave");
            const old = btn.innerText;
            btn.innerText = "Saved!";
            setTimeout(() => btn.innerText = old, 1000);
        }
    } catch (e) {
        console.error("Save failed", e);
        if (!silent) alert(`Save failed: ${e.message}`);
    }
}

async function exportYOLO() {
    try {
        const res = await fetch(`${API_BASE}/export`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            alert(`Exported ${data.exported_count} frames to YOLO format at:\n${data.path}`);
        }
    } catch (e) {
        alert("Export failed.");
    }
}

// --- UI Updates ---

function renderFrameList() {
    const ul = document.getElementById("frameList");
    ul.innerHTML = "";
    frames.forEach((f, i) => {
        const li = document.createElement("li");
        li.className = "frame-item";
        li.id = `frame-${i}`;
        
        const statusClass = (f.annotation_status || 'PENDING').toLowerCase().replace('_', '');
        
        li.innerHTML = `
            <div class="frame-name">${f.image_path}</div>
            <span class="badge ${statusClass}">${f.annotation_status || 'PENDING'}</span>
        `;
        li.addEventListener("click", () => loadFrame(i));
        ul.appendChild(li);
    });
}

function updateStats() {
    let p=0, a=0, s=0;
    frames.forEach(f => {
        const st = (f.annotation_status || 'PENDING').toUpperCase();
        if (st === 'PENDING') p++;
        else if (st === 'ANNOTATED') a++;
        else s++;
    });
    document.getElementById("statPending").innerText = p;
    document.getElementById("statAnnotated").innerText = a;
    document.getElementById("statSkipped").innerText = s;
}

function updateStatusButtons() {
    const st = currentImageData ? currentImageData.status : '';
    document.querySelectorAll(".btn-status").forEach(btn => {
        btn.classList.toggle("active-status", btn.getAttribute("data-status") === st);
    });
}

function setStatus(status) {
    if (!currentImageData) return;
    currentImageData.status = status;
    updateStatusButtons();
    saveHistoryState();
    saveAnnotation();
}

function navigate(dir) {
    let next = currentFrameIndex + dir;
    if (next >= 0 && next < frames.length) {
        loadFrame(next);
    }
}

// --- Undo / Redo ---

function saveHistoryState() {
    const stateStr = JSON.stringify({
        status: currentImageData.status,
        annotations: currentImageData.annotations,
        currentPolygon: currentPolygon
    });
    
    if (historyIndex >= 0 && history[historyIndex] === stateStr) return; // no change
    
    // Discard future
    history = history.slice(0, historyIndex + 1);
    history.push(stateStr);
    historyIndex++;
}

function undo() {
    if (historyIndex > 0) {
        historyIndex--;
        restoreState(history[historyIndex]);
    }
}

function redo() {
    if (historyIndex < history.length - 1) {
        historyIndex++;
        restoreState(history[historyIndex]);
    }
}

function restoreState(stateStr) {
    const state = JSON.parse(stateStr);
    currentImageData.status = state.status;
    currentImageData.annotations = state.annotations;
    currentPolygon = state.currentPolygon;
    
    // Deduce state
    if (currentPolygon && currentPolygon.length > 0) {
        editorState = 'DRAWING';
    } else {
        editorState = 'IDLE';
    }
    selectedPolyIdx = -1;
    draggingVertex = null;
    hoveredVertex = null;
    
    updateStatusButtons();
    render();
}

function clearHistory() {
    history = [];
    historyIndex = -1;
}

// --- Coordinate Math ---

// Screen (canvas pixel) to Normalized (0-1)
function s2n(sx, sy) {
    const imgX = (sx - offsetX) / scale;
    const imgY = (sy - offsetY) / scale;
    return {
        x: Math.max(0, Math.min(1, imgX / imageObj.width)),
        y: Math.max(0, Math.min(1, imgY / imageObj.height))
    };
}

// Normalized to Screen
function n2s(nx, ny) {
    return {
        x: (nx * imageObj.width) * scale + offsetX,
        y: (ny * imageObj.height) * scale + offsetY
    };
}

function fitImage() {
    if (!imageObj.width) return;
    const scaleX = cw / imageObj.width;
    const scaleY = ch / imageObj.height;
    scale = Math.min(scaleX, scaleY) * 0.95; // 5% padding
    
    const dispW = imageObj.width * scale;
    const dispH = imageObj.height * scale;
    offsetX = (cw - dispW) / 2;
    offsetY = (ch - dispH) / 2;
    render();
}

// --- Canvas Interactions ---

function onWheel(e) {
    if (!imageObj.width) return;
    e.preventDefault();
    
    // Zoom around cursor
    const mouseX = e.offsetX;
    const mouseY = e.offsetY;
    
    const zoomFactor = e.deltaY < 0 ? 1.1 : 0.9;
    
    const oldScale = scale;
    scale *= zoomFactor;
    
    // Adjust offset to keep mouse point stationary
    offsetX = mouseX - (mouseX - offsetX) * (scale / oldScale);
    offsetY = mouseY - (mouseY - offsetY) * (scale / oldScale);
    
    render();
}

function onMouseDown(e) {
    if (!imageObj.width) return;
    
    // Middle click or space+click for pan
    if (e.button === 1 || e.shiftKey) {
        isPanning = true;
        panStart = { x: e.offsetX - offsetX, y: e.offsetY - offsetY };
        document.getElementById("canvasWrapper").classList.add("panning");
        return;
    }
    
    // Left click
    if (e.button === 0) {
        const norm = s2n(e.offsetX, e.offsetY);
        
        if (editorState === 'IDLE') {
            // Check if clicking a saved vertex to edit
            if (hoveredVertex && hoveredVertex.polyIdx !== -1) {
                editorState = 'EDITING';
                draggingVertex = hoveredVertex;
                selectedPolyIdx = hoveredVertex.polyIdx;
                render();
                return;
            }
            
            // Check if clicking inside an existing polygon body to select it
            if (currentImageData && currentImageData.annotations) {
                for (let i = currentImageData.annotations.length - 1; i >= 0; i--) {
                    if (isPointInPolygon(norm, currentImageData.annotations[i].polygon)) {
                        selectedPolyIdx = i;
                        render();
                        return;
                    }
                }
            }
            
            // If we click empty space, start drawing
            editorState = 'DRAWING';
            selectedPolyIdx = -1;
            currentPolygon = [[norm.x, norm.y]];
            saveHistoryState();
            render();
            return;
        }
        
        if (editorState === 'DRAWING') {
            // If clicking near first point of current polygon, close it
            if (hoveredVertex && hoveredVertex.polyIdx === -1 && hoveredVertex.vIdx === 0 && currentPolygon.length > 2) {
                closePolygon();
                return;
            }
            
            // Otherwise, add point to current polygon
            currentPolygon.push([norm.x, norm.y]);
            saveHistoryState();
            render();
            return;
        }
    }
}

function onMouseMove(e) {
    if (!imageObj.width) return;
    
    if (isPanning) {
        offsetX = e.offsetX - panStart.x;
        offsetY = e.offsetY - panStart.y;
        render();
        return;
    }
    
    if (editorState === 'EDITING' && draggingVertex) {
        const norm = s2n(e.offsetX, e.offsetY);
        currentImageData.annotations[draggingVertex.polyIdx].polygon[draggingVertex.vIdx] = [norm.x, norm.y];
        render();
        return;
    }
    
    // Hit test vertices for hover
    hoveredVertex = null;
    let found = false;
    
    // Check saved polygons first
    if (currentImageData && currentImageData.annotations) {
        for (let i = 0; i < currentImageData.annotations.length; i++) {
            const poly = currentImageData.annotations[i].polygon;
            for (let j = 0; j < poly.length; j++) {
                const s = n2s(poly[j][0], poly[j][1]);
                if (Math.hypot(e.offsetX - s.x, e.offsetY - s.y) < 8) {
                    hoveredVertex = { polyIdx: i, vIdx: j };
                    found = true;
                    break;
                }
            }
            if (found) break;
        }
    }
    
    // Check current polygon (if drawing)
    if (!found && editorState === 'DRAWING') {
        for (let j = 0; j < currentPolygon.length; j++) {
            const s = n2s(currentPolygon[j][0], currentPolygon[j][1]);
            if (Math.hypot(e.offsetX - s.x, e.offsetY - s.y) < 8) {
                hoveredVertex = { polyIdx: -1, vIdx: j };
                break;
            }
        }
    }
    
    canvas.style.cursor = hoveredVertex ? 'pointer' : 'crosshair';
    
    // Render to show current line being drawn if in drawing mode
    if (editorState === 'DRAWING') {
        render(e.offsetX, e.offsetY);
    } else {
        render(); // just update hover states
    }
}

function onMouseUp(e) {
    if (isPanning) {
        isPanning = false;
        document.getElementById("canvasWrapper").classList.remove("panning");
    }
    if (editorState === 'EDITING') {
        editorState = 'IDLE';
        draggingVertex = null;
        saveHistoryState();
        saveAnnotation();
    }
}

function closePolygon() {
    if (currentPolygon.length >= 3) {
        if (!currentImageData.annotations) currentImageData.annotations = [];
        currentImageData.annotations.push({
            class_id: 0,
            class_name: "waterlogging",
            polygon: [...currentPolygon]
        });
        currentPolygon = [];
        editorState = 'IDLE';
        selectedPolyIdx = currentImageData.annotations.length - 1;
        
        // Auto-mark as annotated
        currentImageData.status = "ANNOTATED";
        updateStatusButtons();
        saveHistoryState();
        saveAnnotation();
        render();
    }
}

function deleteSelectedPolygon() {
    if (editorState === 'IDLE' && selectedPolyIdx !== -1) {
        currentImageData.annotations.splice(selectedPolyIdx, 1);
        selectedPolyIdx = -1;
        saveHistoryState();
        saveAnnotation();
        render();
    } else if (editorState === 'DRAWING' && currentPolygon.length > 0) {
        currentPolygon.pop(); // Delete last point
        if (currentPolygon.length === 0) {
            editorState = 'IDLE';
        }
        saveHistoryState();
        render();
    }
}

// --- Render ---

function render(mouseX = null, mouseY = null) {
    ctx.clearRect(0, 0, cw, ch);
    if (!imageObj.width) return;
    
    // Draw Image
    ctx.drawImage(
        imageObj,
        offsetX, offsetY,
        imageObj.width * scale, imageObj.height * scale
    );
    
    // Draw Saved Polygons
    if (currentImageData && currentImageData.annotations) {
        currentImageData.annotations.forEach((ann, i) => {
            drawPoly(ann.polygon, '#2ecc71', i);
        });
    }
    
    // Draw Current Polygon
    if (currentPolygon.length > 0) {
        drawPoly(currentPolygon, '#3498db', -1, mouseX, mouseY);
    }
}

function drawPoly(poly, color, polyIdx, mouseX = null, mouseY = null) {
    if (poly.length === 0) return;
    
    // Highlight if selected
    const isSelected = (polyIdx !== -1 && polyIdx === selectedPolyIdx);
    const drawColor = isSelected ? '#f1c40f' : color; // Yellow if selected
    
    // 1. Draw the boundary lines (and preview line if active)
    ctx.beginPath();
    const first = n2s(poly[0][0], poly[0][1]);
    ctx.moveTo(first.x, first.y);
    
    for (let i = 1; i < poly.length; i++) {
        const pt = n2s(poly[i][0], poly[i][1]);
        ctx.lineTo(pt.x, pt.y);
    }
    
    if (polyIdx === -1 && mouseX !== null && mouseY !== null) {
        // Drawing mode preview line
        ctx.lineTo(mouseX, mouseY);
    } else if (polyIdx !== -1 && poly.length > 2) {
        // Saved polygon boundary closure
        ctx.closePath();
    }
    
    ctx.lineWidth = isSelected ? 3 : 2;
    ctx.strokeStyle = drawColor;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();
    
    // 2. Fill if it's a closed, saved polygon
    if (polyIdx !== -1 && poly.length > 2) {
        ctx.fillStyle = drawColor + '40'; // 25% opacity
        ctx.fill();
    }
    
    // 3. Draw the vertices on top of the lines
    poly.forEach((pt, vIdx) => {
        const s = n2s(pt[0], pt[1]);
        const isHovered = hoveredVertex && hoveredVertex.polyIdx === polyIdx && hoveredVertex.vIdx === vIdx;
        
        // Only show vertices for selected polygon or drawing polygon
        if (polyIdx === -1 || isSelected || isHovered) {
            ctx.beginPath();
            ctx.arc(s.x, s.y, isHovered ? 6 : 4, 0, Math.PI * 2);
            ctx.fillStyle = isHovered ? '#ffffff' : drawColor;
            ctx.fill();
            
            ctx.lineWidth = 1;
            ctx.strokeStyle = '#000000'; // black border for contrast
            ctx.stroke();
            
            // Visual CLOSE indicator
            if (isHovered && polyIdx === -1 && vIdx === 0 && poly.length > 2) {
                ctx.fillStyle = '#ffffff';
                ctx.font = '12px sans-serif';
                ctx.fillText("CLOSE", s.x + 10, s.y - 10);
            }
        }
    });
}

// Ray-casting point in polygon algorithm
function isPointInPolygon(pt, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const xi = poly[i][0], yi = poly[i][1];
        const xj = poly[j][0], yj = poly[j][1];
        const intersect = ((yi > pt.y) !== (yj > pt.y))
            && (pt.x < (xj - xi) * (pt.y - yi) / (yj - yi) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
}
