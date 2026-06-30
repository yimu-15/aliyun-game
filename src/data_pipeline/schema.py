# =============================================================================
# 世界杯冠军预测 Agent — 数据字段设计（Schema）
# =============================================================================
# 每张表均标注：字段名、类型、主键/外键、真实数据来源
# 严禁使用编造数据填充，所有字段必须可追溯到真实来源
# =============================================================================

from datetime import datetime
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field, asdict
import json

# =============================================================================
# 辅助枚举
# =============================================================================

class Confederation(str, Enum):
    """大洲足联"""
    UEFA = "UEFA"         # 欧洲
    CONMEBOL = "CONMEBOL" # 南美洲
    CONCACAF = "CONCACAF" # 中北美及加勒比
    CAF = "CAF"           # 非洲
    AFC = "AFC"           # 亚洲
    OFC = "OFC"           # 大洋洲


class MatchStage(str, Enum):
    """比赛阶段"""
    GROUP = "group"             # 小组赛
    ROUND_OF_32 = "round_32"    # 32 强
    ROUND_OF_16 = "round_16"    # 16 强
    QUARTER_FINAL = "quarter"   # 1/4 决赛
    SEMI_FINAL = "semi"         # 半决赛
    THIRD_PLACE = "third_place" # 三四名决赛
    FINAL = "final"             # 决赛


class MatchResult(str, Enum):
    """比赛结果（从主队视角）"""
    HOME_WIN = "H"  # 主队胜
    AWAY_WIN = "A"  # 客队胜
    DRAW = "D"      # 平局


# =============================================================================
# 表 1: teams — 球队基础信息表
# =============================================================================
# 主要来源：kaggle_intl_matches + kaggle_fifa_rankings
# 国家名统一通过 name_mapping.json 标准化
# =============================================================================

