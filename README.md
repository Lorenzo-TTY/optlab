# OptLab 工程多目标优化工具

OptLab 是一个本地单用户的工程多目标优化工作台。它面向“真实工程目标函数评估昂贵、目标维度和参数维度由用户决定”的场景，提供两类使用方式：

- 交互式 ask/tell 工作流：用户可以自由录入任意数量的参数/目标数据行；算法建议只是可选参考，用户可在需要时请求下一批候选参数，也可以完全按自己的实验计划补充数据。
- 自动评估工作流：内置函数、本地 Python 插件或 HTTP 服务自动返回目标值，后端 worker 在预算内运行优化并持续输出 Pareto 结果。

当前版本是 v1，本地可信环境优先，不包含多租户、登录、插件沙箱、权限审计或分布式队列。

## 核心能力

- 支持 1-30 维参数变量，1-6 维优化目标。
- 支持变量类型：`float`、`int`、`categorical`、`bool`。
- 支持目标方向：`min` 和 `max`，内部统一转换为最小化。
- 支持约束模型：不等式、等式、硬约束、软约束。
- 支持三类工程目标函数接入：内置 benchmark、本地 Python 插件、HTTP JSON 服务。
- 支持交互式手工评估：用户先定义参数空间和目标空间维度，然后可手工录入参数与目标数据集；算法建议可选、可编辑，不强制作为下一次实验输入。
- 支持本地优化项目管理：在侧边栏新建、重命名、保存和切换项目，并在下次打开同一浏览器时恢复最后使用的项目。
- 支持实时目标空间可视化：2D scatter、3D scatter、4-6 目标 parallel coordinates、best-per-objective、Pareto preview、coverage min。
- 支持 Result Summary：从已保存 observations 或后端 archive 汇总 Pareto 前沿、目标覆盖和每个目标的当前最优值。
- 支持导出自动评估任务结果：CSV 和 JSON。
- 支持 Notebook SDK 示例。
- 支持后端测试、前端测试、Notebook 示例测试。

## 当前算法策略

OptLab v1 区分自动评估和人工/工程闭环评估。

自动评估任务：

- `n_obj == 1`：单目标 GA 或 random baseline。
- `2 <= n_obj <= 3`：NSGA-II。
- `4 <= n_obj <= 6`：NSGA-III。
- `4 <= n_obj <= 6`：可显式选择 RVEA，作为 many-objective 替代方案。

交互式 ask/tell 任务：

- 初期观测不足时使用 `sobol-lhs-maximin` 初始设计，综合 Sobol、Latin hypercube 和 maximin 候选筛选，覆盖归一化参数空间。
- 观测数量达到初始设计阈值后，使用 `ensemble-MOBO`，采用 qLogNParEGO-style Chebyshev scalarization，并结合 Gaussian Process、Random Forest、Neural Network surrogate 的集成预测、uncertainty scoring 和 diversity scoring 从候选池中选择下一组参数。
- advisor 只读取已保存的 observations。用户可以保存手工数据后再请求建议，也可以先请求建议、修改候选参数、补充目标值后再保存；未保存的数据不会进入 advisor。
- 当前实现是轻量本地 v1，运行时依赖 `scikit-learn`，不依赖 PyTorch/BoTorch。策略对齐 MOBO、ParEGO 和 qLogNParEGO 思路，但不声明等价于完整 BoTorch acquisition optimization。后续推荐以可选依赖方式加入 BoTorch `qLogNEHVI` / `qLogNParEGO`，用于昂贵、噪声、多目标工程评估。

详细算法依据见 [docs/algorithm-policy.md](docs/algorithm-policy.md)。

## 可视化策略

目标维度不同，首选可视化不同：

- 2 个目标：二维散点图作为主视图。
- 3 个目标：三维散点图作为主视图，parallel coordinates 作为辅助。
- 4-6 个目标：parallel coordinates 作为主视图，并通过 Result Summary 展示 best-per-objective、Pareto preview、Pareto count 和 coverage min。

高维可视化不直接强行投影成一个“看似简单”的二维图，而是把每个目标作为一条坐标轴展示，这样能同时观察候选解在所有目标上的折中关系。低维目标仍沿用同一套候选数据结构，所以 2D、3D 和高维场景可以自然切换。

## 项目结构

