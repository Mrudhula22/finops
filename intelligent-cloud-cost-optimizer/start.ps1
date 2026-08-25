# ── Quick start script (Windows PowerShell) ──────────────────────────────────
Write-Host "🚀 Starting Intelligent Cloud Cost Optimizer..." -ForegroundColor Cyan

# 1. Start MongoDB + Redis via Docker
Write-Host "`n[1/3] Starting MongoDB and Redis..." -ForegroundColor Yellow
docker-compose up -d mongodb redis
Start-Sleep -Seconds 5

# 2. Backend
Write-Host "`n[2/3] Starting FastAPI backend..." -ForegroundColor Yellow
Set-Location backend
pip install -r requirements.txt -q
Start-Process powershell -ArgumentList "-NoExit", "-Command", "uvicorn main:app --reload --port 8000"
Set-Location ..

# 3. Frontend
Write-Host "`n[3/3] Starting React frontend..." -ForegroundColor Yellow
Set-Location frontend
Start-Process powershell -ArgumentList "-NoExit", "-Command", "npm install; npm start"
Set-Location ..

Write-Host "`n✅ All services starting!" -ForegroundColor Green
Write-Host "   Frontend : http://localhost:3000" -ForegroundColor White
Write-Host "   API      : http://localhost:8000" -ForegroundColor White
Write-Host "   API Docs : http://localhost:8000/docs" -ForegroundColor White
Write-Host "`n📧 Demo login: admin@demo.com / admin123" -ForegroundColor Cyan
Write-Host "   (Run: python data/sample/generate_sample_data.py to seed DB first)" -ForegroundColor Gray
