# 下一步开发建议

本文档记录 ModelInquisitor 后续开发建议。第三方 BPMN 到 mCRL2 转译器应保持不变，后续改进应集中在独立的检查器层。

## 整体原则

后续新增能力仍应遵循当前项目定位：不追求 BPMN 与 mCRL2 的完整等价证明，而是通过更多可自动提取、可验证的 Claims，从不同角度提高对转译结果的置信度。

建议优先实现满足以下条件的性质：

- 能从 BPMN 静态结构中稳定提取。
- 能通过当前命名策略映射到 mCRL2 action。
- 能生成明确、可由 mCRL2 工具链验证的 MCF 公式。
- 能补足当前已实现 Claims 的盲区。

## 推荐新增 Claims

### 1. End Event Preservation Claim

目标：确保 BPMN 中的每个 end event 在转译后的 mCRL2 模型中仍然可观察。

当前 deadlock freedom 近似检查已经会使用 end event action，但它是按 process 聚合的。End Event Preservation Claim 可以更细粒度地检查每个 end event 是否被保留：

```text
<true* . end_action>true
```

适用场景：

- 一个流程包含多个 end event。
- 不同 end event 代表不同业务结束状态。
- 转译器可能漏掉某个结束分支。

这类 Claim 与已实现的 Action Preservation Claim 有重叠，但可以单独保留，因为 end event 对流程完整性和死锁分析都很关键。

### 2. Exclusive Branch Reachability Claim

当前 mutex Claim 检查的是两个排他分支不能同时发生，但它不能证明每个分支本身都是可达的。

建议为每条 exclusive branch 的首个可观察动作增加可达性 Claim：

```text
<true* . branch_action>true
```

两类 Claim 配合后可以形成互补：

- branch reachability 检查每个分支是否被保留。
- mutex 检查分支之间是否仍然保持互斥。

### 3. Parallel Branch Preservation Claim

目标：验证 parallel gateway 的各个并行分支没有在转译中丢失。

对每个 parallel split，查找每条分支中的首个可观察动作，并检查其可达：

```text
<true* . branch_action>true
```

这可以捕获并行分支生成缺失或分支连接错误。

### 4. Sequential Successor Claim

目标：检查没有分支干扰的顺序流是否在转译后仍保持基本先后关系。

对于 BPMN 中形如：

```text
A -> B
```

且 A、B 都是可观察节点，并且中间没有 exclusive/parallel gateway 干扰时，可以生成 Claim，要求 B 不能在 A 之前发生：

```text
[(!A)* . B]false
```

这与现有 Causality Claim 接近，但提取规则更局部、更直观，适合作为面向 sequenceFlow 的补充检查。

实现时需要避免与现有 dominator-based causality 产生大量重复 Claim。可以先只对直接相邻的普通任务节点启用，或在输出中合并重复性质。

### 5. Parallel Join Synchronization Claim

当前第三方命名策略已经知道 parallel gateway 的同步动作，例如：

- `c_start_gw_N`。
- `c_sync_join_N`。

可考虑检查：

```text
<true* . c_start_gw_N>true
<true* . c_sync_join_N>true
[(!branch_action)* . c_sync_join_N]false
```

建议在 Parallel Branch Preservation 稳定后，再实现这类更强的同步 Claim。

### 6. Boundary Event Interruption Claim

状态：基础版本已实现为 `flow::boundary_event_lifecycle`，会检查 boundary event 触发后可到达处理分支，并对 interrupting boundary event 检查触发后不再进入正常后继。

后续可继续增强：检查 conditional boundary event 的条件抽象是否与第三方转译器中的 lifecycle guard 一致。

目标：检查 interrupting boundary event 的转译是否保留“中断原任务后进入异常路径”这一核心语义。

对于 `cancelActivity=true` 的 boundary event，可以考虑检查：

- boundary event action 可达。
- boundary event 发生后，原任务正常完成动作不应再发生。
- boundary event 发生后，异常处理分支的首个可观察动作应可达。

公式雏形：

```text
<true* . boundary_action>true
[true* . boundary_action . true* . normal_completion_action]false
<true* . boundary_action . true* . handler_action>true
```

这类 Claim 涉及事件语义和转译命名细节，建议放在基础 action/message/branch Claims 稳定之后再做。

## 工具链与工程改进

### 1. 明确中间产物生命周期

当前 runner 中存在 `keep_artifacts` 参数，但中间产物清理行为尚未完整实现。

建议语义：

- 如果用户提供 `--work-dir`，则保留该目录中的产物。
- 如果没有提供工作目录，则使用临时目录。
- 如确有需要，再增加 `--keep-artifacts` 参数用于保留默认产物。

### 2. 解析 mCRL2 Action Alphabet

当前检查器主要根据 BPMN 和命名策略推导 action 名称。现在已经有一个很窄的源码级检查用于确认虚拟 `Environment` 进程的 send/recv 方向，但尚未系统性解析整个 mCRL2 action alphabet。

建议增加轻量级 mCRL2 action parser，用于提取 `act` 声明。

收益：

- 在调用 `lps2pbes` 之前发现缺失 action。
- 改善公式错误诊断。
- 支持更完整的形式化接口：

```text
E(M_bpmn, Code_mcrl2) -> Claims[]
```

### 3. 改进公式参数处理

当前公式默认使用：

```text
exists oid: OrderId. action(oid)
```

这与当前样例兼容，但不够通用。

后续可改进为：

- 从 mCRL2 action alphabet 中推断 action 参数个数和类型。
- 对无参数 action 生成无参数公式。
- 支持多个参数的 action。

## BPMN 覆盖范围扩展

可考虑逐步扩展 parser 和 extractor 对以下 BPMN 特性的支持：

- inclusive gateway。
- event-based gateway。
- loop task 和 multi-instance task。
- 嵌套 subprocess 语义。
- interrupting 和 non-interrupting boundary event。
- timer、error、signal、conditional event 对应的 Claims。
- 在需要时检查 data-flow preservation。

这些扩展应放在核心集成测试和负例测试完成之后，因为每个新 BPMN 特性都需要回归测试保护。

## 建议开发顺序

1. 实现 End Event Preservation Claims。
2. 实现 Exclusive Branch Reachability Claims。
3. 实现 Parallel Branch Preservation Claims。
4. 清理并明确中间产物生命周期。
5. 增加 mCRL2 action alphabet 解析。
6. 实现 Parallel Join Synchronization Claims。
7. 实现 Sequential Successor Claims。
8. 扩展 boundary event 条件 guard、non-interrupting event 和嵌套 subprocess 等复杂 BPMN 语义。
9. 继续扩大 BPMN 特性覆盖范围。