```text
D:\mltest
+-- backend
|   +-- pyproject.toml
|   +-- src\optlab
|   |   +-- api              # FastAPI 应用和 HTTP/WebSocket 入口
|   |   +-- core             # 数据模型、编码、Pareto archive、metrics、runner、advisor
|   |   +-- evaluators       # builtin/python/http 目标函数适配器
|   |   +-- services         # worker、SQLite store、任务管理
|   |   +-- sdk.py           # Notebook 友好 API
|   +-- tests
+-- frontend
|   +-- package.json
|   +-- src
|       +-- App.tsx
|       +-- api.ts
|       +-- components
|       +-- styles.css
+-- notebooks
|   +-- sdk_examples.py
|   +-- test_sdk_helpers.py
+-- docs
|   +-- api-contract.md
|   +-- algorithm-policy.md
+-- README.md
```

## 环境要求

推荐环境：

- Windows + PowerShell。
- Python 3.10-3.12。
- Node.js 20 或更新版本。
- npm。

后端依赖：

- FastAPI
- Pydantic v2
- NumPy
- pymoo
- scikit-learn
- httpx
- uvicorn
- pytest

前端依赖：

- React
- TypeScript
- Vite
- Plotly
- Vitest
- Testing Library

## 安装

### 1. 后端

在 PowerShell 中进入项目根目录：

```powershell
cd D:\mltest
```

如果已经存在 `backend\.venv`，可以直接使用它。若需要重建后端环境：

```powershell
cd D:\mltest\backend
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

如果本机没有 `py -3.11`，可换成可用的 Python 3.10-3.12 解释器。

### 2. 前端

```powershell
cd D:\mltest\frontend
npm install
```

## 启动本地服务

需要两个终端窗口。

### 终端 1：启动后端

```powershell
cd D:\mltest\backend
.\.venv\Scripts\python.exe -m uvicorn optlab.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

后端地址：

```text
http://127.0.0.1:8000
```

### 终端 2：启动前端

```powershell
cd D:\mltest\frontend
npm run dev
```

前端地址：

```text
http://127.0.0.1:5173
```

Vite 已配置代理：

- `/api` 转发到 `http://127.0.0.1:8000`
- `/ws` 转发到后端 WebSocket

## UI 使用流程

### 0. 新建或切换优化项目

左侧 `Projects` 侧边栏用于管理本地优化工作：

- `New project`：创建一个新的优化项目。
- `Project name`：重命名当前项目。
- `Save project`：显式保存当前项目。
- 项目列表：切换到已有项目，并显示每个项目的已保存 observations 数量和仍可编辑行数。

项目会自动保存到当前浏览器的 `localStorage`，包括问题定义、草稿行、advisor 建议行、已保存 observations、advisor 状态和更新时间。Result Summary、Pareto preview、best-per-objective 和 coverage min 会从已保存 observations 实时重算，不作为独立权威数据保存。

### 1. 输入参数空间和目标空间维度

在页面顶部的 `Problem Setup` 区域输入：

- `Parameter dimensions`：参数变量维度，范围 1-30。
- `Objective dimensions`：目标函数维度，范围 1-6。
- `Batch size`：每次请求算法建议的候选数量。
- `Seed`：随机种子，用于复现实验序列。

维度改变后，下面的参数定义表和目标定义表会自动增删行，并尽量保留已有行配置。

### 2. 定义参数变量表

每个参数变量一行，主要字段：

- `Name`：变量名，例如 `x1`、`temperature`、`pressure`。
- `Type`：变量类型，支持 `float`、`int`、`bool`、`categorical`。
- `Lower`：数值变量下界。
- `Upper`：数值变量上界。
- `Scale`：`linear` 或 `log`。

当前 UI 已覆盖数值型主流程。`categorical` 和 `bool` 在后端编码层支持，但 v1 对离散变量只承诺合法性和 smoke 级运行，不承诺与连续变量相同的收敛质量。

### 3. 定义目标函数表

每个目标函数一行，主要字段：

- `Name`：目标名，例如 `cost`、`efficiency`、`stress`。
- `Direction`：`min` 或 `max`。
- `Unit`：目标单位，可选。
- `Threshold`：工程阈值，可选。

最大化目标在后端内部转换为最小化，即内部使用 `-value` 进行统一优化。

### 4. 录入或导入实验数据行

在 `Ask / Tell Workbench` 中可以直接添加数据行：

```text
Add manual rows
```

