# 当前已实现内容

## 项目定位

ModelInquisitor 是一个用于 BPMN 到 mCRL2 转译流程的旁路验证模块。它不替代主验证器，也不试图证明 BPMN 模型与生成的 mCRL2 模型在完整语义上绝对等价。

本项目采用更工程化的方式：从 BPMN 源模型中抽取关键语义事实，表示为 Claims，再将这些 Claims 转换为 modal mu-calculus 公式，并使用 mCRL2 工具链在转译后的 mCRL2 模型上进行验证。

当前验证流程如下：

```text
BPMN XML -> BPMN 解析器 -> Claim 提取器 -> MCF 公式生成器
                                      mCRL2 模型 -> mCRL2 工具链 -> 验证结果
```

## 已实现模块

### 1. 核心模型

核心模型位于 `ModelInquisitor/core/models.py`。

目前定义了：

- `BPMNModel`：完整的 BPMN 协作模型。
- `ProcessModel`：单个 BPMN 流程，包含节点、顺序流、开始事件和 `is_executable` 标记。
- `BPMNNode`：任务、事件、网关、子流程等 BPMN 节点及其元数据。
- `SequenceFlow`：单个流程内部的控制流边。
- `MessageFlow`：跨参与者的通信边。
- `Participant`：BPMN 协作图中的参与者元数据。
- `Claim`：需要在 mCRL2 端验证的语义断言。

图算法辅助模块位于 `ModelInquisitor/core/graph.py`，目前提供：

- 从指定节点出发的可达性分析。
- 分支结构的汇合点查找。
- 用于因果关系提取的支配节点分析。

### 2. BPMN 解析器

BPMN 解析器位于 `ModelInquisitor/parsers/bpmn.py`。

当前支持解析：

- BPMN `process`。
- 常见任务节点，包括 `serviceTask`、`receiveTask`、`sendTask`、`userTask`、`task`、`scriptTask`。
- `startEvent`、`endEvent`、`parallelGateway`、`exclusiveGateway`、`subProcess`、`boundaryEvent`、`intermediateCatchEvent`、`intermediateThrowEvent`。
- `sequenceFlow`。
- `participant`。
- `messageFlow`。
- message、timer、conditional、signal、error 等事件定义元数据。
- `process.isExecutable`，用于区分真实可执行流程与非可执行的环境/占位流程。
- subprocess 内部的可观察节点和内部 sequence flow，并记录内部节点所属的 `parent_subprocess_id`。

解析器还会记录节点所属流程，并支持将单个流程导出为 NetworkX 有向图，方便后续进行图分析。

### 3. Claim 提取器

Claim 提取由 `ModelInquisitor/extractors/__init__.py` 统一组织。目前所有 Claim kind 都统一整理为 `prefix::claim_name`，前缀限定为 `soundness`、`flow`、`concurrency`、`interaction`。

#### 3.1 死锁自由近似检查

实现位于 `ModelInquisitor/extractors/deadlock.py`。

该提取器会为每个 BPMN 流程生成一个 Claim，要求该流程应当能够到达某个 end event。

需要注意的是，当前语义是有意采用的近似版本：生成的公式检查的是 end event 可达性，而不是严格意义上的全路径死锁自由性质。

非可执行流程会被跳过。这样第三方样例中用于闭合 message flow 的虚拟 `Environment` 参与者不会被误报为无法到达 end event。

#### 3.2 Action Preservation 检查

实现位于 `ModelInquisitor/extractors/action_preservation.py`。

该提取器会为每个 BPMN 可观察节点生成一个 Claim，要求该节点在转译后的 mCRL2 模型中仍然可以作为可达 action 被观察到。

当前覆盖范围包括：

- 普通任务节点。
- send/receive/message 相关任务。
- end event。
- boundary event。
- intermediate catch/throw event。
- 带事件定义的 start event。

生成的公式形如：

```text
<true*>(<exists oid: OrderId. action(oid)>true)
```

