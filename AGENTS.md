# OptLab Agent 工作协议

本文档记录本项目中 Codex 与子代理的协作规则、执行边界、验证要求和重要操作日志。之后每次进行有意义的实现、测试、审查、文档或提交操作，都需要同步补充本文件的“执行记录”。

## 项目目标

OptLab 是面向工程场景的本地多目标优化工作台。当前重点方向：

- 支持用户自由定义参数空间维度和目标空间维度。
- 支持用户自行录入任意数量的参数/目标观测数据。
- 算法建议作为可选参考，不强制作为下一组输入。
- 采用稳定、泛用的多目标优化策略，逐步增强到 Gaussian Process、Random Forest、Neural Network surrogate 和 Multi-objective Bayesian Optimization 等能力。
- 对不同变量维度、目标维度和目标空间覆盖情况进行可复现实验验证。
- 在 UI 中明确展示优化结果、Pareto 前沿、best-per-objective、覆盖诊断和建议来源。

## 协作规则

- 主代理负责整体集成、关键路径实现、最终验证、提交和推送。
- 子代理用于并行研究、审查、测试设计、局部实现和代码质量复核。
- 子代理不得回退或覆盖未授权文件；并行写入任务必须明确写入范围。
- 每轮子代理结果都需要由主代理审查后再纳入主线。
- 外部资料、论文、官方文档和 GitHub 信息只作为设计依据；落地实现必须通过本地测试验证。

## 工程约束

- 后端核心保持可复现：固定 seed、固定问题定义、确定性评估器应得到一致候选序列。
- UI 交互保持用户主导：手工数据集是主数据源，advisor 只读取已保存 observations。
- 优化结果展示必须来自已保存 observations 或后端 archive，不展示未保存草稿数据作为结果。
- 高维目标优先使用平行坐标、best-per-objective、Pareto count、覆盖指标等可解释视图。
- 新增依赖必须写入对应项目配置，并在本地环境中安装和验证。
- 重要功能必须覆盖后端测试、前端测试和浏览器交互测试。

## 当前子代理使用策略

- 算法研究代理：对 MOBO、GP、RF、NN surrogate、采集函数、空间填充设计给出落地建议。
- 后端审查代理：检查 advisor、surrogate、数据生成、稳定性和 API 契约。
- 前端审查代理：检查结果展示、交互状态、可访问性和高维布局。
- 测试代理：补充覆盖、稳定性、前端结果展示和交互闭环测试。
- 最终审查代理：在提交前检查回归风险、文档一致性和测试证据。

## 执行记录

### 2026-05-11

