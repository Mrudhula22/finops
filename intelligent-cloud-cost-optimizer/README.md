# Intelligent Multi-Cloud Cost Optimization Using Autonomous and Explainable AI

A full-stack AI-powered system that predicts, analyzes, and autonomously optimizes cloud costs across AWS, Azure, and GCP with full explainability.

---

## Architecture Overview

```
User → Natural Language Query → AI Planner Agent
  → Multi-Cloud Data Collection (AWS + Azure + GCP)
  → Unified Data Layer
  → Predictive Cost Analysis (ML Forecasting)
  → Optimization Engine (Multi-Cloud Comparison)
  → Security Analysis + Risk Assessment
  → Explainable AI
  → Human Approval / Autonomous Execution
  → Monitor → Feedback → Agent Memory
```

---

## Five Core Modules

| Module | Description |
|--------|-------------|
| **Module 1** | Predictive Cost Optimization (ARIMA, Prophet, XGBoost, LSTM) |
| **Module 2** | Autonomous AI Agent (Recommendation + Autonomous Modes) |
| **Module 3** | Multi-Cloud Cost Optimization (AWS vs Azure vs GCP) |
| **Module 4** | Security-Aware Cost Optimization |
| **Module 5** | Explainable AI (WHY, WHAT, HOW decisions) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Recharts, TailwindCSS, Axios |
| Backend | Python 3.11, FastAPI, SQLAlchemy |
| Database | PostgreSQL 15, Redis |
| ML Models | scikit-learn, XGBoost, Prophet, statsmodels |
| AI Agent | OpenAI GPT-4o |
| Cloud SDKs | boto3 (AWS), azure-sdk, google-cloud |
| Deployment | Docker, Docker Compose |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose installed
- Python 3.11+
- Node.js 18+

### 1. Clone & Configure
```bash
git clone https://github.com/yourname/intelligent-cloud-cost-optimizer
cd intelligent-cloud-cost-optimizer
cp .env.example .env
# Edit .env with your cloud credentials
```

### 2. Start with Docker
```bash
docker-compose up -d
```

### 3. Run Backend Locally (without Docker)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 4. Run Frontend Locally
```bash
cd frontend
npm install
npm start
```

### 5. Access
- **Frontend Dashboard**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **API Docs (ReDoc)**: http://localhost:8000/redoc

---

## Project Structure

```
intelligent-cloud-cost-optimizer/
├── frontend/               # React dashboard
│   └── src/
│       ├── components/     # Reusable UI components
│       ├── pages/          # Route pages
│       └── services/       # API service layer
├── backend/
│   ├── agents/             # AI agent layer
│   ├── cloud/              # AWS / Azure / GCP adapters
│   ├── ml/                 # ML forecasting & anomaly models
│   ├── optimization/       # Cost & multi-cloud optimization
│   ├── execution/          # Autonomous execution engine
│   ├── explainability/     # Explainable AI layer
│   ├── database/           # DB models & schemas
│   ├── api/                # FastAPI routes
│   └── main.py
├── data/                   # Sample & processed data
├── experiments/            # Research notebooks
├── tests/                  # Test suite
└── docker-compose.yml
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | User authentication |
| GET | `/api/costs/summary` | Multi-cloud cost summary |
| GET | `/api/costs/breakdown` | Per-resource cost breakdown |
| POST | `/api/forecast/predict` | Run cost forecast |
| GET | `/api/recommendations` | Get AI recommendations |
| POST | `/api/recommendations/execute` | Execute recommendation |
| GET | `/api/multicloud/compare` | Compare cloud providers |
| GET | `/api/execution/history` | Execution audit log |

---

## Agent Modes

**Recommendation Mode** (default, safe):
```
AI → Analyze → Recommend → Human Approval → Execute
```

**Autonomous Mode** (requires explicit enable):
```
AI → Analyze → Recommend → Validate → Execute → Monitor → Rollback if needed
```

---

## License
MIT
