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
- 每次对项目进行有意义的修改后，都需要在完成必要验证后提交到 Git，并推送到 GitHub 仓库 `https://github.com/Lorenzo-TTY/optlab`；除非用户明确要求暂缓提交或暂缓推送。
- 子代理用于并行研究、审查、测试设计、局部实现和代码质量复核。
- 子代理不得回退或覆盖未授权文件；并行写入任务必须明确写入范围。
- 每轮子代理结果都需要由主代理审查后再纳入主线。
- 外部资料、论文、官方文档和 GitHub 信息只作为设计依据；落地实现必须通过本地测试验证。
- 当上下文使用量接近 60% 时，主代理需要主动压缩上下文：把当前目标、已改文件、关键决策、阻塞项、测试结果和下一步写入可恢复的本地记录，再继续执行；压缩内容不得遗漏尚未完成的验证、未解决的用户纠偏和未纳入主线的子代理结论。

## 用户执行期望

- 用户对主代理能力预期是：“我对于你的能力预期是超越人类能力边界的”。
- 用户对执行方式的期望是：“我希望你充分利用你具备的一切能力”。
- 因此执行项目任务时应主动调动可用工具、技能、子代理、浏览器验证、文档核查、本地测试和工程审查能力，目标是在当前环境允许范围内交付高质量、可验证、可恢复的结果。

## 自我完善、优化、进化规则

- 每次实现、测试、验证或用户纠偏后，主代理都需要复盘是否暴露了可复用流程、测试缺口、交互瓶颈、工具使用误区或技能说明缺陷；稳定结论应补充进 `AGENTS.md` 或对应 skill。
- 遇到重复低效操作、浏览器接入失败、验证失败、上下文压缩、子代理失效或用户指出偏差时，不只修当前问题，还要更新规则、测试、文档或工具使用策略，降低同类问题复发概率。
- 优化目标必须同时覆盖产品体验、工程质量、测试证据、文档准确性、代理协作流程和可恢复性；不得只满足“代码能运行”的最低标准。
- 新能力优先做成可验证、可扩展、可局部回退的机制；实现时保留后续演进入口，并用测试或浏览器验证证明用户关键路径真实可用。
- 对 Codex/浏览器/ChatGPT Web 等外部工具能力要基于当前可观测事实校准，不把不可控、隔离或空白工具表面误判为可用能力；工具能力边界一旦确认，应沉淀到对应 skill。

## 工程约束

- 后端核心保持可复现：固定 seed、固定问题定义、确定性评估器应得到一致候选序列。
- UI 交互保持用户主导：手工数据集是主数据源，advisor 只读取已保存 observations。
- 优化结果展示必须来自已保存 observations 或后端 archive，不展示未保存草稿数据作为结果。
- 本地优化项目持久化必须以版本化 schema 保存 `problem`、草稿/建议行、已保存 observations、advisor 状态和创建/更新时间；Result Summary、Pareto 前沿和覆盖摘要属于可重算派生结果，不作为权威源持久化。
- 每个项目的数据边界必须隔离：切换项目时只恢复该项目自己的问题定义、草稿、建议和已保存 observations；advisor 请求只能读取当前项目中已保存 observations。
- 浏览器本地存储损坏或配额失败时，UI 不得崩溃；应回退到可继续操作的内存状态或新项目，并在界面中提示持久化失败。
- 参数定义表、目标定义表和 ask/tell 数据录入表需要支持从 Excel/WPS/Google Sheets 等表格工具复制的行列数据；批量粘贴必须按当前单元格向右、向下填充，并自动扩展允许范围内的参数/目标维度或手工数据行。
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

### 2026-05-12

