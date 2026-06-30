"""
赛程对阵树组件 — 使用 Plotly 绘制淘汰赛对阵图

支持交互:
  - 悬停显示详细信息 (球队名、晋级概率)
  - 点击高亮路径
  - 可展开/折叠
"""

from typing import List, Dict, Optional
import plotly.graph_objects as go
import streamlit as st


def render_bracket_tree(
    results: list,
    team_map: Dict,
    groups: Dict,
    title: str = "淘汰赛对阵树",
) -> None:
    """
    渲染交互式淘汰赛对阵树。

    Args:
        results: ChampionResult 列表 (按夺冠概率排序)
        team_map: {team_id: TeamRating}
        groups: 分组信息
        title: 图表标题
    """
    if not results or len(results) < 4:
        st.warning("至少需要 4 支球队才能展示对阵树")
        return

    # 取 Top 球队模拟对阵
    top_n = min(len(results), 16)
    top_teams = []
    for r in results[:top_n]:
        name = r.team_name or r.team_id
        prob = r.champion_prob if hasattr(r, 'champion_prob') else 0.0
        top_teams.append({"id": r.team_id, "name": name, "prob": prob})

    # 构建淘汰赛树
    n_rounds = _calc_rounds(len(top_teams))
    fig = _build_plotly_bracket(top_teams, n_rounds, team_map)

    st.plotly_chart(fig, use_container_width=True, config={
        'displayModeBar': True,
        'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
    })

    # ── 图例 ──
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown("🟦 **高概率晋级** (>60%)")
    c2.markdown("🟩 **中等概率** (40-60%)")
    c3.markdown("🟨 **较低概率** (<40%)")
    c4.markdown("⬜ **未确定**")


def _calc_rounds(n_teams: int) -> int:
    """计算需要的淘汰赛轮数"""
    rounds = 0
    t = n_teams
    while t >= 2:
        rounds += 1
        t //= 2
    return max(rounds, 2)


