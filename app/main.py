"""
世界杯冠军预测 Agent — Streamlit 可视化前端 (分页面版)

启动:
    streamlit run app/main.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

# ── 页面配置 ──
st.set_page_config(
    page_title="世界杯冠军预测 Agent",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──
st.markdown("""
<style>
.stApp { background: linear-gradient(180deg, #0D1B2A 0%, #14273D 100%); }
.hero-section { background:linear-gradient(135deg,#0D1B2A,#1a3a5c); border-radius:16px;
    padding:1.5rem; margin-bottom:1rem; border:1px solid rgba(240,192,64,.3); }
.hero-title { font-size:2rem; font-weight:900; color:#F0C040; }
.hero-subtitle { font-size:.95rem; color:#A0B0C0; }
.champion-card { background:linear-gradient(135deg,#F0C040,#D4A020); border-radius:16px;
    padding:1.5rem; text-align:center; box-shadow:0 6px 24px rgba(240,192,64,.25); }
.champion-card .team { font-size:2rem; font-weight:900; color:#0D1B2A; }
.metric-box { background:rgba(20,39,61,.8); border-radius:12px; padding:1rem;
    text-align:center; border:1px solid rgba(240,192,64,.15); }
.metric-value { font-size:1.5rem; font-weight:800; color:#F0C040; }
.metric-label { font-size:.8rem; color:#8899AA; }
.section-title { font-size:1.3rem; font-weight:700; color:#F0C040;
    border-left:4px solid #F0C040; padding-left:.8rem; margin:1.2rem 0 .8rem 0; }
.app-footer { text-align:center; color:#556677; font-size:.75rem; margin-top:2rem;
    padding-top:1rem; border-top:1px solid rgba(240,192,64,.1); }
section[data-testid="stSidebar"] { background:linear-gradient(180deg,#0a1525,#0D1B2A);
    border-right:1px solid rgba(240,192,64,.1); }
.stButton>button { width:100%; background:linear-gradient(135deg,#1f77b4,#145a8c);
    color:white; border:none; border-radius:8px; font-weight:600; }
</style>
""", unsafe_allow_html=True)

# ── 侧边栏 ──
with st.sidebar:
    st.markdown("## 🏆 世界杯预测")
    page = st.radio("导航", ["🏠 Home","📊 球队实力榜","🌳 赛程对阵树","🔍 比分预测","📄 Report"],
                     label_visibility="collapsed")
    st.divider()

    with st.expander("📐 模型参数", expanded=False):
        n_teams = st.selectbox("模拟球队数", [8,16,32,40], index=2)
        n_sim = st.slider("蒙特卡洛模拟次数", 500, 20000, 5000, 500)
        seed = st.number_input("随机种子", 0, 999, 42)

    with st.expander("⚖️ 评分权重", expanded=False):
        w_hist = st.slider("历史底蕴", 0.0, 1.0, 0.20, 0.05)
        w_str  = st.slider("FIFA 排名", 0.0, 1.0, 0.30, 0.05)
        w_ad   = st.slider("攻防效率", 0.0, 1.0, 0.20, 0.05)
        w_pq   = st.slider("球员班底", 0.0, 1.0, 0.15, 0.05)
        w_rf   = st.slider("近期状态", 0.0, 1.0, 0.15, 0.05)
        total_w = w_hist + w_str + w_ad + w_pq + w_rf
        st.caption(f"权重合计: {total_w:.2f}" + (" ✓" if abs(total_w-1.0)<0.01 else " ⚠️"))

    with st.expander("🏟️ 赛制设置", expanded=False):
        group_size = st.selectbox("每组球队数", [3,4], index=1)
        advance_per_group = st.selectbox("每组出线数", [1,2], index=1)
        host_advantage = st.checkbox("启用东道主优势", value=True)

    st.divider()

    if st.button("🔄 获取最新数据 & 重新预测", type="primary", use_container_width=True):
        with st.spinner("正在采集数据..."):
            try:
                from data_collection.live_fetcher import fetch_all
                st.cache_data.clear()
                fetch_all(force=True)
                st.success("✅ 数据刷新完成! 点击页面刷新")
            except Exception as e:
                st.error(f"刷新失败: {e}")

    st.divider()
    import requests
    try:
        requests.get("http://localhost:8000/api/health", timeout=2)
        st.success("🟢 Backend API 在线")
    except Exception:
        st.warning("🟡 Backend API 离线 (预测仍可用)")
    st.caption("Model v2.0 | localhost:8501")


# ── 预测引擎 ──
@st.cache_data(ttl=600, show_spinner="正在运行蒙特卡洛模拟...")
def _do_prediction(n_teams, n_sim, seed_val, w_hist, w_str, w_ad, w_pq, w_rf,
                   group_size, advance_per_group, host_adv):
    from utils.data_loader import load_teams, load_matches, build_team_snapshots
    from models.team_rating import rate_all_teams, WEIGHTS
    from models.champion import run_monte_carlo
    import models.team_rating as tr

    orig = dict(tr.WEIGHTS)
    tr.WEIGHTS["historical"] = w_hist
    tr.WEIGHTS["strength"] = w_str
    tr.WEIGHTS["attack_defense"] = w_ad
    tr.WEIGHTS["player_quality"] = w_pq
    tr.WEIGHTS["recent_form"] = w_rf

    teams_df = load_teams(use_real_data=False)
    matches_df = load_matches(use_real_data=False)
    snaps = build_team_snapshots(teams_df, matches_df)[:n_teams]
    team_ratings = rate_all_teams(snaps)
    team_map = {t.team_id: t for t in team_ratings}

    team_ids = [t.team_id for t in team_ratings]
    n_groups = max(1, n_teams // group_size)
    groups = {}
    for g_idx in range(n_groups):
        g_name = chr(65 + g_idx)
        start = g_idx * group_size
        end = start + group_size
        groups[g_name] = team_ids[start:end] if end <= len(team_ids) else team_ids[start:]

    n_qual = n_groups * advance_per_group
    bracket = []
    remaining = n_qual
    while remaining >= 2:
        bracket.append([(i, i + 1) for i in range(0, remaining, 2)])
        remaining //= 2

    host_ids = ["CAN", "MEX", "USA"] if host_adv else []
    results = run_monte_carlo(team_ratings, groups, bracket, host_ids, n_sim=n_sim, seed=seed_val)
    tr.WEIGHTS = orig
    return results, team_map, groups, team_ratings


# ── 执行预测 (有错误保护，不会再白屏) ──
host_adv = host_advantage

try:
    results, team_map, groups, team_ratings = _do_prediction(
        n_teams, n_sim, seed, w_hist, w_str, w_ad, w_pq, w_rf,
        group_size, advance_per_group, host_adv,
    )
except Exception as e:
    st.error(f"预测引擎启动失败: {e}")
    st.info("请检查数据文件，或减少模拟次数")
    st.stop()


# ── 页面路由 ──
if page == "🏠 Home":
    from app.home import render
    render(results, team_map, team_ratings, groups, n_sim)

elif page == "📊 球队实力榜":
    from app.analysis import render
    render(results, team_map, team_ratings, groups)

elif page == "🌳 赛程对阵树":
    from app.bracket import render
    render(results, team_map, groups)

elif page == "🔍 比分预测":
    from app.match_detail import render
    render(results, team_map, team_ratings)

elif page == "📄 Report":
    from app.report import render
    render(results, team_map, team_ratings, groups, n_sim)

# ── 页脚 ──
st.markdown('<div class="app-footer">世界杯冠军预测 Agent v2.0 | 可解释 · 可视化 · 全流程 | localhost:8501</div>', unsafe_allow_html=True)
