# AIDLC Core Workflow (OpenClaw port)

**PRIORITY**: This workflow OVERRIDES ad-hoc implementation for non-trivial work.

## Adaptive Principle

The workflow adapts to the work. Use full depth for medium/high complexity or ambiguous requests. Collapse gates only when the user explicitly requests a lightweight path or the work is trivial.

## Inception Phase (Planning)

Always start here for non-trivial requests.

### Gate 0 — Context Snapshot (ALWAYS)
Produce a short locked snapshot:
- Intent & success criteria
- Greenfield vs brownfield classification
- Constraints & non-negotiables
- Existing assets / code to reuse
- Explicit open questions

Present and wait for **Approve and Continue** or **Request Changes**.

### Gate 1 — Assess
- Complexity (Low / Medium / High)
- Key risks
- Dependencies
- Recommended depth of remaining gates

Present and wait for approval.

### Gate 2 — Decompose
Break into clear Units of Work with:
- Name / responsibility
- Dependencies between units
- Suggested owner (OpenClaw subagent / human)

Present and wait for approval.

### Gate 3 — Design Decisions
Capture the important architectural and design choices with short rationale. Prefer decisions that keep the system simple, secure, and aligned with existing patterns.

Present and wait for approval.

### Gate 4 — Execution Plan
Produce a concrete, sequenced plan that can be executed by agents. Include:
- Ordered steps
- Which units can run in parallel
- How OpenClaw subagents will be used
- Verification / acceptance criteria

Present and wait for approval.

## Construction Phase

Only after Gate 4 is locked:
- Implement the units
- Prefer parallel OpenClaw subagents where independent
- Keep changes small and verifiable
- Run tests / typecheck / build as appropriate
- Stop and report if a new decision is required

## Hard Constraints

- Never skip a human gate.
- Never write production code before the Execution Plan is approved.
- Prefer explicit planning mode throughout Inception (no production edits).
- This process takes precedence for non-trivial work when the OpenClaw aidlc skill is active.
- Keep the rule files under this skill `references/` editable so the user can evolve the process.