这类 Claim 主要用于检查转译完整性：如果 BPMN 中的关键业务动作在 mCRL2 中消失、命名错误或不可达，验证会失败。

#### 3.3 End Event Preservation 检查

实现位于 `ModelInquisitor/extractors/end_event_preservation.py`。

该提取器会为每个 BPMN end event 单独生成一个 `soundness::end_event_preservation` Claim，要求该结束事件在转译后的 mCRL2 模型中仍然作为可达终止动作出现。

这比按流程聚合的 deadlock freedom 近似更细粒度，可以发现多结束事件流程中某个特定结束分支被漏转或命名错误的问题。

#### 3.4 Message Flow Rendezvous 检查

实现位于 `ModelInquisitor/extractors/concurrency_semantics.py` 的通信 claim 提取逻辑。

该逻辑会为每条 BPMN `messageFlow` 生成 interaction Claims，要求该消息在 mCRL2 模型中表现为同步后的 communicated action，并且尊重参与者侧控制流上下文。

对一条 message flow，命名策略会推导：

- send action：`s_msg`。
- receive action：`r_msg`。
- communicated action：`c_msg`。

`interaction::rendezvous_visibility` 同时检查：

```text
<true*>(<exists oid: OrderId. c_msg(oid)>true)
[true* . (exists oid: OrderId. s_msg(oid))]false
[true* . (exists oid: OrderId. r_msg(oid))]false
```

`interaction::rendezvous_causality` 则检查全局通信动作不能早于发送方和接收方各自的可观察前置上下文。

这两类 Claim 一起覆盖消息同步语义，用于发现通信同步规则缺失、`comm` 配置错误、原始 send/receive 动作意外暴露，或通信过早发生等问题。

#### 3.5 因果依赖检查

实现位于 `ModelInquisitor/extractors/causality.py`。

该提取器会对每个流程计算支配节点关系。如果一个可观察源节点支配另一个可观察目标节点，就生成一个 Claim，表示目标节点不能在源节点之前发生。

这可以捕获直线流程或结构化流程区域中的必要前驱关系。

#### 3.6 互斥排他检查

实现位于 `ModelInquisitor/extractors/mutex.py`。

对于拥有多条输出分支的 exclusive gateway，该提取器会查找每条分支中的首个可观察动作，并生成两两互斥的 Claims。

生成的性质用于检查同一次执行 trace 中不应同时出现两个排他分支动作。

#### 3.7 Exclusive Branch Reachability 检查

实现位于 `ModelInquisitor/extractors/exclusive_branch_reachability.py`。

该提取器会为 exclusive gateway 的每条输出分支查找首个可观察动作，并生成 `flow::exclusive_branch_reachability` Claim，要求每条可选择分支本身仍然可达。

它与 mutex 类 Claim 互补：mutex 证明排他分支不能同时发生，branch reachability 则证明每条分支没有在转译中被丢失。

#### 3.8 并发语义扩展 Claims

实现位于 `ModelInquisitor/extractors/concurrency_semantics.py`。

该提取器新增了以下已整理前缀的 Claim：

