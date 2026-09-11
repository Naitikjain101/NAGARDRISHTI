# Urban Watch — Model Policy

**Version: Phase 1**

---

## Purpose

This document defines the rules that govern how AI models are selected, evaluated, and accepted or rejected for use in Urban Watch. Every team member and every automated script must follow these rules.

Violation of this policy results in fabricated metrics, unreliable detections, and system discredit.

---

## Rule 1: Never Trust Model Filenames

A model named `pothole_detector.pt` is NOT automatically a pothole detector.

A model named `traffic_yolo.pt` is NOT automatically a traffic detector.

**Every model must be loaded and its `model.names` attribute must be inspected programmatically before any assumption is made about its capabilities.**

```python
from ultralytics import YOLO
model = YOLO("some_model.pt")
print(model.names)   # ← This is the ground truth
```

---

## Rule 2: Inspect Before Use

For every candidate model, record:

| Field | How to Obtain |
|---|---|
| Model filename | filename |
| Model family | model.cfg or architecture name |
| Task | model.task |
| Classes | model.names |
| Number of classes | len(model.names) |
| Parameter count | model.info() |
| Expected input size | model config |
| Source URL | documentation/release |
| License | documentation/release |
| Training dataset | documentation/release |

If any field cannot be determined: mark it `UNKNOWN`.

If `UNKNOWN` fields are critical (e.g., license is unknown for a production system): **reject the model**.

---

## Rule 3: Never Fabricate Metrics

The following are FORBIDDEN:

- Hardcoding mAP, precision, recall, or F1 values
- Copying benchmark numbers from a paper without re-running inference
- Reporting "~95% accuracy" without a ground-truth test
- Using confidence scores from model output and claiming they are system accuracy

What to report instead:

```
mAP50: NOT MEASURED — no ground-truth validation dataset
Precision: NOT MEASURED
Recall: NOT MEASURED
```

FPS values must be measured on the actual deployment hardware. Do not copy FPS from a benchmark run on a different machine.

---

## Rule 4: Never Rename Unsupported Classes

If a model's `model.names` contains:

```python
{0: 'person', 1: 'bicycle', 2: 'car', ...}
```

It does NOT detect:
- potholes
- helmets
- waterlogging
- road cracks
- traffic signs

**Do NOT map these classes to custom names.** Do not report that a COCO model detects potholes because it detects "bumps on the road."

---

## Rule 5: Benchmark Before Production Selection

A model must be benchmarked on real video before it enters the production configuration.

Benchmark must measure:

- Inference latency per frame (milliseconds)
- FPS under realistic conditions
- Detection count on a real video
- False positive rate (subjectively estimated if no ground truth)
- Tracking stability (ID switches, lost tracks)
- Memory usage
- Device actually used

Select based on measured results. Not based on:
- Model recency ("newer = better")
- File size ("smaller = faster")
- README claims ("achieves 99% accuracy")

---

## Rule 6: Record Model License

Every accepted model must have its license recorded before use.

| License | Commercial Use | Notes |
|---|---|---|
| AGPL-3.0 | Restricted | Ultralytics default — requires open source if distributed |
| Apache 2.0 | Permitted | Most permissive open-source license |
| MIT | Permitted | Most permissive open-source license |
| GPL-3.0 | Restricted | Must open-source derivative works |
| CC BY 4.0 | Permitted with attribution | Attribution required |
| Proprietary | NOT PERMITTED | Never use without explicit agreement |
| Unknown | NOT PERMITTED | Reject unless clarified |

For SIH prototype purposes: AGPL-3.0 is acceptable since this is a non-commercial hackathon project. Record explicitly.

---

## Rule 7: Record Model Source

For every accepted model record:

- Official source URL (GitHub release, Hugging Face, official docs)
- Whether the checkpoint was downloaded from an **official** or **unofficial** source
- Whether the source could be verified as authentic

Do NOT use models from anonymous GitHub mirrors or unnamed personal accounts without cross-referencing against the official repository.

---

## Rule 8: Separate Raw Detections from Tracked Objects

Raw detections (from a single frame, no track ID) and tracked objects (persistent across frames, with track ID) are **different data structures**.

A detection without a track ID must NOT be discarded — it may be displayed or counted separately.

A tracked vehicle must use its first-seen timestamp as the start of tracking, not the current frame timestamp.

Vehicle counting uses **unique track IDs only**. It does NOT sum raw detection counts.

---

## Rule 9: Accuracy Takes Priority Over FPS

When a faster model produces more false positives or misses vehicles, it is NOT acceptable to choose it for speed.

Decision criteria priority:

1. Detection reliability (does it find all required classes?)
2. False positive rate (does it invent detections?)
3. Tracking stability (does ByteTrack maintain consistent IDs?)
4. Small-object performance (can it detect distant motorcycles?)
5. FPS (fast enough for near-realtime use: target >10 FPS minimum)
6. Memory usage

A model that runs at 60 FPS but misses 40% of vehicles fails criterion 1. It is rejected.

---

## Rule 10: No Model Enters Production Without Evidence

"Production configuration" means the model is actively used when processing real uploaded videos.

A model may enter production configuration ONLY when:

- [ ] model.names has been inspected and contains required classes
- [ ] model has been loaded successfully on the target device
- [ ] at least one real video inference has been run
- [ ] inference latency has been measured
- [ ] false positive rate is acceptable (subjectively evaluated)
- [ ] tracking produces stable IDs
- [ ] license is recorded and acceptable

---

## Phase 1 Accepted Model Classes

For Phase 1, the model must contain these COCO classes at minimum:

| Class | COCO ID |
|---|---|
| person | 0 |
| bicycle | 1 |
| car | 2 |
| motorcycle | 3 |
| bus | 5 |
| truck | 7 |

Any model that does not contain all six classes is **rejected for Phase 1**.

---

## Phase 1 Out-of-Scope Classes (Future Phases)

| Class | Status | Reason |
|---|---|---|
| pothole | NOT AVAILABLE | No valid pretrained COCO-based model; requires specialized dataset |
| helmet | NOT AVAILABLE | Requires specialized training data |
| nohelmet | NOT AVAILABLE | Requires specialized training data |
| waterlogging | NOT AVAILABLE | Requires specialized training data |
| road damage | NOT AVAILABLE | Requires specialized training data |
| license plate | NOT AVAILABLE | Requires specialized ANPR model |

**Do NOT attempt to detect these classes in Phase 1 by repurposing COCO models.**

---

## Model Rejection Log

All rejected candidates must be logged in `PHASE_1_REPORT.md` with:

- Model name
- Source
- Reason for rejection
- Date inspected

---

*Document version: Phase 1 initial*
*Last updated: 2026-08-31*
