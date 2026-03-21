# Demo Brief Design

**Goal:** Add a one-page demo brief that the operator can use during a live advisor-facing demonstration of the H2track system.

## Scope

This document is not a technical design document and not a PPT outline. It is a compact speaking brief for the live demo itself. The audience is a thesis advisor or evaluator observing the demonstration in real time.

The brief should stay on one page in spirit: short sections, short bullets, and a clear speaking order.

## Structure

The document should have exactly four practical sections:

1. **Project Goal**
   - One concise explanation of the full closed-loop capability being demonstrated.

2. **Live Demo Flow**
   - The operator’s speaking order: prep, launch, self-check, patrol, gas detection, tracking, source finding, alarm and stop.

3. **What To Watch During The Demo**
   - The few runtime signals worth pointing out while the robot is moving.

4. **Closing Summary**
   - Three concise statements: what worked, current engineering limitations, and what the next development focus is.

## Constraints

- Keep the document concise enough for live use.
- Write for spoken delivery, not for paper reading.
- Avoid deep technical detail.
- Use the existing project terminology: `demo_prep`, `demo.launch.py`, `demo_selfcheck`, patrol, tracking, source finding.

## Deliverables

- Create `docs/demo-brief.md` with the final one-page brief.
- Add a light regression test that ensures the file exists and preserves the four required sections.

## Success Criteria

The feature is complete when:

- `docs/demo-brief.md` exists
- it contains the approved four-part structure
- the brief is clearly written for a live advisor-facing demo
- a regression test protects the section structure
