"""预测 API — 冠军预测、赛程树、单场分析"""

from fastapi import APIRouter, HTTPException

from backend.services.prediction_service import PredictionService

router = APIRouter()
_service = PredictionService()


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
