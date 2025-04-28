import uvicorn
from fastapi import FastAPI, HTTPException, Query
import sqlalchemy
import databases
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Union
import sqlite3

# Database configuration
DATABASE_URL = "sqlite:///./cloud_access.db"
database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

# Table definitions
plans = sqlalchemy.Table(
    "plans", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("description", sqlalchemy.Text),
)
permissions = sqlalchemy.Table(
    "permissions", metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("name", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("endpoint", sqlalchemy.String, unique=True),
    sqlalchemy.Column("description", sqlalchemy.Text),
)
plan_permissions = sqlalchemy.Table(
    "plan_permissions", metadata,
    sqlalchemy.Column("plan_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("plans.id"), primary_key=True),
    sqlalchemy.Column("permission_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("permissions.id"), primary_key=True),
    sqlalchemy.Column("limit", sqlalchemy.Integer),  # max calls allowed
)
subscriptions = sqlalchemy.Table(
    "subscriptions", metadata,
    sqlalchemy.Column("user_id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("plan_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("plans.id")),
)
usage = sqlalchemy.Table(
    "usage", metadata,
    sqlalchemy.Column("user_id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("permission_id", sqlalchemy.Integer, sqlalchemy.ForeignKey("permissions.id"), primary_key=True),
    sqlalchemy.Column("count", sqlalchemy.Integer, default=0),
)

# Create engine and tables
engine = sqlalchemy.create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
metadata.create_all(engine)

# FastAPI instance
app = FastAPI(title="Cloud Service Access Management System")

# Pydantic models
class PlanCreate(BaseModel):
    name: str
    description: str
    permission_ids: Union[int, List[int]] = Field(default_factory=list)
    limits: Union[int, List[int]] = Field(default_factory=list)

    @validator("permission_ids", "limits", pre=True)
    def ensure_list(cls, v):
        if v is None:
            return []
        return v if isinstance(v, list) else [v]

class PlanUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permission_ids: Optional[Union[int, List[int]]] = None
    limits: Optional[Union[int, List[int]]] = None

    @validator("permission_ids", "limits", pre=True)
    def ensure_list_optional(cls, v):
        if v is None:
            return None
        return v if isinstance(v, list) else [v]

class PermissionCreate(BaseModel):
    name: str
    endpoint: str
    description: Optional[str] = None

class PermissionUpdate(BaseModel):
    name: Optional[str] = None
    endpoint: Optional[str] = None
    description: Optional[str] = None

class SubscribeRequest(BaseModel):
    user_id: int
    plan_id: int

class UsageRequest(BaseModel):
    endpoint: str

# Application startup/shutdown events
@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# Helper functions
async def get_plan(plan_id: int):
    return await database.fetch_one(plans.select().where(plans.c.id == plan_id))

async def get_permission_by_id(permission_id: int):
    return await database.fetch_one(permissions.select().where(permissions.c.id == permission_id))

async def get_permission_by_endpoint(endpoint: str):
    return await database.fetch_one(permissions.select().where(permissions.c.endpoint == endpoint))

async def get_subscription(user_id: int):
    return await database.fetch_one(subscriptions.select().where(subscriptions.c.user_id == user_id))

async def check_access(user_id: int, endpoint: str):
    perm = await get_permission_by_endpoint(endpoint)
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found for endpoint")
    sub = await get_subscription(user_id)
    if not sub:
        return False, "No subscription"
    plan_perm = await database.fetch_one(
        plan_permissions.select().where(
            (plan_permissions.c.plan_id == sub.plan_id) &
            (plan_permissions.c.permission_id == perm.id)
        )
    )
    if not plan_perm:
        return False, "Endpoint not in plan permissions"
    usage_row = await database.fetch_one(
        usage.select().where(
            (usage.c.user_id == user_id) &
            (usage.c.permission_id == perm.id)
        )
    )
    used = usage_row['count'] if usage_row else 0
    if used >= plan_perm['limit']:
        return False, "Usage limit reached"
    return True, None

async def track_usage(user_id: int, perm_id: int):
    row = await database.fetch_one(
        usage.select().where(
            (usage.c.user_id == user_id) &
            (usage.c.permission_id == perm_id)
        )
    )
    if row:
        new_count = row['count'] + 1
        await database.execute(
            usage.update()
                  .where((usage.c.user_id == user_id) & (usage.c.permission_id == perm_id))
                  .values(count=new_count)
        )
    else:
        await database.execute(
            usage.insert().values(user_id=user_id, permission_id=perm_id, count=1)
        )

# Management APIs
@app.post("/plans")
async def create_plan(payload: PlanCreate):
    if len(payload.permission_ids) != len(payload.limits):
        raise HTTPException(status_code=400, detail="Permissions and limits lists must have the same length")
    try:
        plan_id = await database.execute(plans.insert().values(
            name=payload.name, description=payload.description
        ))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Plan name must be unique")
    for perm_id, limit in zip(payload.permission_ids, payload.limits):
        await database.execute(
            plan_permissions.insert().values(
                plan_id=plan_id, permission_id=perm_id, limit=limit
            )
        )
    return {"id": plan_id}

@app.put("/plans/{plan_id}")
async def modify_plan(plan_id: int, payload: PlanUpdate):
    if not await get_plan(plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")
    update_data = {k: v for k, v in payload.dict().items() if k in ['name','description'] and v is not None}
    if update_data:
        await database.execute(
            plans.update().where(plans.c.id == plan_id).values(**update_data)
        )
    if payload.permission_ids is not None:
        if len(payload.permission_ids) != len(payload.limits):
            raise HTTPException(status_code=400, detail="Permissions and limits lists must have the same length")
        await database.execute(plan_permissions.delete().where(plan_permissions.c.plan_id == plan_id))
        for perm_id, limit in zip(payload.permission_ids, payload.limits):
            await database.execute(
                plan_permissions.insert().values(
                    plan_id=plan_id, permission_id=perm_id, limit=limit
                )
            )
    return {"status": "updated"}

@app.delete("/plans/{plan_id}")
async def delete_plan(plan_id: int):
    await database.execute(plan_permissions.delete().where(plan_permissions.c.plan_id == plan_id))
    await database.execute(plans.delete().where(plans.c.id == plan_id))
    return {"status": "deleted"}

@app.post("/permissions")
async def add_permission(payload: PermissionCreate):
    try:
        perm_id = await database.execute(permissions.insert().values(
            name=payload.name, endpoint=payload.endpoint, description=payload.description
        ))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Permission name or endpoint must be unique")
    return {"id": perm_id}

@app.put("/permissions/{permission_id}")
async def modify_permission(permission_id: int, payload: PermissionUpdate):
    if not await get_permission_by_id(permission_id):
        raise HTTPException(status_code=404, detail="Permission not found")
    update_data = {k: v for k, v in payload.dict().items() if v is not None}
    if update_data:
        await database.execute(
            permissions.update().where(permissions.c.id == permission_id).values(**update_data)
        )
    return {"status": "updated"}

@app.delete("/permissions/{permission_id}")
async def delete_permission(permission_id: int):
    await database.execute(plan_permissions.delete().where(plan_permissions.c.permission_id == permission_id))
    await database.execute(permissions.delete().where(permissions.c.id == permission_id))
    return {"status": "deleted"}

# Subscription APIs
@app.post("/subscriptions")
async def subscribe(payload: SubscribeRequest):
    if await get_subscription(payload.user_id):
        raise HTTPException(status_code=400, detail="Subscription already exists")
    await database.execute(subscriptions.insert().values(
        user_id=payload.user_id, plan_id=payload.plan_id
    ))
    return {"status": "subscribed"}

@app.put("/subscriptions/{user_id}")
async def modify_subscription(user_id: int, payload: SubscribeRequest):
    if not await get_subscription(user_id):
        raise HTTPException(status_code=404, detail="Subscription not found")
    await database.execute(
        subscriptions.update().where(subscriptions.c.user_id == user_id).values(plan_id=payload.plan_id)
    )
    return {"status": "updated"}

@app.get("/subscriptions/{user_id}")
async def view_subscription(user_id: int):
    sub = await get_subscription(user_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    plan = await get_plan(sub['plan_id'])
    # Guard missing plans
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found for subscription")

    rows = await database.fetch_all(
        plan_permissions.select().where(plan_permissions.c.plan_id == plan['id'])
    )
    perms = []
    for row in rows:
        perm = await get_permission_by_id(row['permission_id'])
        if not perm:
            continue
        perms.append({
            'permission_id': perm['id'],
            'endpoint': perm['endpoint'],
            'limit': row['limit']
        })

    return {
        'user_id': user_id,
        'plan': {
            'id': plan['id'],
            'name': plan['name'],
            'description': plan['description']
        },
        'permissions': perms
    }

@app.get("/subscriptions/{user_id}/usage")
async def view_usage(user_id: int):
    if not await get_subscription(user_id):
        raise HTTPException(status_code=404, detail="Subscription not found")
    rows = await database.fetch_all(usage.select().where(usage.c.user_id == user_id))
    result = []
    for row in rows:
        perm = await get_permission_by_id(row['permission_id'])
        result.append({'endpoint': perm['endpoint'], 'count': row['count']})
    return {'user_id': user_id, 'usage': result}

@app.get("/access/{user_id}/{endpoint}")
async def access_control(user_id: int, endpoint: str):
    allowed, reason = await check_access(user_id, endpoint)
    return {'user_id': user_id, 'endpoint': endpoint, 'access': allowed, 'reason': reason}

@app.post("/usage/{user_id}")
async def record_usage(user_id: int, payload: UsageRequest):
    allowed, reason = await check_access(user_id, payload.endpoint)
    if not allowed:
        if reason == "No subscription":
            # user has no subscription
            raise HTTPException(status_code=404, detail="Subscription not found")
        # other reasons are forbidden
        raise HTTPException(status_code=403, detail=reason)
    perm = await get_permission_by_endpoint(payload.endpoint)
    await track_usage(user_id, perm['id'])
    return {'status': 'recorded'}

@app.get("/usage/{user_id}/limit")
async def limit_status(user_id: int):
    sub = await get_subscription(user_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    rows = await database.fetch_all(
        plan_permissions.select().where(plan_permissions.c.plan_id == sub['plan_id'])
    )
    result = []
    for row in rows:
        perm = await get_permission_by_id(row['permission_id'])
        usage_row = await database.fetch_one(
            usage.select().where(
                (usage.c.user_id == user_id) & (usage.c.permission_id == row['permission_id'])
            )
        )
        used = usage_row['count'] if usage_row else 0
        result.append({'endpoint': perm['endpoint'], 'used': used, 'limit': row['limit']})
    return {'user_id': user_id, 'limits': result}

SERVICES = [f"service{i}" for i in range(1, 7)]

@app.get("/services/{service_name}")
async def call_service(service_name: str, user_id: int = Query(..., description="User ID making the call")):
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail="Service not found")
    allowed, reason = await check_access(user_id, service_name)
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)
    perm = await get_permission_by_endpoint(service_name)
    await track_usage(user_id, perm['id'])
    return {'service': service_name, 'status': 'OK'}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