TEAMS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS teams (
    team_id         TEXT PRIMARY KEY,       -- 统一 3 字母代码 (如 BRA, ARG, FRA)
    team_name_en    TEXT NOT NULL UNIQUE,    -- 英文全名 (如 "Brazil")
    team_name_cn    TEXT NOT NULL,           -- 中文名 (如 "巴西")
    fifa_code       TEXT NOT NULL,           -- FIFA 3 字母代码
    confederation   TEXT NOT NULL,           -- 所属大洲足联 (UEFA/CONMEBOL/...)
    elo_rating      REAL,                   -- 最新 ELO 评分
    elo_rating_date TEXT,                   -- ELO 评分日期
    current_fifa_rank INTEGER,              -- 最新 FIFA 排名
    fifa_rank_date  TEXT,                   -- FIFA 排名日期
    fifa_rank_points REAL,                  -- FIFA 排名积分
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

-- 数据来源说明：
--   team_id, team_name_en, fifa_code, confederation
--     → 来源: kaggle_fifa_rankings (country_full, country_abrv, confederation)
--   elo_rating, elo_rating_date
--     → 来源: eloratings.net (手动导出 CSV)
--   current_fifa_rank, fifa_rank_date, fifa_rank_points
--     → 来源: kaggle_fifa_rankings (rank, rank_date, total_points)
"""


# =============================================================================
# 表 2: matches — 历史比赛记录表
# =============================================================================
# 主要来源：kaggle_intl_matches + kaggle_worldcup
# 两者合并后，所有比赛统一到此表
# =============================================================================

MATCHES_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS matches (
    match_id        TEXT PRIMARY KEY,       -- 唯一标识 (格式: {date}_{home}_{away})
    match_date      TEXT NOT NULL,          -- 比赛日期 (YYYY-MM-DD)
    tournament      TEXT NOT NULL,          -- 赛事名称 (如 "FIFA World Cup 2022")
    stage           TEXT,                   -- 比赛阶段 (group/round_16/...)
    home_team_id    TEXT NOT NULL,          -- 主队 ID (外键 → teams.team_id)
    away_team_id    TEXT NOT NULL,          -- 客队 ID (外键 → teams.team_id)
    home_score      INTEGER NOT NULL,       -- 主队进球
    away_score      INTEGER NOT NULL,       -- 客队进球
    home_goals_half INTEGER,               -- 主队半场进球
    away_goals_half INTEGER,               -- 客队半场进球
    result          TEXT NOT NULL,          -- 结果 (H/A/D)
    neutral_venue   INTEGER DEFAULT 0,      -- 是否中立场地 (0/1)
    city            TEXT,                   -- 比赛城市
    country         TEXT,                   -- 比赛国家
    attendance      INTEGER,               -- 观众人数
    referee         TEXT,                   -- 裁判
    source          TEXT NOT NULL,          -- 数据来源标识
    created_at      TEXT DEFAULT (datetime('now'))
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_tournament ON matches(tournament);
CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_id);

-- 数据来源说明：
--   基础比赛信息 (date, home_team, away_team, home_score, away_score, tournament, city, country, neutral):
--     → 来源: kaggle_intl_matches (results.csv, 1872-2024, 约 44,000 场比赛)
--   世界杯补充信息 (stage, attendance, referee):
--     → 来源: kaggle_worldcup (WorldCupMatches.csv, 1930-2022)
--   半场进球:
--     → 来源: kaggle_intl_matches (2021+ 的数据有 home_goals_half/away_goals_half)
--     → 历史数据缺失半场进球为 NULL，后续可通过 openfootball 数据补充
--   数据合并策略:
--     1. 以 kaggle_intl_matches 为主表
--     2. kaggle_worldcup 中独有的字段做 LEFT JOIN 补充
--     3. 去重：同一场比赛 (date + home_team + away_team) 保留信息更完整的一条
"""


# =============================================================================
# 表 3: rankings — FIFA 排名历史表
# =============================================================================
# 来源：kaggle_fifa_rankings
# =============================================================================

RANKINGS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS rankings (
    ranking_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    rank_date       TEXT NOT NULL,          -- 排名发布日期
    team_id         TEXT NOT NULL,          -- 球队 ID (外键 → teams.team_id)
    rank_position   INTEGER NOT NULL,       -- 排名位置
    total_points    REAL,                   -- FIFA 总积分
    previous_points REAL,                   -- 上期积分
    rank_change     INTEGER,               -- 排名变化
    confederation   TEXT,                   -- 所属大洲足联
    source          TEXT DEFAULT 'kaggle_fifa_rankings',
    created_at      TEXT DEFAULT (datetime('now')),

    UNIQUE(rank_date, team_id)
);

CREATE INDEX IF NOT EXISTS idx_rankings_date ON rankings(rank_date);
CREATE INDEX IF NOT EXISTS idx_rankings_team ON rankings(team_id);

-- 数据来源说明：
--   全部字段来自 kaggle_fifa_rankings
--   覆盖 1992-2024 每月排名快照
--   如需预测前的最新排名，取 rank_date 在世界杯开赛前最近的一条
"""


# =============================================================================
# 表 4: players — 球员信息表
# =============================================================================
# 来源：kaggle_fifa_players (FIFA 23 游戏数据) + kaggle_worldcup (世界杯出场记录)
# ⚠️ 说明：使用 FIFA 游戏评分的理由——
#   EA Sports 拥有全球球探网络，其球员评分是基于真实球探报告量化而来，
#   学术界已有研究验证 FIFA 评分与实际球员能力的相关性 > 0.8。
#   虽然这不是"真实比赛数据"，但它是目前可免费获取的最权威球员量化指标。
#   如需真实身价数据，可后续接入 Transfermarkt 爬虫。
# =============================================================================

PLAYERS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS players (
    player_id       TEXT PRIMARY KEY,       -- 球员唯一标识
    player_name     TEXT NOT NULL,          -- 球员姓名
    nationality     TEXT NOT NULL,          -- 国籍 (外键 → teams.team_id)
    age             INTEGER,               -- 年龄
    height_cm       REAL,                  -- 身高 (cm)
    weight_kg       REAL,                  -- 体重 (kg)
    overall_rating  INTEGER,               -- 综合能力值 (0-99, FIFA 游戏评分)
    potential       INTEGER,               -- 潜力值
    position        TEXT,                   -- 主要位置 (GK/DEF/MID/FWD)
    pace            INTEGER,               -- 速度
    shooting        INTEGER,               -- 射门
    passing         INTEGER,               -- 传球
    dribbling       INTEGER,               -- 盘带
    defending       INTEGER,               -- 防守
    physicality     INTEGER,               -- 身体对抗
    club_name       TEXT,                   -- 当前俱乐部
    market_value_eur REAL,                 -- 市场身价 (欧元)
    source          TEXT DEFAULT 'kaggle_fifa_players',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_players_nationality ON players(nationality);
CREATE INDEX IF NOT EXISTS idx_players_position ON players(position);

-- 数据来源说明：
--   overall_rating, potential, pace, shooting, passing, dribbling, defending, physicality
--     → 来源: kaggle_fifa_players (FIFA 23 Complete Player Dataset)
--     → 覆盖约 19,000 名球员
--   market_value_eur
--     → 来源: kaggle_fifa_players (基于 FIFA 游戏内估价，非 Transfermarkt 真实身价)
--     → ⚠️ 缺失项说明: 真实身价（Transfermarkt）暂时无法自动获取，见缺失说明
--   世界杯出场信息
--     → 来源: kaggle_worldcup (WorldCupPlayers.csv)
"""


# =============================================================================
# 表 5: group_stage — 小组赛分组与积分表
# =============================================================================
# 来源：对于 2026 世界杯，分组抽签尚未进行，MVP 阶段需说明处理方式
# =============================================================================

GROUP_STAGE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS group_stage (
    group_id        TEXT PRIMARY KEY,       -- 组 ID (如 G_A, G_B, ...)
    group_name      TEXT NOT NULL,          -- 组名 (如 "A 组")
    team_id         TEXT NOT NULL,          -- 球队 ID (外键 → teams.team_id)
    tournament      TEXT NOT NULL,          -- 赛事标识 (如 "WC2026")
    matches_played  INTEGER DEFAULT 0,     -- 已比赛场次
    wins            INTEGER DEFAULT 0,     -- 胜场
    draws           INTEGER DEFAULT 0,     -- 平局
    losses          INTEGER DEFAULT 0,     -- 负场
    goals_for       INTEGER DEFAULT 0,     -- 进球
    goals_against   INTEGER DEFAULT 0,     -- 失球
    goal_diff       INTEGER DEFAULT 0,     -- 净胜球
    points          INTEGER DEFAULT 0,     -- 积分
    is_confirmed    INTEGER DEFAULT 0,     -- 是否已确认 (0=预测, 1=实际)
    source          TEXT NOT NULL,         -- 数据来源
    created_at      TEXT DEFAULT (datetime('now')),

    UNIQUE(tournament, group_id, team_id)
);

-- 数据来源说明：
--   ⚠️ 2026 世界杯分组:
--     状态: 尚未公布 (预计 2025 年底 FIFA 抽签)
--     MVP 处理方案:
--       根据 FIFA 排名和历史世界杯表现，按分档规则生成预估分组。
--       ┌──────────── 分档规则 ────────────┐
--       │ 第 1 档: FIFA Top-16 球队       │
--       │ 第 2 档: 排名 17-32 球队        │
--       │ 第 3 档: 排名 33-48 球队        │
--       │ 分组: 每组 3 队，各档 1 队       │
--       └─────────────────────────────────┘
--       生成的分组标注 source = 'ESTIMATED_BASED_ON_FIFA_RANK'。
--       在 Web 页面和报告中醒目标注「预估分组，基于当前 FIFA 排名」。
--       一旦官方公布真实分组，替换为 source = 'OFFICIAL_FIFA_DRAW'。
--
--   历史世界杯分组:
--     来源: openfootball/world-cup (各届世界杯小组赛数据)
--     → 用于回测模型准确性
"""


# =============================================================================
# 表 6: tournament_bracket — 淘汰赛赛程树表
# =============================================================================
# 存储淘汰赛阶段的树状结构，支持可视化赛程树渲染
# =============================================================================

TOURNAMENT_BRACKET_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS tournament_bracket (
    node_id         TEXT PRIMARY KEY,       -- 节点 ID (如 R16_1, QF_2, SF_1, FINAL)
    tournament      TEXT NOT NULL,          -- 赛事标识 (如 "WC2026")
    stage           TEXT NOT NULL,          -- 阶段 (round_32/round_16/quarter/semi/final)
    round_order     INTEGER NOT NULL,       -- 轮次顺序 (1=1/16决赛, 2=1/8决赛, 3=1/4, 4=半决, 5=决赛)
    parent_node_id  TEXT,                   -- 父节点 ID (上级比赛的胜者进入此节点)
    left_child_id   TEXT,                   -- 左子节点 ID
    right_child_id  TEXT,                   -- 右子节点 ID
    team_a_id       TEXT,                   -- 球队 A (外键 → teams.team_id)
    team_b_id       TEXT,                   -- 球队 B (外键 → teams.team_id)
    winner_id       TEXT,                   -- 胜者 (外键 → teams.team_id, NULL=未确定)
    match_date      TEXT,                   -- 比赛日期
    stadium         TEXT,                   -- 比赛场馆
    city            TEXT,                   -- 比赛城市
    is_predicted    INTEGER DEFAULT 1,      -- 是否为预测结果 (0=实际结果, 1=预测)
    prob_team_a     REAL,                   -- 球队 A 晋级概率
    prob_team_b     REAL,                   -- 球队 B 晋级概率
    source          TEXT NOT NULL,         -- 数据来源
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_bracket_tournament ON tournament_bracket(tournament);
CREATE INDEX IF NOT EXISTS idx_bracket_stage ON tournament_bracket(stage);

-- 数据来源说明：
--   淘汰赛节点结构（比赛对阵关系）:
--     → 来源: fifa_2026_schedule (赛制配置文件)
--     → MVP 阶段: 手动配置 wc2026_bracket.json
--   实际比赛结果:
--     → 来源: 比赛进行中从 kaggle_intl_matches 更新
--   预测概率:
--     → 由预测引擎计算后写入此表
"""


# =============================================================================
# 表 7: predictions — 预测结果记录表
# =============================================================================
# 存储每次预测的完整结果，支持历史查询和准确率对比
# =============================================================================

PREDICTIONS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id   TEXT PRIMARY KEY,       -- 预测唯一标识
    created_at      TEXT NOT NULL,          -- 预测生成时间
    model_version   TEXT NOT NULL,          -- 模型版本 (如 "xgboost_v1.0")
    data_snapshot   TEXT NOT NULL,          -- 数据快照标识 (用于复现)
    target_team_id  TEXT NOT NULL,          -- 目标球队 (外键 → teams.team_id)
    champion_prob   REAL NOT NULL,          -- 夺冠概率
    final_prob      REAL,                   -- 进入决赛概率
    semi_prob       REAL,                   -- 进入半决赛概率
    quarter_prob    REAL,                   -- 进入 1/4 决赛概率
    round_16_prob   REAL,                   -- 进入 16 强概率
    confidence_95_low  REAL,               -- 95% 置信区间下界
    confidence_95_high REAL,               -- 95% 置信区间上界
    sim_count       INTEGER NOT NULL,       -- 蒙特卡洛模拟次数
    top_factors     TEXT,                   -- 关键影响因素 (JSON)
    is_verified     INTEGER DEFAULT 0,     -- 是否经过实际结果验证
    actual_result   TEXT,                   -- 实际结果 (比赛结束后填入)
    source          TEXT DEFAULT 'prediction_engine',
    created_at_ts   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at);