- `concurrency::no_artificial_ordering`：parallel gateway 下独立分支的关键动作应存在两种可达先后顺序。
- `concurrency::branch_order_preservation`：同一并发分支内部的可观察顺序不能被并发展开打乱。
- `concurrency::branch_co_occurrence`：parallel gateway 的各分支关键动作应能出现在同一条执行 trace 中。
- `concurrency::no_early_join`：join 后续动作必须等待所有分支 completion action。
- `concurrency::join_reachable_after_all_branches`：所有分支完成后，join 后续动作必须仍然可达。
- `concurrency::exactly_once_branch_completion_before_join`：非循环结构化 parallel block 的每个分支 completion action 在 join 前应恰好出现一次。
- `interaction::rendezvous_visibility`：message flow 应表现为 `c_msg`，而不是裸露的 `s_msg` 或 `r_msg`。
- `interaction::rendezvous_causality`：全局通信动作不能早于参与者侧控制流前置上下文。
- `interaction::environment_rendezvous_visibility`：由虚拟 Environment 参与者闭合的 message flow 也应表现为同步后的 `c_msg`，且不能暴露裸 `s_msg` / `r_msg`。
- `interaction::environment_endpoint_direction`：虚拟 Environment 进程的 send/recv 方向应与 BPMN message flow 的 source/target 方向一致。
- `interaction::conversation_order_preservation`：由同一参与者控制流推出的消息顺序应在全局 trace 中保持。
- `interaction::no_post_resolution_chatter`：event-based waiting loop 被 resolving message 解决后，循环问询/回复不应继续出现。
- `flow::exclusive_branch_reachability`：exclusive gateway 的每条分支首个可观察动作都应可达。
- `flow::exclusive_branch_mutex`：exclusive gateway 的互斥分支不能在同一条 trace 中共同出现。
- `flow::event_based_first_wins`：event-based gateway 每轮等待中先发生的事件排除本轮其他候选事件。
- `flow::event_based_branch_reachability`：event-based gateway 的每个候选事件分支都应可达。
- `soundness::bounded_unfolding_soundness`：在默认 bound 2 内，循环展开 0..2 次后退出 trace 应可达。
- `flow::escape_possibility`：执行循环体后，退出动作仍应可达。
- `flow::no_forced_starvation`：在等待点上 resolving exit 应保持可达，作为 starvation/fairness 的有限近似检查。
- `soundness::subprocess_expansion_preservation`：subprocess 内部可观察动作应在 mCRL2 模型中保持可达，避免子流程被错误折叠成不透明占位动作。
- `flow::boundary_event_lifecycle`：boundary event 触发后应能到达处理分支；对 interrupting boundary event，还要求触发后不能继续到原正常后继。

这些 Claims 仍遵循项目的旁路验证定位：优先从 BPMN 静态结构中抽取关键、可命名、可由 MCF 公式验证的语义事实，而不是试图完整重建 BPMN 运行时语义。

### 4. 命名策略

命名策略抽象位于 `ModelInquisitor/strategies/base.py`。

当前具体实现为 `ModelInquisitor/strategies/third_party_bpmn2mcrl2.py`，用于适配仓库中的 `third-party/bpmn2mcrl2` 转译器命名约定。

它负责将 BPMN 概念映射到 mCRL2 action 名称，包括：

- 任务动作。
- end event 动作。
- message flow 对应的 send、receive、communicated actions。
- 第三方转译器使用的 parallel gateway 同步动作。

通过命名策略，检查器可以保持与转译器实现本身解耦。

### 5. MCF 公式生成

公式生成器位于 `ModelInquisitor/generators/mcf.py`。

它会将 Claims 转换为 modal mu-calculus 公式：

- 死锁自由近似：检查 end event 动作是否可达。
- Action Preservation：检查 BPMN 可观察节点对应 action 是否可达。
- 因果依赖：检查目标动作不能在源动作之前发生。
- 互斥排他：检查两个分支动作的两种先后顺序都不允许出现。
- 并发 interleaving：检查并行分支两种先后顺序、分支内部顺序和分支共同出现。
- Join：检查 no-early-join、所有分支完成后的可达性，以及 join 前 completion action 的 exactly-once 约束。
- 通信：检查 rendezvous 可见性、Environment message flow 可见性、通信因果、conversation order 和 resolving message 后的等待循环终止。
- 静态源码检查：`interaction::environment_endpoint_direction` 使用 runner 直接检查生成的 mCRL2 源码，而不是交给 PBES 求解。
- 选择与循环：检查 exclusive/event-based choice 语义，以及 bounded unfolding、escape、starvation 近似性质。

当前公式默认假设 mCRL2 action 带有 `OrderId` 参数，形式为 `action(oid)`。

