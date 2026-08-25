"""
Generate realistic sample data and seed MongoDB.
Run: python data/sample/generate_sample_data.py
"""
import asyncio, random
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb://localhost:27017"
DB_NAME   = "cloudoptimizer"

PROVIDERS = ["aws", "azure", "gcp"]
COST_BASE = {"aws": 33900, "azure": 35000, "gcp": 30000}

async def seed():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # ── Cost history (12 months) ──────────────────────────────────────────────
    records = []
    now = datetime.utcnow()
    for prov in PROVIDERS:
        base = COST_BASE[prov]
        for i in range(12):
            d = now - timedelta(days=30 * i)
            trend    = base + i * 500
            seasonal = 2000 * (1 + 0.2 * (i % 3))
            noise    = random.uniform(-800, 800)
            amount   = max(0, trend + seasonal + noise)
            records.append({
                "resource_id": f"{prov}-account-total",
                "provider": prov,
                "service": "total",
                "amount": round(amount, 2),
                "currency": "INR",
                "period_start": datetime(d.year, d.month, 1),
                "period_end":   datetime(d.year, d.month, 28),
                "cost_type": "OnDemand",
                "created_at": datetime.utcnow(),
            })

    if records:
        await db.cost_records.delete_many({})
        await db.cost_records.insert_many(records)
        print(f"Inserted {len(records)} cost records")

    # ── Sample recommendations ────────────────────────────────────────────────
    recs = [
        {"recommendation_type":"rightsizing","current_provider":"aws","recommended_provider":"aws",
         "current_cost":10159,"predicted_cost":7111,"estimated_saving":3048,"saving_percentage":30.0,
         "security_score":88.0,"risk_score":20.0,"confidence_score":0.91,
         "reason":"batch-processor (c5.xlarge) avg CPU=4.8% — downsize to c5.large",
         "status":"pending","created_at":datetime.utcnow(),"updated_at":datetime.utcnow()},
        {"recommendation_type":"provider_switch","current_provider":"aws","recommended_provider":"gcp",
         "current_cost":18500,"predicted_cost":14200,"estimated_saving":4300,"saving_percentage":23.2,
         "security_score":85.0,"risk_score":35.0,"confidence_score":0.88,
         "reason":"Web Application: GCP Compute Engine ₹14,200 vs AWS EC2 ₹18,500",
         "status":"pending","created_at":datetime.utcnow(),"updated_at":datetime.utcnow()},
        {"recommendation_type":"idle","current_provider":"aws","recommended_provider":"aws",
         "current_cost":2521,"predicted_cost":0,"estimated_saving":2521,"saving_percentage":100.0,
         "security_score":90.0,"risk_score":10.0,"confidence_score":0.95,
         "reason":"worker-dev (t3.medium) idle — CPU avg 3.1% over 7 days",
         "status":"pending","created_at":datetime.utcnow(),"updated_at":datetime.utcnow()},
    ]
    await db.optimization_recommendations.delete_many({})
    await db.optimization_recommendations.insert_many(recs)
    print(f"Inserted {len(recs)} recommendations")

    # ── Demo user ────────────────────────────────────────────────────────────
    from passlib.context import CryptContext
    pwd = CryptContext(schemes=["bcrypt"])
    existing = await db.users.find_one({"email": "admin@demo.com"})
    if not existing:
        await db.users.insert_one({
            "email": "admin@demo.com",
            "hashed_password": pwd.hash("admin123"),
            "full_name": "Admin User",
            "is_active": True,
            "is_admin": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        })
        print("Created demo user: admin@demo.com / admin123")
    else:
        print("Demo user already exists")

    client.close()
    print("✅ Sample data seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed())