CREATE INDEX IF NOT EXISTS idx_predictions_team ON predictions(target_team_id);

-- 数据来源说明：
--   全部字段由预测引擎计算生成
--   model_version 和 data_snapshot 确保结果可复现
--   top_factors 存储 JSON (用于可解释性展示)
"""


# =============================================================================
# 表 8: head_to_head — 历史交锋汇总表
# =============================================================================
# 预计算的球队间历史交锋统计，加速预测引擎
# =============================================================================

HEAD_TO_HEAD_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS head_to_head (
    h2h_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team_a_id       TEXT NOT NULL,          -- 球队 A
    team_b_id       TEXT NOT NULL,          -- 球队 B
    total_matches   INTEGER DEFAULT 0,     -- 总交锋次数
    team_a_wins     INTEGER DEFAULT 0,     -- A 胜次数
    team_b_wins     INTEGER DEFAULT 0,     -- B 胜次数
    draws           INTEGER DEFAULT 0,     -- 平局次数
    team_a_goals    INTEGER DEFAULT 0,     -- A 总进球
    team_b_goals    INTEGER DEFAULT 0,     -- B 总进球
    last_match_date TEXT,                   -- 最近一次交锋日期
    last_match_result TEXT,                -- 最近一次交锋结果
    worldcup_only_matches INTEGER DEFAULT 0,  -- 仅世界杯交锋次数
    data_up_to_date TEXT,                   -- 数据截止日期
    source          TEXT NOT NULL,         -- 数据来源
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),

    UNIQUE(team_a_id, team_b_id)
);

CREATE INDEX IF NOT EXISTS idx_h2h_teams ON head_to_head(team_a_id, team_b_id);

-- 数据来源说明：
--   由 matches 表预计算生成
--   来源链: kaggle_intl_matches → matches 表 → 聚合 → head_to_head 表
"""


