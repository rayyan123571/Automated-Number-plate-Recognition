# 🚗 Automated Number Plate Recognition (ANPR) System

A full-stack **Automatic Number Plate Recognition** system built with **YOLOv8** for plate detection, **EasyOCR** for text recognition, **FastAPI** for the backend API, and **Next.js** for the frontend dashboard.

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green?logo=fastapi)
![Next.js](https://img.shields.io/badge/Next.js-15+-black?logo=next.js)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-purple)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Features

- **Real-time Detection** — Upload images or use a live webcam feed via WebSocket
- **YOLOv8 Plate Detection** — Fine-tuned YOLOv8n model for license plate localization
- **EasyOCR Text Recognition** — Extracts plate text from detected regions
- **REST API** — FastAPI backend with Swagger docs at `/docs`
- **WebSocket Live Feed** — Real-time detection with FPS counter and bounding box overlay
- **Analytics Dashboard** — Charts, stats cards, and detection trends via Recharts
- **Detection History** — Full searchable history of all detections stored in SQLite
- **Dark Theme UI** — Modern glassmorphism design with Tailwind CSS v4
- **Training Pipeline** — CLI tool to train/fine-tune YOLOv8 on custom datasets
- **ONNX Export** — Export trained models to ONNX for production deployment

---

## 📁 Project Structure

```
ANPR_project/
├── app/                          # Backend (FastAPI)
│   ├── core/                     # Config, database, logging
│   │   ├── config.py             # Pydantic settings (.env)
│   │   ├── database.py           # SQLAlchemy engine & session
│   │   └── logging_config.py     # Structured logging setup
│   ├── models/                   # SQLAlchemy ORM models
│   │   └── detection.py          # Detection table schema
│   ├── routes/                   # API endpoints
│   │   ├── detection.py          # POST /detect — image upload
│   │   ├── detections.py         # GET /detections — history & stats
│   │   ├── health.py             # GET /health — system status
│   │   └── ws_detection.py       # WebSocket /ws/detect — live feed
│   ├── services/                 # Business logic
│   │   ├── anpr_service.py       # YOLO + OCR pipeline
│   │   ├── detector.py           # YOLOv8 model loader
│   │   ├── detection_store.py    # Database CRUD operations
│   │   ├── ocr_service.py        # EasyOCR wrapper
│   │   ├── training_service.py   # Training pipeline service
│   │   ├── evaluation_service.py # Model evaluation service
│   │   └── dataset_validator.py  # Dataset integrity checker
│   ├── utils/                    # Shared utilities
│   └── main.py                   # FastAPI app entry point
├── anpr-frontend/                # Frontend (Next.js)
│   ├── src/
│   │   ├── app/                  # Next.js App Router pages
│   │   │   ├── page.tsx          # Dashboard home
│   │   │   ├── live/             # Live webcam detection
│   │   │   ├── analytics/        # Analytics charts & stats
│   │   │   ├── history/          # Detection history table
│   │   │   └── settings/         # System settings
│   │   ├── components/           # Reusable React components
│   │   ├── hooks/                # Custom hooks (useDetections, useWebSocket)
│   │   ├── services/             # API client (anprService)
│   │   └── providers/            # React Query provider
│   ├── package.json
│   └── tailwind.config.ts
├── dataset/                      # Dataset configuration
│   └── data.yaml                 # YOLOv8 dataset config
├── Automatic Plate Number Recognition.v4i.yolov8/
│   ├── train/                    # Training images & labels
│   ├── valid/                    # Validation images & labels
│   └── test/                     # Test images & labels
├── train.py                      # CLI training entry point
├── requirements.txt              # Python dependencies
└── .gitignore
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.12+**
- **Node.js 18+**
- **Git**

### 1. Clone the Repository

```bash
git clone https://github.com/rayyan123571/Automated-Number-plate-Recognition.git
cd Automated-Number-plate-Recognition
```

### 2. Backend Setup

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\Activate.ps1
# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Download Model Weights

Download a pretrained YOLOv8n model or train your own (see Training section):

```bash
# Create models directory
mkdir models

# Option A: Use pretrained YOLOv8n (COCO)
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
mv yolov8n.pt models/best.pt

# Option B: Train on the ANPR dataset (recommended)
python train.py --epochs 50 --batch 16
```

### 4. Start the Backend

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000` with Swagger docs at `http://localhost:8000/docs`.

### 5. Frontend Setup

```bash
cd anpr-frontend
npm install
npm run dev
```

The dashboard will be available at `http://localhost:3000`.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/detect` | Upload an image for plate detection & OCR |
| `GET` | `/detections` | Get detection history (paginated) |
| `GET` | `/detections/stats` | Get detection statistics |
| `GET` | `/detections/{id}` | Get a specific detection |
| `GET` | `/health` | System health check |
| `WS` | `/ws/detect` | WebSocket for real-time live detection |

---

## 🏋️ Training

Train or fine-tune the YOLOv8 model on the ANPR dataset:

```bash
# Full training pipeline (train + evaluate)
python train.py

# Custom configuration
python train.py --epochs 100 --batch 8 --model yolov8s.pt

# Validate dataset only
python train.py --validate-only

# Resume interrupted training
python -c "from ultralytics import YOLO; YOLO('runs/anpr_train/weights/last.pt').train(resume=True)"
```

### Training Options

| Flag | Default | Description |
|------|---------|-------------|
| `--model` | `yolov8n.pt` | YOLOv8 variant (n/s/m/l/x) |
| `--epochs` | `50` | Number of training epochs |
| `--batch` | `16` | Batch size |
| `--imgsz` | `640` | Input image size |
| `--patience` | `15` | Early stopping patience |
| `--lr0` | `0.01` | Initial learning rate |
| `--device` | `auto` | Device: `''` (auto), `0` (GPU), `cpu` |
| `--no-export` | `false` | Skip ONNX export |
| `--skip-eval` | `false` | Skip test set evaluation |

---

## 🛠️ Tech Stack

### Backend
- **FastAPI** — High-performance async web framework
- **Ultralytics YOLOv8** — State-of-the-art object detection
- **EasyOCR** — Optical character recognition
- **SQLAlchemy 2.x** — ORM with SQLite
- **Uvicorn** — ASGI server
- **WebSocket** — Real-time communication

### Frontend
- **Next.js 15+** — React framework with App Router
- **React 19** — UI library
- **TypeScript** — Type safety
- **Tailwind CSS v4** — Utility-first CSS
- **React Query (TanStack)** — Server state management
- **Recharts** — Data visualization
- **Framer Motion** — Animations

### ML/AI
- **YOLOv8n** — 3.2M params, real-time inference
- **EasyOCR** — Multi-language OCR engine
- **ONNX** — Model export for production

---

## 📊 Dataset

The project uses the [Automatic Plate Number Recognition v4](https://universe.roboflow.com/) dataset from Roboflow:

- **1,146** training images
- **107** validation images  
- **57** test images
- **1 class**: `plate-number`
- **Format**: YOLOv8 (normalized bounding boxes)

---

## 📄 License

This project is licensed under the MIT License.

---

## 🙏 Acknowledgments

- [Ultralytics](https://github.com/ultralytics/ultralytics) — YOLOv8
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) — OCR engine
- [Roboflow](https://roboflow.com/) — Dataset hosting
- [FastAPI](https://fastapi.tiangolo.com/) — Web framework
- [Next.js](https://nextjs.org/) — React framework