def _build_plotly_bracket(teams: List[dict], n_rounds: int, team_map: Dict) -> go.Figure:
    """
    使用 Plotly 构建淘汰赛对阵树。

    布局:
      - 每轮是一个垂直列
      - 每场比赛是两个水平排列的节点
      - 连线表示晋级路径
    """
    fig = go.Figure()

    # 颜色映射 (基于晋级概率)
    def prob_color(p: float) -> str:
        if p > 0.15:
            return "#1f77b4"  # 深蓝 (高)
        elif p > 0.08:
            return "#4ecdc4"  # 青绿 (中)
        elif p > 0.03:
            return "#ffe66d"  # 黄 (较低)
        return "#e0e0e0"       # 灰 (低)

    # 从 16 强开始构建 (取最近的 2 的幂)
    n_start = 2
    while n_start < len(teams):
        n_start *= 2
    n_start = min(n_start, 16)

    # 构建每轮的节点
    current_teams = teams[:n_start]
    rounds_data = [current_teams]

    while len(current_teams) > 1:
        next_round = []
        for i in range(0, len(current_teams), 2):
            if i + 1 < len(current_teams):
                a = current_teams[i]
                b = current_teams[i + 1]
                prob_a = a.get("prob", 0)
                prob_b = b.get("prob", 0)
                total = prob_a + prob_b
                if total > 0:
                    winner = a if prob_a >= prob_b else b
                else:
                    winner = a
                next_round.append(winner)
            else:
                next_round.append(current_teams[i])
        rounds_data.append(next_round)
        current_teams = next_round

    # 绘制节点和连线
    round_names = ["16强", "8强", "半决赛", "决赛", "冠军"][-len(rounds_data):]
    if len(round_names) < len(rounds_data):
        round_names = [f"R{i+1}" for i in range(len(rounds_data))]

    y_offset = 0
    node_y_positions = []

    for round_idx, round_teams in enumerate(rounds_data):
        x = round_idx * 1.2
        n = len(round_teams)
        y_positions = []
        spacing = max(1.0, 4.0 / n)

        for i, team in enumerate(round_teams):
            y = y_offset + (n - 1 - i) * spacing
            y_positions.append(y)
            name = team.get("name", team.get("id", "?"))
            prob = team.get("prob", 0)
            color = prob_color(prob)

            # 节点
            fig.add_trace(go.Scatter(
                x=[x], y=[y],
                mode="markers+text",
                marker=dict(size=max(20, min(40, prob * 200 + 15)),
                            color=color, line=dict(color="white", width=2)),
                text=name[:6],
                textposition="middle right" if round_idx < len(rounds_data) - 1 else "middle center",
                textfont=dict(size=10, color="#333"),
                hovertemplate=f"<b>{name}</b><br>夺冠概率: {prob:.1%}<extra></extra>",
                showlegend=False,
            ))

            # 连线到上一轮
            if round_idx > 0:
                prev_y = None
                prev_data = rounds_data[round_idx - 1]
                for j, prev_team in enumerate(prev_data):
                    if prev_team["id"] == team["id"]:
                        prev_y = y_offset + (len(prev_data) - 1 - j) * max(1.0, 4.0 / len(prev_data))
                        break

                if prev_y is not None:
                    fig.add_trace(go.Scatter(
                        x=[x - 1.2, x], y=[prev_y, y],
                        mode="lines",
                        line=dict(color="#ccc", width=2),
                        hoverinfo="skip",
                        showlegend=False,
                    ))

        node_y_positions.append(y_positions)

    # 标题和轴
    fig.update_layout(
        title=dict(text="🏆 淘汰赛对阵树", font=dict(size=16), x=0.5),
        height=max(400, n_start * 30 + 100),
        xaxis=dict(
            tickvals=[i * 1.2 for i in range(len(rounds_data))],
            ticktext=round_names,
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=80, r=60, t=40, b=30),
        plot_bgcolor="white",
        hovermode="closest",
    )

    return fig


def render_simple_bracket_html(teams: List[dict], n_rounds: int = 4) -> str:
    """
    使用 HTML 渲染简化版对阵树 (备选方案)。
    用于在 Streamlit 中嵌入静态展示。
    """
    if len(teams) < 4:
        return "<p>至少需要 4 支球队</p>"

    html = '<div style="font-family:monospace;font-size:12px;line-height:1.6;overflow-x:auto;">'
    html += '<pre style="background:#1a1a2e;color:#e0e0e0;padding:20px;border-radius:10px;">'

    lines = []
    if len(teams) >= 4:
        lines.append("                    ┌────────────┐")
        lines.append(f"                    │  🏆 {teams[0]['name'][:6]:>6} │")
        lines.append("                    └─────┬──────┘")
        lines.append("              ┌───────────┴───────────┐")
        lines.append("        ┌─────┴─────┐           ┌─────┴─────┐")
        if len(teams) >= 2:
            lines.append(f"        │ {teams[0]['name'][:6]:>6}  │           │ {teams[1]['name'][:6]:>6}  │")
        else:
            lines.append(f"        │ {teams[0]['name'][:6]:>6}  │           │    ?     │")
        lines.append("        └─────┬─────┘           └─────┬─────┘")
        lines.append("     ┌───────┴───────┐       ┌───────┴───────┐")
        if len(teams) >= 4:
            lines.append(f"  ┌──┴──┐        ┌──┴──┐  ┌──┴──┐        ┌──┴──┐")
            lines.append(f"  │{teams[0]['name'][:4]:>4}│        │{teams[1]['name'][:4]:>4}│  │{teams[2]['name'][:4]:>4}│        │{teams[3]['name'][:4]:>4}│")
        lines.append("  └─────┘        └─────┘  └─────┘        └─────┘")

    html += "\n".join(lines)
    html += "</pre></div>"
    return html
