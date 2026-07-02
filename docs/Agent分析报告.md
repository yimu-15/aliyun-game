# 世界杯冠军预测 Agent — 项目分析报告

## 项目概述

世界杯冠军预测 Agent 是一个基于真实数据、可解释AI和交互式可视化的智能预测系统。通过五维度球队评分、泊松单场预测和蒙特卡洛模拟，实现从小组赛到冠军的完整推演。

## 核心能力

| 能力 | 说明 |
|------|------|
| **可解释预测** | 每场预测拆解为5维度因子归因，用户理解"为什么赢" |
| **可视化赛程树** | 交互式对阵图，从32强到冠军完整晋级路径 |
| **真实数据驱动** | Football-Data API + FIFA官网抓取 + Kaggle数据集 |
| **蒙特卡洛可靠性** | 10000次模拟 + Wilson 95%置信区间 |
| **全流程自动化** | 数据采集→预测引擎→可视化→报告下载 |

## 技术架构

```
用户交互层:  Streamlit (前端) + FastAPI (后端API)
应用服务层:  五维度评分 + 泊松预测 + 蒙特卡洛模拟 + 因子归因
数据层:     Football-Data API + FIFA抓取 + Kaggle数据集
```

## 项目结构

```
├── app/                    # Streamlit 前端
│   ├── main.py             #   入口 + 侧边栏路由
│   ├── home.py             #   Home 页
│   ├── analysis.py         #   球队实力分析
│   ├── bracket.py          #   淘汰赛对阵树
│   ├── match_detail.py     #   单场比分预测
│   ├── report.py           #   预测报告
│   └── components/         #   可复用组件
├── backend/                # FastAPI 后端
│   ├── main.py             #   服务入口
│   ├── api/prediction.py   #   预测API (含数据刷新)
│   └── services/           #   业务逻辑
├── models/                 # 预测模型
│   ├── team_rating.py      #   五维度球队评分
│   ├── group_stage.py      #   泊松单场预测 + 小组赛
│   ├── knockout.py         #   淘汰赛三阶段制胜
│   ├── champion.py         #   蒙特卡洛冠军预测
│   └── output.py           #   结构化输出
├── data_collection/        # 实时数据采集
│   └── live_fetcher.py     #   Football-Data API + FIFA抓取
├── utils/                  # 工具
│   └── data_loader.py      #   数据加载
├── config/settings.py      # 全局配置
├── data/                   # 数据文件
├── docs/                   # 文档 + PPT + 素材
├── streamlit_app.py        # Streamlit Cloud 入口
├── requirements.txt        # 依赖清单
├── Dockerfile              # Docker 构建
└── docker-compose.yml      # Docker 编排
```

## 预测模型

**Layer 0: 五维度球队评分**
- 历史底蕴 (20%) — 世界杯冠军/亚军/四强次数
- FIFA排名 (30%) — FIFA排名 + ELO加权
- 攻防效率 (20%) — 近20场进球/失球率
- 球员班底 (15%) — FIFA游戏球员评分
- 近期状态 (15%) — 近10场胜率 + 动量修正

**Layer 1: 泊松单场预测**
λ = 1.32 × 攻击力(A) × 防守力(B) × 东道主加成

**Layer 2: 赛程推演**
小组赛(泊松采样→积分榜→出线) + 淘汰赛(90min→加时×0.33→点球55%)

**Layer 3: 蒙特卡洛聚合**
N次模拟 → 夺冠概率 + Wilson 95% CI

## 启动方式

```bash
conda activate aliyun-game
cd D:/aliyun-game

# 前端
streamlit run app/main.py

# 后端
python backend/main.py
```

## 技术栈

Python 3.10+ | Streamlit | FastAPI | Pandas | NumPy | SciPy | Plotly

---

> 版本: v2.0 | 2026