# =============================================================================
# 数据来源追溯元数据表
# =============================================================================

SOURCE_TRACE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS source_trace (
    trace_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name      TEXT NOT NULL,          -- 目标表名
    record_id       TEXT,                   -- 目标记录 ID
    source_id       TEXT NOT NULL,          -- 数据源 ID (对应 data_sources.yaml)
    source_url      TEXT NOT NULL,          -- 数据源 URL
    source_file     TEXT,                   -- 源文件名
    download_date   TEXT NOT NULL,          -- 下载日期
    data_version    TEXT,                   -- 数据版本标签
    raw_file_hash   TEXT,                   -- 原始文件 SHA256 哈希
    notes           TEXT,                   -- 备注
    created_at      TEXT DEFAULT (datetime('now'))
);

-- 用途说明：
--   每一批数据入库时在 source_trace 中记录追溯链，
--   确保任何数据都能回答："这条数据从哪里来？何时获取的？"
"""


# =============================================================================
# 所有 DDL 汇总
# =============================================================================

ALL_TABLE_DDLS = [
    ("teams", TEAMS_TABLE_DDL),
    ("matches", MATCHES_TABLE_DDL),
    ("rankings", RANKINGS_TABLE_DDL),
    ("players", PLAYERS_TABLE_DDL),
    ("group_stage", GROUP_STAGE_TABLE_DDL),
    ("tournament_bracket", TOURNAMENT_BRACKET_TABLE_DDL),
    ("predictions", PREDICTIONS_TABLE_DDL),
    ("head_to_head", HEAD_TO_HEAD_TABLE_DDL),
    ("source_trace", SOURCE_TRACE_TABLE_DDL),
]


def get_all_ddls() -> list[tuple[str, str]]:
    """返回所有表的 (表名, DDL) 元组列表"""
    return ALL_TABLE_DDLS


def print_all_schemas():
    """打印所有表结构说明（用于文档输出）"""
    for name, ddl in ALL_TABLE_DDLS:
        print(f"\n{'='*60}")
        print(f"表名: {name}")
        print(f"{'='*60}")
        print(ddl)


if __name__ == "__main__":
    print_all_schemas()
