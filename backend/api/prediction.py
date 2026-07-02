"""预测 API — 冠军预测、赛程树、单场分析、数据刷新"""

from fastapi import APIRouter, HTTPException, BackgroundTasks

from backend.services.prediction_service import PredictionService

router = APIRouter()
_service = PredictionService()


@router.post("/refresh")
def refresh_data(background_tasks: BackgroundTasks):
    """触发实时数据采集 + 重新预测 (后台任务)"""
    try:
        from data_collection.live_fetcher import fetch_all
        from backend.services.prediction_service import PredictionService
        import threading

        def _refresh():
            fetch_all(force=True)
            PredictionService._global_instance = None  # 清缓存

        thread = threading.Thread(target=_refresh, daemon=True)
        thread.start()

        return {
            "status": "started",
            "message": "数据刷新已在后台启动，预计 30 秒完成",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/refresh/status")
def refresh_status():
    """检查 refreshed 数据是否就绪"""
    from pathlib import Path
    p = Path("data/processed/current_teams_power.csv")
    if p.exists():
        import os
        mtime = os.path.getmtime(p)
        age = __import__('time').time() - mtime
        return {"ready": True, "teams_file": str(p), "age_seconds": round(age)}
    return {"ready": False, "message": "current_teams_power.csv 未生成"}


@router.get("/champion")
def get_champion_rankings():
    """获取夺冠概率排行榜"""
    try:
        rankings = _service.get_champion_rankings()
        return {
            "model_version": "1.0.0-mvp",
            "rankings": rankings,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bracket")
def get_bracket_tree():
    """获取完整淘汰赛赛程树"""
    try:
        tree = _service.get_bracket_tree()
        return {"bracket": tree}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/match/{team_a}/{team_b}")
def get_match_prediction(team_a: str, team_b: str):
    """获取单场比赛预测 + 可解释性分析"""
    try:
        result = _service.explain_match(team_a, team_b)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