- 创建 `AGENTS.md`，建立项目级代理协作协议和持续记录要求。
- 当前工作分支为 `main`，远端同步到 `origin/main`，本轮高级优化能力实现仍在进行中。
- 已开始本轮目标：补强空间填充数据生成、目标空间覆盖测试、ensemble surrogate/MOBO advisor、优化结果 UI 和稳定性验证。
- 已发现本地后端环境已有 SciPy、缺少 scikit-learn；已将 `scikit-learn>=1.5` 加入后端依赖并安装到当前 venv，用于 GP/RF/NN surrogate。
- 已启动可用数量的并行子代理进行算法、数据覆盖和前端结果展示审查；因线程上限，后续会在代理完成后继续派发下一批。
- 新增 `backend/src/optlab/core/designs.py`，提供 Sobol/LHS/maximin 混合空间填充设计、合成目标空间覆盖数据集和覆盖指标。
- 将 advisor 主流程切换到 `sobol-lhs-maximin` 初始设计与 `ensemble-mobo` surrogate 阶段；surrogate 阶段采用 qLogNParEGO 风格 Chebyshev 标量化，并结合 Gaussian Process、Random Forest、Neural Network 与不确定性/多样性评分。
- 移除未纳入主线的重复 `surrogates.py` 草稿，避免后端存在两套代理模型实现。
- 会话压缩后，旧子代理句柄返回 `not_found`；已重新启动四个范围隔离的子代理，分别负责后端 advisor 性能与测试、前端 Result Summary 测试、README/算法文档同步、最终审查清单。主代理继续负责集成、联网依据、交互验证、提交和推送。
- 已重新联网核查算法依据：BoTorch 文档显示当前 MOBO 支持 `qLogNEHVI`、`qLogEHVI`、`qLogNParEGO`；SciPy QMC 文档支持 Sobol 与 LatinHypercube；pymoo 文档与 GitHub 覆盖 NSGA-III、RVEA 等多/多目标进化算法。v1 文档需要准确说明本项目当前实现为本地轻量 ensemble-MOBO，而非直接引入 BoTorch 运行时。
- 文档子代理完成 `README.md` 与 `docs/algorithm-policy.md` 同步，覆盖 ask/tell 自由补数据、`sobol-lhs-maximin` + `ensemble-MOBO`、Result Summary、高维可视化、`scikit-learn` 依赖和覆盖测试说明；主代理后续会结合实际测试结果复核文档准确性。
- 审查子代理发现需补强事项：目标空间覆盖测试不能只依赖每轴 min-max 范围，应增加投影占用、discrepancy、nearest-distance 分位数等指标；advisor 需测试 GP/RF/NN surrogate 真实参与而非静默降级；Result Summary 的 Saved 计数应表示全部保存行而不是 feasible 子集；浏览器交互验证仍是提交前阻塞项。
- 前端子代理修复 Result Summary 引入后的测试多重命中问题：测试改为按结果录入表和 summary 内部表格 scoped query；mock advisor 同步为 `sobol-lhs-maximin` / `ensemble-mobo`；数值格式去除无意义尾零。子代理报告 `npm run test` 与 `npm run build` 均通过，但未完成真实浏览器截图验证。
- 后端子代理修复 advisor surrogate 阶段性能问题：原实现每生成一个 batch suggestion 都重复 fit GP/RF/NN，现改为每次 advisor request 只训练与评分一次，batch 内复用基础分数并叠加 diversity penalty。子代理报告 `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_designs.py backend\tests\test_advisor.py -q` 结果为 17 passed。
- 主代理根据审查意见继续补强：`OptimizationResults` 的 Saved 计数改为全部已保存 observations；`ParetoView` 保持用户定义的目标顺序；`coverage_summary` 增加 nearest-distance 分位数、二维投影网格占用率和 centered discrepancy；`synthetic_objective_coverage_dataset` 增加目标空间 Sobol/LHS/maximin anchor；后端测试新增 GP/RF/NN surrogate 真实参与断言。
- 验证通过：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_designs.py backend\tests\test_advisor.py -q` 通过 21 个测试；`frontend` 下 `npm run test` 通过 7 个测试。
- 更完整验证通过：`backend\.venv\Scripts\python.exe -m pytest backend\tests -q` 全部通过；`backend\.venv\Scripts\python.exe -m pip check` 显示无破损依赖；`frontend` 下 `npm run build` 通过。
- Notebook 示例验证通过：`backend\.venv\Scripts\python.exe -m pytest notebooks -q` 通过 3 个测试；文档中的算法依据链接已调整到 BoTorch 当前 latest 多目标文档入口，并补充覆盖测试指标描述。
- 浏览器交互验证通过：重启本地 8000/5173 开发服务后，在 `http://127.0.0.1:5173/` 完成 2 目标手工数据保存、可选 advisor 建议请求、advisor 行目标回填与保存、确认不会自动请求下一批；切换到 5 目标后完成高维手工数据保存，Result Summary 显示 `2 saved / 2 feasible / 2 Pareto / coverage min`，Best Per Objective 和 Pareto Front Preview 可见，Objective Explorer 显示 `Parallel coordinates primary`。浏览器 console error/warn 数为 0。
- 已关闭上一批已完成子代理，并启动提交前只读复审代理两名：一名审查后端算法/覆盖/测试，一名审查前端结果展示/交互/文档一致性。主代理继续准备最终 diff、测试和 Git 提交。
- 前端/文档复审代理发现提交前阻塞项：`Get optional algorithm suggestion` 当前会隐式提交已完成但未显式保存的草稿行，并发送给 advisor，违反“未保存数据不进入 advisor”的产品契约。需要改为 advisor 只读取已保存 observations，并新增前端反例测试。
- 后端复审代理发现提交前阻塞项：surrogate 阶段在最小观测数时可能实际只使用 `gp/rf` 或降级 `idw`，但响应仍可能让用户误以为完整 GP/RF/NN ensemble 已参与。需要真实披露模型列表/降级状态，补最小门槛和 fallback 测试，并考虑提高 surrogate 启动观测阈值。
- 已修复两个复审阻塞项：前端 `handleAsk` 改为只把已保存 observations 发送给 advisor，不再隐式保存完整草稿行；后端 `ensemble-MOBO` reason 会披露 `full GP/RF/NN ensemble` 或 `degraded ensemble (...)` 以及实际模型列表，初始设计阈值提高到至少 12 个观测点。新增测试覆盖未保存草稿不进入 advisor、目标顺序保留、`idw` fallback 披露、错误维度 existing 拒绝和坏覆盖数据集负例。
- 阻塞项修复后的目标验证通过：`frontend` 下 `npm run test` 通过 9 个测试；`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_designs.py backend\tests\test_advisor.py -q` 通过 24 个测试。
- 阻塞项修复后的完整验证通过：`backend\.venv\Scripts\python.exe -m pytest backend\tests -q` 全部通过 44 个测试；`backend\.venv\Scripts\python.exe -m pytest notebooks -q` 通过 3 个测试；`backend\.venv\Scripts\python.exe -m pip check` 无破损依赖；`frontend` 下 `npm run build` 通过。
- 最终浏览器复测通过：完整但未保存的手工行直接请求 advisor 时，Saved observations 仍为 0，manual 行保持 `complete`，advisor 建议只作为 active recommendation 出现；显式保存后 Result Summary 更新；advisor 行保存后不会自动请求下一批；5 目标自定义顺序 `drag/lift/cost/noise/mass` 下，Objective Explorer 使用 parallel coordinates，Result Summary/Pareto preview 表头保持用户定义顺序。浏览器 console error/warn 数为 0。
- 最终静态复查中移除 advisor 内不再使用的旧 `_latin_hypercube` 与 `_idw_expected_score` helper，并将旧测试名 `test_initial_lhs...` 改为 `test_initial_space_filling...`，避免代码和测试命名继续暗示旧算法路径。
- 清理后回归验证通过：`backend\.venv\Scripts\python.exe -m pytest backend\tests\test_designs.py backend\tests\test_advisor.py -q` 通过 24 个测试；`frontend` 下 `npm run test` 通过 9 个测试；`git diff --check` 无空白错误，仅提示 Windows 行尾转换。
