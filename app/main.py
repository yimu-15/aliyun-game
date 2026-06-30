"""
世界杯冠军预测 Agent — Streamlit 可视化前端

启动:
    streamlit run app/main.py
"""

import sys
import os
from pathlib import Path

# 确保项目根在 path 中
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

# ── 页面配置 ──
st.set_page_config(
    page_title="世界杯冠军预测 Agent",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS 样式 ──
st.markdown("""
<style>
    .main-title { font-size: 2.2rem; font-weight: 800; color: #1a1a2e; margin-bottom: 0.5rem; }
    .subtitle { font-size: 1.05rem; color: #555; margin-bottom: 1.5rem; }
    .champion-card { background: linear-gradient(135deg, #ffd700, #ffaa00); border-radius: 12px;
                     padding: 20px; text-align: center; color: #1a1a2e; }
    .champion-team { font-size: 2rem; font-weight: 800; }
    .champion-prob { font-size: 1.2rem; color: #333; }
    .metric-box { background: #f8f9fa; border-radius: 8px; padding: 15px; text-align: center;
                  border: 1px solid #e0e0e0; }
    .metric-value { font-size: 1.6rem; font-weight: 700; color: #1f77b4; }
    .metric-label { font-size: 0.85rem; color: #777; }
    .rating-bar { height: 8px; border-radius: 4px; margin: 2px 0; }
    .footer { text-align: center; color: #aaa; font-size: 0.8rem; margin-top: 30px; }
    .stButton>button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# ── 侧边栏 ──
with st.sidebar:
    st.image("https://img.icons8.com/color/96/football2--v1.png", width=60)
    st.markdown("## 🏆 世界杯预测")

    page = st.radio(
        "📋 导航菜单",
        ["🏠 首页概览", "📊 球队实力榜", "🌳 赛程对阵树",
         "🔍 比分预测", "📋 预测报告"],
        label_visibility="collapsed",
    )

    st.divider()

    # ── 可配置参数区 (10) ──
    st.markdown("### ⚙️ 参数配置")

    with st.expander("📐 模型参数", expanded=False):
        n_teams = st.selectbox("模拟球队数", [8, 16, 32, 40], index=2,
                                help="参与模拟的球队数量")
        n_sim = st.slider("蒙特卡洛模拟次数", 500, 20000, 5000, 500,
                          help="模拟次数越多结果越稳定")
        seed = st.number_input("随机种子", 0, 999, 42,
                               help="固定种子确保结果可复现")

    with st.expander("⚖️ 评分权重", expanded=False):
        w_hist = st.slider("历史底蕴", 0.0, 1.0, 0.20, 0.05)
        w_str = st.slider("FIFA 排名", 0.0, 1.0, 0.30, 0.05)
        w_ad = st.slider("攻防效率", 0.0, 1.0, 0.20, 0.05)
        w_pq = st.slider("球员班底", 0.0, 1.0, 0.15, 0.05)
        w_rf = st.slider("近期状态", 0.0, 1.0, 0.15, 0.05)
        total_w = w_hist + w_str + w_ad + w_pq + w_rf
        st.caption(f"权重合计: {total_w:.2f}" + (" ✓" if abs(total_w-1.0)<0.01 else " ⚠️ 建议和为1.0"))

    with st.expander("🏟️ 赛制设置", expanded=False):
        group_size = st.selectbox("每组球队数", [3, 4], index=1)
        advance_per_group = st.selectbox("每组出线数", [1, 2], index=1)
        host_advantage = st.checkbox("启用东道主优势", value=True)

    st.divider()
    st.caption(f"Model v2.0-mvp | 可解释预测 · 可视化赛程树")

# ── 缓存: 跑一次预测 ──
@st.cache_data(ttl=600, show_spinner="正在运行蒙特卡洛模拟...")
def run_prediction(n_teams, n_sim, seed_val, w_hist, w_str, w_ad, w_pq, w_rf,
                   group_size, advance_per_group, host_adv):
    """运行完整的预测流水线并返回 results + teams + bracket"""
    from models.team_rating import WEIGHTS as orig_weights
    import models.team_rating as tr

    # 临时替换权重
    orig = dict(tr.WEIGHTS)
    tr.WEIGHTS["historical"] = w_hist
    tr.WEIGHTS["strength"] = w_str
    tr.WEIGHTS["attack_defense"] = w_ad
    tr.WEIGHTS["player_quality"] = w_pq
    tr.WEIGHTS["recent_form"] = w_rf

    from utils.data_loader import load_teams, load_matches, build_team_snapshots
    from models.team_rating import rate_all_teams
    from models.champion import run_monte_carlo

    teams_df = load_teams(use_real_data=False)
    matches_df = load_matches(use_real_data=False)
    snaps = build_team_snapshots(teams_df, matches_df)[:n_teams]
    team_ratings = rate_all_teams(snaps)
    team_map = {t.team_id: t for t in team_ratings}

    # 构建分组
    team_ids = [t.team_id for t in team_ratings]
    n_groups = max(1, n_teams // group_size)
    groups = {}
    for g_idx in range(n_groups):
        g_name = chr(65 + g_idx)
        start = g_idx * group_size
        end = start + group_size
        groups[g_name] = team_ids[start:end] if end <= len(team_ids) else team_ids[start:]

    # 构建淘汰赛对阵
    bracket = _build_bracket(n_groups * advance_per_group)

    host_ids = ["CAN", "MEX", "USA"] if host_adv else []
    results = run_monte_carlo(team_ratings, groups, bracket, host_ids, n_sim=n_sim, seed=seed_val)

    # 恢复权重
    tr.WEIGHTS = orig

    return results, team_map, groups, team_ratings


def _build_bracket(n_teams: int) -> list:
    """根据出线球队数构建淘汰赛对阵"""
    bracket = []
    remaining = n_teams
    while remaining >= 2:
        matches = [(i, i + 1) for i in range(0, remaining, 2)]
        bracket.append(matches)
        remaining = len(matches)
    return bracket


# ── 运行预测 ──
host_adv = host_advantage
results, team_map, groups, team_ratings = run_prediction(
    n_teams, n_sim, seed, w_hist, w_str, w_ad, w_pq, w_rf,
    group_size, advance_per_group, host_adv,
)

# ── 页面路由 ──
if page == "🏠 首页概览":
    from app.pages.home import render
    render(results, team_map, team_ratings, groups, n_sim)

elif page == "📊 球队实力榜":
    from app.pages.analysis import render
    render(results, team_map, team_ratings, groups)

elif page == "🌳 赛程对阵树":
    from app.pages.bracket import render
    render(results, team_map, groups)

elif page == "🔍 比分预测":
    from app.pages.match_detail import render
    render(results, team_map, team_ratings)

elif page == "📋 预测报告":
    from app.pages.report import render
    render(results, team_map, team_ratings, groups, n_sim)

# ── 页脚 ──
st.markdown('<div class="footer">世界杯冠军预测 Agent v2.0-mvp | 可解释 · 可视化 · 全流程</div>',
            unsafe_allow_html=True)