每一行包含完整的参数变量列和目标函数列。用户可以一次添加 1 行，也可以把 `Rows to add` 改成更大的数值后批量添加。只要某一行参数值和目标值都合法，状态会变为 `complete`。

手工行示例：

```text
candidateId: manual_000001
x1: 0.20
x2: 0.80
f1: 0.12
f2: 0.88
```

点击：

```text
Save completed rows
```

前端会把所有 `complete` 行保存为 observations。保存只做数据入库到当前会话，不会自动请求下一组算法建议。用户可以继续添加更多手工数据行，数据组数不受 UI 限制。

### 5. 按需获取算法建议

点击：

```text
Get optional algorithm suggestion
```

后端 `/api/advisor/suggest` 会返回候选参数，例如：

```json
{
  "candidateId": "suggest_000001",
  "variables": {
    "x1": 0.5246543474,
    "x2": 0.7125514693
  },
  "reason": "Sobol/LHS/maximin initial design covers the encoded parameter space."
}
```

这些变量值只是算法参考，不是强制输入。用户可以直接保存它，也可以修改其中的参数值，或完全忽略建议并继续录入自己的实验数据。

### 6. 回填工程目标值

用户根据真实仿真、实验、工程计算或外部系统评估这组参数，并在 `Ask / Tell Workbench` 表中填写目标值。

示例：

```text
candidateId: suggest_000001
x1: 0.52465
x2: 0.71255
f1: 0.12
f2: 0.88
```

当某一行所有目标值都填写为合法数字后，行状态变为 `complete`。

### 7. 保存后再决定是否继续请求建议

点击：

```text
Save completed rows
```

前端会把已完成行转换为 observation，并实时更新可视化。之后用户可以继续手工补充数据，也可以再次点击 `Get optional algorithm suggestion`，让后端根据全部已保存观测建议下一批候选参数。

## 后端核心概念

### ProblemSpec

完整问题定义，包括：

- `variables`
- `objectives`
- `constraints`
- `evaluator`
- `budget`
- `algorithm`

后端模型定义在：

```text
backend\src\optlab\core\models.py
```

### EvaluatorAdapter

目标函数适配器，把不同来源的工程目标函数统一成同一种返回格式。

统一返回：

```json
{
  "objectives": { "obj_name": 1.23 },
  "constraints": { "constraint_name": -0.5 },
  "metadata": {}
}
```

### AlgorithmRunner

自动评估模式的优化执行器：

```text
backend\src\optlab\core\runner.py
```

它负责：

- 选择算法。
- 生成候选变量。
- 调用 evaluator。
- 更新 Pareto archive。
- 计算 metrics。
- 发送 worker event。

### Advisor

交互式 ask/tell 模式的候选建议器：

```text
backend\src\optlab\core\advisor.py
```

它是无状态的：每次请求都携带完整问题定义和观测历史，因此容易复现、测试和恢复。

### ParetoArchive

Pareto archive 是 UI、导出和最终结果的权威来源。rank-0 解必须互不支配。

```text
backend\src\optlab\core\archive.py
```

## 目标函数接入方式

OptLab 支持三种自动评估接入方式，并额外支持 UI 手工回填。

### 1. 内置 benchmark

支持：

- `zdt1`
- `zdt2`
- `dtlz2`
- `dtlz7`

示例 payload：

```json
{
  "variables": [
    { "name": "x1", "type": "float", "lower": 0, "upper": 1 },
    { "name": "x2", "type": "float", "lower": 0, "upper": 1 }
  ],
  "objectives": [
    { "name": "f1", "direction": "min" },
    { "name": "f2", "direction": "min" }
  ],
  "evaluator": { "type": "builtin", "name": "zdt1" },
  "budget": { "max_evals": 64, "seed": 11 },
  "algorithm": "random"
}
```

### 2. 本地 Python 插件

Python 插件在 worker 进程中执行，主 FastAPI 服务不直接运行插件代码。v1 认为插件可信，但用独立 worker 降低卡死主服务的风险。

插件示例：

```python
def evaluate(variables, candidate_id=None, context=None, **kwargs):
    x1 = float(variables["x1"])
    x2 = float(variables["x2"])
    return {
        "objectives": {
            "f1": x1 ** 2 + x2 ** 2,
            "f2": (x1 - 1.0) ** 2 + (x2 + 1.0) ** 2,
        },
        "constraints": {},
        "metadata": {"candidate_id": candidate_id},
    }
```

