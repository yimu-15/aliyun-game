"""
全局配置 — 所有可调节参数集中管理

使用方式:
    from config.settings import settings
    print(settings.DATA_DIR)
"""

import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv 未安装时跳过

# =============================================================================
# 路径配置
# =============================================================================

class Paths:
    """项目路径常量"""

    PROJECT_ROOT = Path(os.getenv("PROJECT_ROOT", str(Path(__file__).resolve().parents[1])))
    DATA_DIR = PROJECT_ROOT / os.getenv("DATA_DIR", "data")
    CONFIG_DIR = PROJECT_ROOT / "config"
    MODELS_DIR = PROJECT_ROOT / "models"
    BACKEND_DIR = PROJECT_ROOT / "backend"
    APP_DIR = PROJECT_ROOT / "app"
    SCRIPTS_DIR = PROJECT_ROOT / "scripts"
    DOCS_DIR = PROJECT_ROOT / "docs"
    TESTS_DIR = PROJECT_ROOT / "tests"

    # 数据子目录
    DATA_RAW = DATA_DIR / "raw"
    DATA_RAW_MATCHES = DATA_RAW / "matches"
    DATA_RAW_RANKINGS = DATA_RAW / "rankings"
    DATA_RAW_PLAYERS = DATA_RAW / "players"
    DATA_RAW_TOURNAMENTS = DATA_RAW / "tournaments"
    DATA_PROCESSED = DATA_DIR / "processed"
    DATA_PROCESSED_FEATURES = DATA_PROCESSED / "features"
    DATA_PROCESSED_MODELS = DATA_PROCESSED / "models"
    DATA_EXTERNAL = DATA_DIR / "external"
    DATA_METADATA = DATA_DIR / "metadata"
    DATA_LOGS = DATA_DIR / "logs"
    DATA_SOURCES = DATA_DIR / "sources"

    # 配置文件
    DATA_SOURCES_YAML = CONFIG_DIR / "data_sources.yaml"
    PREDICTION_MODEL_YAML = CONFIG_DIR / "prediction_model_design.yaml"

    # 静态资源
    APP_STATIC = APP_DIR / "static"


# =============================================================================
# 后端服务配置
# =============================================================================

class BackendConfig:
    """FastAPI 后端配置"""

    HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
    PORT = int(os.getenv("BACKEND_PORT", "8000"))
    RELOAD = os.getenv("BACKEND_RELOAD", "true").lower() == "true"
    TITLE = "世界杯冠军预测 Agent API"
    VERSION = "1.0.0"
    DESCRIPTION = "可解释的世界杯冠军预测服务"


# =============================================================================
# 前端服务配置
# =============================================================================

class AppConfig:
    """Streamlit 前端配置"""

    PORT = int(os.getenv("STREAMLIT_PORT", "8501"))
    TITLE = "世界杯冠军预测 Agent"
    PAGE_ICON = "⚽"
    LAYOUT = "wide"


# =============================================================================
# 预测引擎配置
# =============================================================================

class PredictionConfig:
    """预测模型参数"""

    # 蒙特卡洛模拟
    MONTE_CARLO_SIMULATIONS = int(os.getenv("MONTE_CARLO_SIMULATIONS", "10000"))
    RANDOM_SEED = int(os.getenv("RANDOM_SEED", "42"))

    # 泊松模型
    LEAGUE_AVG_GOALS = 1.32          # 国家队比赛场均进球
    POISSON_K_MAX = 10               # 进球数截断上限
    HOME_ADVANTAGE = 1.15            # 东道主进球期望倍数

    # 球队评分维度权重 (必须和为 1.0)
    RATING_WEIGHTS = {
        "historical":      0.20,     # 历史底蕴
        "strength":        0.30,     # FIFA 排名 / 实力
        "attack_defense":  0.20,     # 攻防效率
        "player_quality":  0.15,     # 球员班底
        "recent_form":     0.15,     # 近期状态
    }

    # 淘汰赛三阶段
    EXTRA_TIME_LAMBDA_FACTOR = 0.33  # 加时赛进球率 (30min/90min)
    PENALTY_STRONG_TEAM_RATE = 0.55  # 强队点球胜率

    # 置信区间
    CI_METHOD = "wilson"             # Wilson score interval
    CI_ALPHA = 0.05                  # 95% 置信水平

    # 可解释性
    EXPLAIN_METHOD = "feature_ablation"
    EXPLAIN_MAX_FACTORS = 5
    EXPLAIN_CONTRIBUTION_THRESHOLD = 0.01


# =============================================================================
# 日志配置
# =============================================================================

class LogConfig:
    """日志配置"""

    LEVEL = os.getenv("LOG_LEVEL", "INFO")
    FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    FILE_PATH = Paths.DATA_LOGS / "app.log"


# =============================================================================
# 导出
# =============================================================================

paths = Paths()
backend = BackendConfig()
app_config = AppConfig()
prediction = PredictionConfig()
log_config = LogConfig()
