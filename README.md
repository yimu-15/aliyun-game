# 世界杯冠军预测 Agent

可解释、可视化、全流程自动化的世界杯冠军预测智能体。

## 核心亮点

- **可解释预测** — 每场比赛的预测结果附带 5 个维度的胜负因子归因分析
- **可视化赛程树** — 从小组赛到冠军的完整交互式赛程树
- **全流程自动** — 数据采集 → 特征工程 → 蒙特卡洛模拟 → 报告生成

## 项目结构

```
worldcup-predictor/
├── config/                 # 配置文件
│   ├── settings.py         #   全局配置 (路径/参数/权重)
│   ├── data_sources.yaml   #   真实数据源注册表
│   └── prediction_model_design.yaml  # 模型设计文档
├── data/                   # 数据文件
│   ├── raw/                #   原始数据 (下载后)
│   ├── processed/          #   清洗后的数据
│   ├── external/           #   外部数据集
│   ├── metadata/           #   元数据与报告
│   └── logs/               #   运行日志
├── models/                 # 预测模型
│   ├── team_rating.py      #   五维度球队评分引擎
│   ├── match_predictor.py  #   泊松单场预测器
│   ├── tournament_sim.py   #   赛程推演 + 蒙特卡洛模拟
│   └── explainer.py        #   因子归因可解释性引擎
├── backend/                # FastAPI 后端服务
│   ├── main.py             #   入口
│   ├── api/                #   API 路由
│   └── services/           #   业务逻辑
├── app/                    # Streamlit 前端
│   ├── main.py             #   入口 (4 页面)
│   ├── pages/              #   页面模块
│   └── components/         #   可复用组件
├── utils/                  # 工具函数
│   ├── logger.py           #   日志配置
│   ├── data_loader.py      #   数据加载
│   └── helpers.py          #   通用辅助函数
├── scripts/                # CLI 脚本
│   ├── fetch_data.py       #   数据下载
│   ├── run_pipeline.py     #   数据处理流水线
│   ├── train_model.py      #   模型训练 (v1.1)
│   └── run_demo.py         #   快速演示 (无需数据)
├── docs/                   # 文档与 PPT 材料
├── tests/                  # 单元测试
├── pyproject.toml          # 项目配置与依赖
├── requirements.txt        # pip 依赖清单 (Streamlit Cloud 用)
├── streamlit_app.py        # Streamlit Cloud 入口文件
├── .streamlit/config.toml  # Streamlit 主题配置
├── .env.example            # 环境变量模板
├── Dockerfile              # Docker 构建文件
├── docker-compose.yml      # Docker 编排
└── README.md               # 本文件
```

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
cd D:/aliyun-game

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -e .
```

### 2. 快速演示 (无需下载数据)

```bash
python scripts/run_demo.py
```

### 3. 下载真实数据

```bash
python scripts/fetch_data.py
python scripts/run_pipeline.py
```

### 4. 启动服务

```bash
# 启动 Streamlit 前端 (推荐)
streamlit run app/main.py

# 启动 FastAPI 后端
python backend/main.py
```

### 5. 访问

- 前端: http://football-games:8501
- 后端 API: http://football-games:8000/docs

> **首次使用需配置域名:** 以管理员身份运行 PowerShell 执行:
> ```powershell
> Add-Content -Path "$env:SystemRoot\System32\drivers\etc\hosts" -Value "`n127.0.0.1 football-games" -Force
> ```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Streamlit + Plotly |
| 后端 | FastAPI |
| 模型 | 泊松模型 + 蒙特卡洛模拟 |
| 可解释性 | 单项特征消融 (Feature Ablation) |
| 数据 | Pandas + KaggleHub |
| 部署 | Docker (计划中) |

## 预测模型说明

### 球队评分 (5 维度加权)

| 维度 | 权重 | 数据来源 |
|------|------|----------|
| 历史底蕴 | 20% | 世界杯历史成绩 |
| FIFA 排名 | 30% | FIFA 官方排名 + ELO |
| 攻防效率 | 20% | 近 20 场进球/失球 |
| 球员班底 | 15% | FIFA 23 游戏评分 |
| 近期状态 | 15% | 近 10 场胜率 + 动量 |

### 预测流程

1. **球队评分** → 0-100 综合评分
2. **泊松预测** → P(胜)/P(平)/P(负) + 期望进球
3. **赛程推演** → 小组赛 + 淘汰赛 (三阶段制胜)
4. **蒙特卡洛** → N=10000 次模拟 → 夺冠概率 + 95% CI
5. **因子归因** → 单特征消融 → Top-5 胜负因子

## 数据源

所有数据来自真实公开来源:

- [Kaggle - International Football Results (1872-2024)](https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017)
- [Kaggle - FIFA World Cup Dataset](https://www.kaggle.com/datasets/abecklas/fifa-world-cup)
- [Kaggle - FIFA World Rankings](https://www.kaggle.com/datasets/cashncarry/fifaworldranking)
- [Kaggle - FIFA 23 Player Dataset](https://www.kaggle.com/datasets/stefanoleone992/fifa-23-complete-player-dataset)
- [openfootball/world-cup (GitHub)](https://github.com/openfootball/world-cup)
- [eloratings.net](https://www.eloratings.net/)

## Streamlit Cloud 部署

### 前提条件
1. 代码已推送到 GitHub 公开仓库
2. GitHub 仓库根目录有 `streamlit_app.py` 和 `requirements.txt`

### 部署步骤

```bash
# 1. 确保 GitHub 仓库连接正确
git remote -v
# → origin  https://github.com/YIMU-15/world-cup-prediction-agent.git

# 2. 提交所有文件
git add .
git commit -m "chore: 添加 Streamlit Cloud 部署配置"
git push origin main

# 3. 打开 https://share.streamlit.io
# 4. 点击 "New app" → 选择仓库 → 入口文件: streamlit_app.py
# 5. 点击 "Deploy!"
```

### 注意事项
- 项目不依赖外部 API，使用内置参考数据，无需配置 secrets
- `.streamlit/config.toml` 已配置深色科技主题
- 首次加载需 1-2 分钟 (安装依赖)

## License

MIT
