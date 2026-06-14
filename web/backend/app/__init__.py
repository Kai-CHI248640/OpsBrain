"""
OpsBrain Web — FastAPI Application

单 Agent 架构 + 工具分组
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes.auth import auth_router
from .routes.dashboard import dashboard_router
from .routes.topology import topology_router
from .routes.apis import apis_router
from .routes.settings import settings_router
from .routes.projects import projects_router
from .routes.agents import agents_router
from .routes.feishu import feishu_router
from .routes.agent import agent_router
from .routes.subagents import subagent_router

app = FastAPI(
    title="OpsBrain",
    description="AI 网络运维平台",
    version="3.0.0",
    docs_url="/opsbrain/docs",
    redoc_url="/opsbrain/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/opsbrain/api/v1"

app.include_router(auth_router, prefix=f"{PREFIX}/auth", tags=["认证"])
app.include_router(dashboard_router, prefix=f"{PREFIX}/dashboard", tags=["控制台"])
app.include_router(topology_router, prefix=f"{PREFIX}/topology", tags=["拓扑"])
app.include_router(apis_router, prefix=f"{PREFIX}/apis", tags=["API Keys"])
app.include_router(settings_router, prefix=f"{PREFIX}/settings", tags=["设置"])
app.include_router(projects_router, prefix=f"{PREFIX}/projects", tags=["项目"])
app.include_router(agents_router, prefix=f"{PREFIX}/agents", tags=["Agent 配置"])
app.include_router(feishu_router, prefix=f"{PREFIX}/feishu", tags=["飞书"])
app.include_router(agent_router, prefix=f"{PREFIX}/agent", tags=["AI Agent"])
app.include_router(subagent_router, prefix=f"{PREFIX}/subagents", tags=["Subagent (兼容)"])


@app.get("/opsbrain/healthz")
async def healthz():
    return {"status": "ok"}
