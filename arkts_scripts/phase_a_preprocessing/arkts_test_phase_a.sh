#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <project_name>" >&2
  exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
PROJECT_NAME=$1
PROJECT_DIR="$REPO_ROOT/arkts_projects/automated_reduced_projects/$PROJECT_NAME"
REPORT_DIR="$REPO_ROOT/data/arkts_preprocessing/$PROJECT_NAME"
REPORT="$REPORT_DIR/phase_a_report.md"

cd "$REPO_ROOT"
python3 -m unittest discover -s arkts_tests/phase_a_preprocessing -p 'test_*.py'

test -s "$PROJECT_DIR/callgraph.txt"
test -f "$PROJECT_DIR/trusted.txt"
test -f "$PROJECT_DIR/untrusted.jsonl"
grep -q '@kit.ArkData' "$PROJECT_DIR/trusted.txt"
if grep -q '@kit.ArkData' "$PROJECT_DIR/untrusted.jsonl"; then
  echo "Error: @kit.ArkData was classified as untrusted" >&2
  exit 1
fi
if grep -Ev '^[MC]:' "$PROJECT_DIR/callgraph.txt" | grep -q .; then
  echo "Error: callgraph.txt contains a non-compatible line" >&2
  exit 1
fi

BUILD_RESULT=$("$SCRIPT_DIR/arkts_merge_source.sh" "$PROJECT_NAME")
CALL_LINES=$(grep -c '^M:' "$PROJECT_DIR/callgraph.txt" || true)
CLASS_LINES=$(grep -c '^C:' "$PROJECT_DIR/callgraph.txt" || true)
TRUSTED_LINES=$(grep -c . "$PROJECT_DIR/trusted.txt" || true)
UNTRUSTED_LINES=$(grep -c . "$PROJECT_DIR/untrusted.jsonl" || true)
COMMIT=$(git -C "$REPO_ROOT/arkts_projects/original_projects/$PROJECT_NAME" rev-parse HEAD 2>/dev/null || echo unknown)

mkdir -p "$REPORT_DIR"
cat > "$REPORT" <<EOF
# Phase A: ArkTS preprocessing and dependency reduction

## Subject

- Project: $PROJECT_NAME
- Commit: $COMMIT

## Outputs

- callgraph.txt method edges: $CALL_LINES
- callgraph.txt class/module edges: $CLASS_LINES
- trusted.txt entries: $TRUSTED_LINES
- untrusted.jsonl entries: $UNTRUSTED_LINES

## Tests

- Python unit tests: PASS
- Output compatibility checks: PASS
- @kit.ArkData whitelist check: PASS
- Reduced-project build: $(printf '%s\n' "$BUILD_RESULT" | grep 'BUILD_STATUS=' | tail -1)

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
EOF

echo "$BUILD_RESULT"
echo "Phase-A report saved to $REPORT"