对应 evaluator：

```json
{
  "type": "python",
  "module_path": "D:\\path\\to\\plugin.py",
  "function_name": "evaluate"
}
```

### 3. HTTP 服务

HTTP evaluator 会向用户服务发送 JSON 请求。

请求：

```json
{
  "jobId": "job_123",
  "candidateId": "cand_1",
  "variables": { "x1": 0.2, "x2": 0.8 },
  "context": { "seed": 11 }
}
```

响应：

```json
{
  "objectives": { "f1": 0.25, "f2": 0.75 },
  "constraints": {},
  "metadata": { "source": "external-simulation" }
}
```

对应 evaluator：

```json
{
  "type": "http",
  "url": "http://127.0.0.1:9000/evaluate",
  "timeout_seconds": 10,
  "max_retries": 2
}
```

### 4. UI 手工回填

对于真实工程实验，目标值可能来自：

- CFD/FEA 仿真。
- 物理实验。
- 商业软件。
- 人工评价。
- 离线数据处理流程。

这时不需要写 evaluator。用户在 UI 中使用 ask/tell 表格手动回填目标值即可。

## HTTP API

主要接口：

```text
POST /api/configs/validate
POST /api/advisor/suggest
POST /api/jobs
GET  /api/jobs/{job_id}
POST /api/jobs/{job_id}/cancel
GET  /api/jobs/{job_id}/results
GET  /api/jobs/{job_id}/export.csv
GET  /api/jobs/{job_id}/export.json
WS   /ws/jobs/{job_id}
```

### 交互式 advisor 请求

```json
{
  "problem": {
    "variables": [
      { "name": "x1", "type": "float", "lower": 0, "upper": 1, "scale": "linear" }
    ],
    "objectives": [
      { "name": "f1", "direction": "min" },
      { "name": "f2", "direction": "min" }
    ],
    "constraints": [],
    "evaluator": { "type": "builtin", "name": "manual" },
    "budget": { "max_evals": 200, "seed": 11 },
    "algorithm": "auto"
  },
  "observations": [],
  "batchSize": 1,
  "seed": 11
}
```

响应：

```json
{
  "phase": "initial",
  "algorithm": "sobol-lhs-maximin",
  "suggestions": [
    {
      "candidateId": "suggest_000001",
      "variables": { "x1": 0.52 },
      "reason": "Sobol/LHS/maximin initial design covers the encoded parameter space."
    }
  ],
  "visualization": {
    "recommendedView": "scatter2d",
    "supportingViews": ["parallel-coordinates", "best-per-objective"],
    "objectiveNames": ["f1", "f2"]
  }
}
```

详细契约见 [docs/api-contract.md](docs/api-contract.md)。

## Notebook SDK

Notebook 入口：

```text
notebooks\sdk_examples.py
```

可用 helper：

```python
from optlab.sdk import run_builtin_zdt1, run_http_problem, run_python_plugin_problem

result = run_builtin_zdt1(max_evals=64, seed=11)
```

Python 插件：

```python
result = run_python_plugin_problem(
    "D:/path/to/plugin.py",
    function_name="evaluate",
    max_evals=64,
    seed=11,
    algorithm="random",
)
```

HTTP 服务：

```python
result = run_http_problem(
    "http://127.0.0.1:9000/evaluate",
    timeout_seconds=10.0,
    max_retries=2,
    max_evals=64,
    seed=11,
)
```

## 运行测试

### 后端测试

```powershell
cd D:\mltest
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
```

### Notebook 示例测试

```powershell
cd D:\mltest
backend\.venv\Scripts\python.exe -m pytest notebooks -q
```

### 前端测试

```powershell
cd D:\mltest\frontend
npm run test
```

### 前端生产构建

```powershell
cd D:\mltest\frontend
npm run build
```

## 当前测试覆盖

后端覆盖：

- 变量编码/解码。
- 目标方向转换。
- Pareto 支配和 rank-0 archive。
- 指标计算。
- evaluator 异常归一化。
- HTTP 超时。
- worker 取消。
- Python 插件卡死时 worker terminate。
- synthetic objective coverage dataset 能覆盖每个目标维度，并报告 coverage min、二维投影占用、nearest-distance 分位数和 centered discrepancy。
- advisor `sobol-lhs-maximin` 初始设计确定性。
- advisor `ensemble-MOBO` 建议不重复已观测候选。
- advisor 接受任意手工 observation ID，并在固定 seed 下对手工数据集给出可复现建议。
- advisor 拒绝空 candidateId、越界数值变量和非法布尔变量。
- 高维可视化策略。
- RVEA many-objective 显式运行。
- API 生命周期、结果查询、导出、WebSocket replay。

