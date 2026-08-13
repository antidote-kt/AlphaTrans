# Phase A: ArkTS preprocessing and dependency reduction

## Subject

- Project: RdbPlus
- Commit: 0826aee20e48dc8b3f94e22275118ed4db80c400

## Outputs

- callgraph.txt method edges: 797
- callgraph.txt class/module edges: 100
- trusted.txt entries: 37
- untrusted.jsonl entries: 1

## Tests

- Python unit tests: PASS
- Output compatibility checks: PASS
- @kit.ArkData whitelist check: PASS
- Reduced-project build: BUILD_STATUS=PASS

## Differences from Java AlphaTrans

- ArkAnalyzer exports ArkIR for ArkTS production and test sources directly; no main, test, or merged JAR is produced.
- The generator walks ArkIR method bodies and records direct call sites, matching the role of JavaCG; it does not use CHA or RTA.
- callgraph.txt keeps AlphaTrans M:/C: line format. Its M/I/O/S/D letters carry ArkIR call-expression meanings rather than JVM-instruction meanings.
- Module-level ArkTS functions are represented with their source module as owner.
- C: records include module dependencies as well as class dependencies.
- The reducer resolves SDK declarations, scans oh-package manifests, locates ArkTS declarations with ohos-typescript AST, and propagates removal through callgraph.txt.

## Known limitations

- HarmonyOS SDK call targets are less precise when OHOS_SDK_HOME is not configured.
- ArkAnalyzer 1.0.90 reports ArkAliasTypeDefineStmt as an unhandled statement; this statement is a type-alias definition rather than a call site.
- Third-party references outside safely located class, method, or function ranges remain reported in untrusted.jsonl instead of being force-deleted.
