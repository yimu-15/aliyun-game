"""
预测报告页面 — 可下载报告 (9)
"""

import streamlit as st
from datetime import datetime
from io import StringIO
import base64


def render(results, team_map, team_ratings, groups, n_sim):
    if not results:
        st.info("数据加载中，请先在 Home 页面点击「🔄 获取最新数据 & 重新预测」")
        return
    st.markdown('<div class="section-title">📋 预测报告</div>', unsafe_allow_html=True)

    # ── 报告预览 ──
    st.subheader("📄 报告预览")

    report_md = _generate_report(results, team_map, team_ratings, groups, n_sim)

    with st.expander("📖 点击展开完整报告", expanded=True):
        st.markdown(report_md)

    # ── 9. 可下载按钮 ──
    st.markdown("---")
    st.subheader("📥 下载报告")

    col1, col2 = st.columns(2)

    with col1:
        # Markdown 下载
        md_bytes = report_md.encode("utf-8")
        b64_md = base64.b64encode(md_bytes).decode()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.markdown(
            f'<a href="data:text/markdown;base64,{b64_md}" '
            f'download="worldcup_prediction_{timestamp}.md">'
            f'<button style="background:#1f77b4;color:white;padding:10px 20px;'
            f'border:none;border-radius:8px;cursor:pointer;width:100%;">'
            f'📥 下载 Markdown 报告</button></a>',
            unsafe_allow_html=True,
        )

    with col2:
        # JSON 下载
        import json
        from models.output import format_champion_rankings
        json_data = format_champion_rankings(results)
        json_str = json.dumps(json_data, ensure_ascii=False, indent=2)
        b64_json = base64.b64encode(json_str.encode("utf-8")).decode()
        st.markdown(
            f'<a href="data:application/json;base64,{b64_json}" '
            f'download="worldcup_prediction_{timestamp}.json">'
            f'<button style="background:#2ca02c;color:white;padding:10px 20px;'
            f'border:none;border-radius:8px;cursor:pointer;width:100%;">'
            f'📊 下载 JSON 数据</button></a>',
            unsafe_allow_html=True,
        )

    # CSV 下载
    st.markdown("---")
    import pandas as pd
    csv_data = []
    for r in results:
        csv_data.append({
            "排名": results.index(r) + 1,
            "球队": r.team_name or r.team_id,
            "夺冠概率": f"{r.champion_prob:.4f}",
            "CI下界": f"{r.ci_low:.4f}",
            "CI上界": f"{r.ci_high:.4f}",
            "综合评分": f"{r.overall_rating:.1f}",
            "决赛概率": f"{r.final_prob:.4f}",
            "半决赛概率": f"{r.semi_prob:.4f}",
        })
    df_csv = pd.DataFrame(csv_data)
    csv_str = df_csv.to_csv(index=False)
    b64_csv = base64.b64encode(csv_str.encode("utf-8")).decode()
    st.markdown(
        f'<a href="data:text/csv;base64,{b64_csv}" '
        f'download="worldcup_rankings_{timestamp}.csv">'
        f'<button style="background:#ff7f0e;color:white;padding:10px 20px;'
        f'border:none;border-radius:8px;cursor:pointer;width:100%;">'
        f'📈 下载 CSV 排行榜</button></a>',
        unsafe_allow_html=True,
    )


def _generate_report(results, team_map, team_ratings, groups, n_sim) -> str:
    """生成 Markdown 格式预测报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# 世界杯冠军预测分析报告",
        f"",
        f"**生成时间:** {now}  ",
        f"**模拟次数:** {n_sim:,} 次蒙特卡洛模拟  ",
        f"**参赛球队:** {len(team_ratings)} 支  ",
        f"**小组数量:** {len(groups)} 组  ",
        f"",
        f"---",
        f"",
        f"## 一、夺冠概率排行榜 (Top-10)",
        f"",
        f"| 排名 | 球队 | 夺冠概率 | 95% 置信区间 | 综合评分 |",
        f"|------|------|----------|-------------|----------|",
    ]

    for i, r in enumerate(results[:10], 1):
        name = r.team_name or r.team_id
        lines.append(
            f"| {i} | {name} | {r.champion_prob:.1%} | "
            f"[{r.ci_low:.1%}, {r.ci_high:.1%}] | {r.overall_rating:.1f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 二、球队综合评分",
        "",
        "| 球队 | 综合 | 历史底蕴 | FIFA排名 | 攻防效率 | 球员班底 | 近期状态 |",
        "|------|------|----------|----------|----------|----------|----------|",
    ])

    sorted_teams = sorted(team_ratings, key=lambda t: t.overall, reverse=True)
    for t in sorted_teams[:10]:
        name = t.team_name or t.team_id
        lines.append(
            f"| {name} | {t.overall:.1f} | {t.historical:.0f} | {t.strength:.0f} | "
            f"{t.attack_defense:.0f} | {t.player_quality:.0f} | {t.recent_form:.0f} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## 三、小组赛分组情况",
        "",
    ])

    for g_name, team_ids in groups.items():
        names = []
        for tid in team_ids:
            t = team_map.get(tid)
            names.append((t.team_name or tid) if t else tid)
        lines.append(f"- **{g_name} 组:** {', '.join(names)}")

    lines.extend([
        "",
        "---",
        "",
        "## 四、方法论说明",
        "",
        "### 球队评分模型",
        "采用五维度加权评分模型:",
        "- **历史底蕴 (20%):** 世界杯历史成绩",
        "- **FIFA排名 (30%):** FIFA官方排名 + ELO评分",
        "- **攻防效率 (20%):** 近20场进球/失球率",
        "- **球员班底 (15%):** FIFA游戏球员评分",
        "- **近期状态 (15%):** 近10场胜率 + 动量修正",
        "",
        "### 预测模型",
        "- **小组赛:** 独立泊松分布模型",
        "- **淘汰赛:** 三阶段制胜 (90分钟 → 加时 → 点球)",
        "- **冠军预测:** 蒙特卡洛模拟 (N次独立采样)",
        "- **置信区间:** Wilson Score Interval (95%)",
        "",
        "---",
        "",
        f"*本报告由世界杯冠军预测 Agent 自动生成*",
    ])

    return "\n".join(lines)