前端覆盖：

- 本地项目新建、重命名、切换、显式保存和重新打开后恢复最后激活项目。
- 损坏或不可写的浏览器本地存储不会让工作台崩溃。
- 维度优先输入。
- 参数/目标定义表自动生成。
- advisor 请求。
- 候选建议表渲染。
- 用户无需请求建议即可添加并保存手工数据行。
- 用户保存手工数据后，再按需请求算法建议，请求体包含已保存 observations。
- 用户回填 advisor 建议行后可以只保存数据，不会自动请求下一组候选。
- 非法或越界手工参数不会被保存。
- 高维目标下切换 parallel coordinates 指引。
- Result Summary 展示 Pareto preview、best-per-objective、coverage min 和 advisor 来源。

## 稳定性规则

- 所有目标内部统一为最小化。
- 参数变量统一编码到 `[0, 1]`。
- 整数变量解码时 round 并 clamp 到合法范围。
- 固定 seed、固定问题定义、确定性 evaluator 下，候选序列应可复现。
- Pareto archive 中 rank-0 解必须互不支配。
- `n_obj <= 4` 可使用 exact hypervolume；`5-6` 目标优先使用 Pareto 数、可行率、best-per-objective、近似 HV 或抽样指标。

## v1 限制

- 这是本地单用户工具，不提供认证和权限模型。
- Python 插件默认可信，不做沙箱隔离。
- HTTP evaluator 只支持 JSON，不支持文件上传。
- SQLite 足够 v1 使用，暂不接入 PostgreSQL、Ray、Celery 或分布式队列。
- ask/tell advisor 当前是轻量本地 ensemble surrogate + MOBO 风格策略，不等价于完整 BoTorch Bayesian Optimization。
- 交互式 UI 的数据行数量不做固定上限；真实可操作规模主要受浏览器表格渲染性能和本机内存限制影响。
- 交互式项目持久化使用浏览器 `localStorage`，适合本地单用户 v1；跨浏览器、跨设备同步和导入/导出属于后续增强。
- BoTorch/qLogNEHVI/qLogNParEGO 是推荐的后续可选增强，不是当前默认依赖。
- `categorical` 和 `bool` 支持运行与展示，但不承诺与连续变量同等的收敛质量。
- 前端当前聚焦交互式手工评估；自动 evaluator 任务主要通过 API 和 SDK 使用。

## 常见问题

### 为什么交互式优化不直接跑 NSGA-II/NSGA-III？

真实工程目标函数通常评估昂贵，甚至需要人工、仿真软件或实验台架。此时一次性启动完整进化算法并不合适。ask/tell 工作流让算法只提出下一批最值得评估的参数，用户完成评估后再反馈目标值。

### 为什么需要 Sobol/LHS/maximin 初始设计？

在没有足够观测数据前，surrogate 不可靠。Sobol/LHS/maximin 初始设计能在归一化参数空间中做较均匀覆盖，并通过 maximin 筛选减少初始候选过度聚集，为后续 ensemble surrogate 和 MOBO 风格建议提供训练点。

### 高维目标为什么用 parallel coordinates？

超过 3 个目标时，直接三维图无法表达全部目标。parallel coordinates 可以把每个目标作为一条轴，同时显示候选解在多个目标之间的折中。

### 什么时候用 HTTP evaluator？

当工程目标函数已经由另一个服务、仿真平台、脚本服务器或商业软件包装成 HTTP 接口时，使用 HTTP evaluator 最自然。

### 什么时候用 Python 插件？

当目标函数可以在本地 Python 中直接计算，且代码可信时，用 Python 插件最简单。

### 什么时候用 UI 手工回填？

当目标值来自外部实验、人工判断、长时间仿真或暂时无法自动接入的工程流程时，用 UI 手工回填。用户可以把已有实验数据逐行录入，也可以先让 advisor 给出参考候选，再自行决定是否采用、修改或跳过这些候选。

## 相关文档

- [API Contract](docs/api-contract.md)
- [Algorithm Policy](docs/algorithm-policy.md)