### 6. 验证 Runner

验证 runner 位于 `ModelInquisitor/runners/verifier.py`。

它负责执行完整的 mCRL2 验证链路：

```text
mcrl22lps -> lps2pbes -> pbes2bool
```

对每个生成的 Claim 公式，runner 会写出 `.mcf` 文件，将其转换为 PBES，再求解 PBES，并报告该 Claim 是否通过。

对于 `interaction::environment_endpoint_direction`，runner 会读取生成的 mCRL2 源码并直接匹配对应的 `env_send_*` / `env_recv_*` 进程定义。这个静态检查即使在 mCRL2 工具链缺失或 `mcrl22lps` 转换失败时也会执行。

如果 mCRL2 命令行工具不在 `PATH` 中，runner 会将每个 Claim 标记为 `not_run`。

### 7. 命令行接口

命令行入口位于 `main.py`。

基本使用方式：

```text
python main.py <source.bpmn> <translated.mcrl2>
```

可选参数：

- `--work-dir`：指定生成 `.lps`、`.mcf`、`.pbes` 等中间产物的目录。
- `--show-formulas`：打印生成的 MCF 公式。

CLI 会输出：

- 紧凑的验证结果表。
- 按 Claim 类型分组的解释。
- 失败详情，或在指定 `--show-formulas` 时输出公式详情。

退出码含义：

- `0`：所有 Claims 均通过。
- `1`：至少一个 Claim 验证为 false。
- `2`：输入文件不存在。
- `3`：模型转换、公式生成、求解失败，或工具链未运行。

## 已实现测试

测试位于 `tests/test_model_inquisitor.py`。

当前覆盖：

- 与第三方转译器兼容的名称清洗规则。
- BPMN parser 是否保留流程、节点、边和 message flow 元数据。
- 流程图边是否正确导出。
- message flow 的源流程和目标流程解析。
- 第三方命名策略是否能匹配样例 mCRL2 中的 action。
- Claim 抽取。
- MCF 公式生成。
- 真实 mCRL2 工具链端到端验证；如果工具链缺失，该测试会自动跳过。

当前本地测试结果：

```text
45 passed
```

## 当前端到端状态

在 `.venv` 依赖安装完成，且 mCRL2 命令行工具已经加入 `PATH` 后，当前样例可以端到端运行：

```text
.venv/bin/python main.py tests/input/spec.bpmn tests/input/spec.mcrl2 --work-dir .verify-artifacts
```

观测结果：

```text
42 个 Claims 全部通过
```

通过的 Claims 包括：

- 2 个死锁自由近似 Claims。
- 8 个 Action Preservation Claims。
- 2 个 End Event Preservation Claims。
- 6 个因果依赖 Claims。
- 6 个 Necessary Response Claims。
- 2 个 `concurrency::no_artificial_ordering` Claims。
- 2 个 `concurrency::branch_co_occurrence` Claims。
- 2 个 `concurrency::no_early_join` Claims。
- 2 个 `concurrency::join_reachable_after_all_branches` Claims。
- 2 个 `concurrency::exactly_once_branch_completion_before_join` Claims。
- 3 个 `interaction::rendezvous_visibility` Claims。
- 3 个 `interaction::rendezvous_causality` Claims。
- 2 个 `interaction::conversation_order_preservation` Claims。

当前基础样例没有生成 mutex、branch-order、event-based choice 或 loop Claim，因为输入 BPMN 中没有对应结构；这些能力由独立的内联测试和 pizza collaboration 样例覆盖。

第三方 `sample4` 的两个真实输出也已覆盖：

- `Freight-Forward.bpmn` + `freight-forward_output.mcrl2`：63 个 Claims 全部通过，非可执行 `Environment` 流程不会再生成 deadlock freedom Claim。
- `Transport.bpmn` + `transport_output.mcrl2`：45 个 Claims 全部通过，Environment send/recv 方向和同步可见性均通过检查。
