# 算法策略

OptLab v1 将两类优化场景分开处理：自动评估任务使用进化算法，交互式工程闭环使用 ask/tell advisor。

## 自动评估任务

自动评估任务由后端 worker 在预算内连续调用 evaluator，并把已评估结果写入 archive。默认策略保持稳定、泛用、可复现：

- `n_obj == 1`：单目标 GA 或 random baseline。
- `2 <= n_obj <= 3`：NSGA-II。
- `4 <= n_obj <= 6`：NSGA-III。
- `4 <= n_obj <= 6`：可显式选择 RVEA，作为 many-objective 替代方案。

这一路径适合内置 benchmark、本地 Python 插件和 HTTP evaluator 可以自动返回目标值的场景。

## 交互式 ask/tell advisor

交互式任务以用户保存的 observations 为主数据源。用户可以无限量手工补充参数/目标观测数据；advisor 建议只是可选、可编辑的参考，不会强制作为下一组输入，也不会自动触发下一轮实验。

advisor 接口保持无状态。每次 `/api/advisor/suggest` 请求都发送完整 `ProblemSpec`、当前已保存 observations、batch size 和 seed。未保存草稿行不会进入 advisor，也不会进入优化结果展示。

当前 advisor 分两阶段：

- 初始设计阶段使用 `sobol-lhs-maximin`，综合 Sobol、Latin hypercube 和 maximin 候选筛选，优先覆盖归一化参数空间。
- surrogate 阶段使用 `ensemble-MOBO`，采用 qLogNParEGO-style Chebyshev scalarization，把多目标观测转成多个随机权重下的标量化问题，再结合 Gaussian Process、Random Forest、Neural Network surrogate 的集成预测，以及 uncertainty/diversity scoring 选择候选。

这是轻量本地 v1 实现，运行时依赖 `scikit-learn`，不依赖 PyTorch、GPyTorch 或 BoTorch。策略设计对齐 MOBO、ParEGO 和 qLogNParEGO 思路，但不声明等价于完整 BoTorch acquisition optimization。后续可以把 BoTorch `qLogNEHVI` / `qLogNParEGO` 作为可选增强，用于更昂贵、噪声更强的工程评估。

## 可视化和结果摘要

目标空间展示按目标维度选择主视图：

- 2 个目标：2D scatter。
- 3 个目标：3D scatter，并保留 parallel coordinates 作为辅助视图。
- 4-6 个目标：parallel coordinates 作为主视图。

Result Summary 展示来自已保存 observations 或后端 archive 的结果，不使用未保存草稿数据。摘要重点包括 best-per-objective、Pareto preview、Pareto count 和 coverage min，用于快速判断目标空间覆盖、当前最优目标值和 Pareto 前沿质量。

## 测试与验证要求

当前策略需要覆盖以下验证：

- synthetic objective coverage dataset 能覆盖每个目标维度，并报告 coverage min、二维投影占用、nearest-distance 分位数和 centered discrepancy。
- `sobol-lhs-maximin` 初始建议在固定 seed、固定问题定义下可复现。
- `ensemble-MOBO` 在已有 observations 下给出确定性、唯一且不重复已观测候选的建议。
- ask/tell 请求只读取已保存 observations，用户可继续手工补数据而不被算法建议绑定。
- UI Result Summary 能展示 Pareto preview、best-per-objective、coverage min 和 advisor 来源。

## 研究依据与后续路线

- BoTorch qLogNEHVI 是昂贵噪声多目标工程闭环的目标可选后端。
- qLogNParEGO 是较高目标数或批量标量化 BO 的优先 fallback 思路。
- qEHVI/qNEHVI 作为概念祖先保留引用；log-EI 系列用于缓解 EI/EHVI 数值消失问题。
- AGE-MOEA2 当前不作为默认选项，因为本地 pymoo import 需要额外 `numba`；RVEA 可在不新增该依赖的情况下用于 many-objective 任务。

参考资料：

- BoTorch multi-objective docs: https://botorch.org/docs/multi_objective
- BoTorch acquisition API: https://botorch.readthedocs.io/en/stable/acquisition.html
- qNEHVI paper: https://papers.nips.cc/paper/2021/hash/11704817e347269b7254e744b5e22dac-Abstract.html
- qEHVI paper: https://arxiv.org/abs/2006.05078
- LogEI paper: https://arxiv.org/abs/2310.20708
- pymoo RVEA docs: https://pymoo.org/algorithms/moo/rvea.html
- pymoo algorithm catalog: https://pymoo.org/index.html
