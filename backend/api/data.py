"""数据 API — 球队信息、排名查询"""

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/teams")
def get_teams():
    """获取所有球队列表"""
    try:
        from models.team_rating import _BUILTIN_TEAMS
        return {"teams": _BUILTIN_TEAMS}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
