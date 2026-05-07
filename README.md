# ModelInquisitor - Claims-based BPMN Translation Checker

ModelInquisitor checks whether an mCRL2 translation preserves key semantic facts from the source BPMN model. It does not try to prove full equivalence between BPMN and mCRL2. Instead, it extracts semantic invariants as Claims, renders them as modal mu-calculus formulas, and verifies those formulas against the translated model.

The default naming strategy is compatible with `third-party/bpmn2mcrl2`, but that compatibility lives behind a replaceable strategy interface. The parser, Claim extractors, formula generator, and runner do not depend directly on one concrete translator.

## Architecture

```text
ModelInquisitor/
├── core/        # BPMN model, Claims, and graph algorithms
├── parsers/     # BPMN XML parsing and NetworkX graph export
├── extractors/  # Semantic Claim extractors
├── generators/  # Claim -> MCF formula generation
├── strategies/  # Replaceable BPMN -> mCRL2 naming strategies
└── runners/     # mCRL2 toolchain orchestration
```

## Claims

- **Deadlock freedom**: each process should still be able to reach an end event.
- **Causality**: a source node should be a necessary predecessor of a target node.
- **Message synchronization**: cross-process message sends and receives should be forced to synchronize.
- **Mutex**: branches under an exclusive gateway should not both occur in one execution trace.
- **Interrupting boundary mutex**: an interrupting boundary event's exceptional branch should be mutually exclusive with the normal continuation of the attached task.
- **Necessary response**: if a response node post-dominates a source node, then every continuation after the source should eventually reach the response.

Claim formulas mention only actions that represent BPMN-visible semantics. Translator-internal helper actions such as raw `s_*`/`r_*` message endpoints and gateway synchronization actions are treated as implementation detail rather than semantic claim targets. For a BPMN message flow, the communicated `c_*` action is the semantic representative of the message exchange.

## Command-line Verification

Install dependencies with `uv`:

```powershell
uv sync --dev
```

Verify a BPMN/mCRL2 pair:

```powershell
uv run python main.py tests/input/spec.bpmn tests/input/spec.mcrl2
```

Keep intermediate artifacts and print generated formulas:

```powershell
uv run python main.py tests/input/spec.bpmn tests/input/spec.mcrl2 --work-dir .verify-artifacts --show-formulas
```

The runner calls the real mCRL2 toolchain:

```text
mcrl22lps -> lps2pbes -> pbes2bool
```

The default UI prints a compact result table and a grouped explanation of what was checked. Detailed panels are shown only for failures or when `--show-formulas` is used.

Exit codes:

- `0`: all Claims were verified as true.
- `1`: at least one Claim was verified as false.
- `2`: an input file was missing.
- `3`: model conversion, formula generation, or solving failed.
