from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.route_planner import router as route_planner_router

app = FastAPI(title="JaGOOD Smart Route Planner", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(route_planner_router)