- 新需求：交互界面需要支持新建优化项目、保存每个优化项目的数据和结果、下次打开继续使用，并通过侧边栏或下拉菜单切换项目。
- 按 `talk-with-chatgpt-web` 技能要求，已避免使用非登录的新 Chrome；先尝试 `chrome_devtools` 只看到 `about:blank`，随后改用 Browser runtime 的 `extension` 后端，成功发现并 claim 用户已有 Chrome 中已登录的 `https://chatgpt.com/` 标签页。
- 已向用户现有 Chrome 的 ChatGPT Web 发送项目持久化设计复核问题，内容只包含本地项目的非敏感架构摘要；等待外部建议期间继续本地实现。
- 前端新增 `projectStorage.ts` 与 `ProjectSidebar.tsx`，采用 `localStorage` 保存本地单用户项目列表和最后激活项目 id；项目状态包含 `problem`、草稿/建议行、已保存 observations、advisor 状态、创建/更新时间。
- `App.tsx` 已接入项目侧边栏、新建项目、重命名项目、显式保存项目、切换项目和自动本地保存；`styles.css` 已增加项目侧边栏与宽屏工作区布局。
- ChatGPT Web 第一轮复核结论：本地 `localStorage` 方案适合 v1，但应采用版本化 schema、保存最后激活项目、让 saved observations 成为结果与 advisor 的唯一权威来源、避免持久化派生 summary、处理损坏/配额异常，并把导出/导入作为后续增强。已据此为项目持久化对象加入 `schemaVersion`，并保持 Result Summary 由 observations 实时重算。
- 用户纠偏 `talk-with-chatgpt-web` 使用方式：后续必须直接使用用户本地已打开、已登录的 Chrome 标签页；不得打开新的空白浏览器、隔离上下文或干净 DevTools/Playwright 浏览器来代替。项目上下文可以按需直接发送给 ChatGPT Web，但仍不得发送密钥、cookie、`.env`、浏览器存储或认证材料。
- 已更新 `C:\Users\TT\.codex\skills\talk-with-chatgpt-web\SKILL.md`，明确本地 Chrome 优先、`about:blank` 视为错误浏览器表面、非敏感项目上下文无需过度脱敏、硬性秘密边界保留。
- 已将上下文管理规范写入协作规则：上下文使用量接近 60% 时主动压缩，并把目标、文件、决策、阻塞项、测试证据和下一步落地到可恢复记录。
- 项目持久化补强完成：`projectStorage.ts` 的保存/读取路径会处理损坏 JSON、缺失项目、不可写 `localStorage` 和无效 active project；UI 在本地保存失败时保留内存状态并提示，不让工作台崩溃。
- 前端项目侧边栏补充图标、更新时间、active project 标识和项目列表摘要；`README.md` 已补充本地项目管理、恢复机制、派生结果不持久化和 v1 localStorage 限制。
- 验证通过：`frontend` 下 `npm run test` 通过 12 个测试；`frontend` 下 `npm run build` 通过；`backend\.venv\Scripts\python.exe -m pytest backend\tests -q` 通过 44 个测试；`backend\.venv\Scripts\python.exe -m pytest notebooks -q` 通过 3 个测试；`git diff --check` 无空白错误，仅提示 Windows 行尾转换。
- 浏览器交互验证通过：在 `http://127.0.0.1:5173/` 创建 `Wing sweep` 并保存 1 条 observation，新建 `Thermal sweep` 并保留未提交草稿行，重新打开页面后恢复最后激活项目，再切回 `Wing sweep` 时已保存 observation、Result Summary 和项目列表摘要保持正确；浏览器 console 无 error/warn，仅有 React DevTools info。
- 根据用户要求，已将“每次有意义修改项目后验证、提交并推送到 GitHub 仓库 `https://github.com/Lorenzo-TTY/optlab`”写入协作规则。
- 根据用户要求，已将“我对于你的能力预期是超越人类能力边界的”和“我希望你充分利用你具备的一切能力”写入用户执行期望。
- 新需求：参数定义、目标定义和 ask/tell 数据录入需要支持从 Excel 等表格以行/列形式批量复制粘贴，避免逐个单元格手动输入。
- 已按 `talk-with-chatgpt-web` skill 尝试查找可用 Chrome；`chrome_devtools` 只暴露 Playwright MCP 的 `about:blank` 隔离实例，本机正常 Chrome profile 正在运行但未通过当前可用工具暴露为可 claim 的用户标签页，因此未向 ChatGPT Web 发送项目内容。
- 已进一步更新 `C:\Users\TT\.codex\skills\talk-with-chatgpt-web\SKILL.md`：明确 Codex 只能控制工具暴露的 Chrome 表面；自动发现顺序应优先 `browser.user.openTabs()` / `browser.user.claimTab(...)` 或 extension-backed 用户标签页；拒绝 `about:blank`、`ms-playwright`、临时 `user-data-dir` 和 `--remote-debugging-pipe` 隔离实例。
- 已新增 `frontend/src/spreadsheet.ts`，并在 `ConfigPanel` 和 `ResultsTable` 接入 TSV/CSV 风格表格解析；参数/目标定义表支持从任意单元格开始粘贴并自动扩展维度，ask/tell 表支持从任意参数/目标单元格粘贴并自动追加手工行。
- 前端验证通过：`frontend` 下 `npm run test` 通过 14 个测试；`frontend` 下 `npm run build` 通过。
- `/compact` 检查点：当前目标是完成表格批量粘贴功能的剩余验证、浏览器交互复测、提交并推送；本轮已改 `README.md`、`AGENTS.md`、`frontend/src/App.tsx`、`frontend/src/App.test.tsx`、`frontend/src/components/ConfigPanel.tsx`、`frontend/src/components/ResultsTable.tsx`，新增 `frontend/src/spreadsheet.ts`；后续不得遗漏 `git diff --check`、后端回归、浏览器粘贴关键路径验证、Git 提交和 GitHub 推送。
- `/compact` 后补充回归验证通过：`frontend` 下 `npm run test` 通过 14 个测试，`frontend` 下 `npm run build` 通过；`backend\.venv\Scripts\python.exe -m pytest backend\tests -q` 通过 44 个测试；`git diff --check` 无空白错误，仅提示 Windows 行尾转换。
- 浏览器粘贴复测通过：在 `http://127.0.0.1:5173/` 从参数定义表粘贴 `temperature/pressure` 两行、从目标定义表粘贴 `cost/quality` 两行，再在 ask/tell 中粘贴两行 `temperature/pressure/cost/quality` 数据；界面自动扩展到 2 参数/2 目标、自动追加 `manual_000002`，保存后 Result Summary 显示 `2 saved / 2 feasible`，浏览器 console 仅有 React DevTools info。
