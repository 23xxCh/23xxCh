# 2-Minute Demo Script Design

**Goal:** Add a short Chinese-only speaking script that the operator can read aloud during a live advisor-facing H2track demo.

## Scope

This document is not a technical report and not a rehearsal checklist. It is a spoken script for the operator to deliver during a live demo in roughly two minutes.

The script should stay compact, spoken in natural Chinese, and aligned with the already approved demo flow: prep, launch, self-check, patrol, hydrogen detection, tracking, source finding, alarm, and stop.

## Structure

The document should have exactly three practical sections:

1. **开场**
   - About 20 seconds.
   - Explain what the robot is, what problem the system solves, and what closed loop will be shown.

2. **演示过程**
   - About 70 seconds.
   - Follow the real operator sequence: `demo_prep`, `demo.launch.py`, `demo_selfcheck`, patrol, gas detection, tracking, obstacle avoidance, source finding, alarm, and stop.

3. **结束总结**
   - About 30 seconds.
   - State what this demo proves, what engineering limits remain, and what the next development focus is.

## Constraints

- Write the full script in Chinese.
- Keep the tone oral, short-sentence, and advisor-facing.
- Avoid deep technical detail and avoid PPT-style bullet overload inside the script body.
- Use existing project terms where needed: `demo_prep`, `demo.launch.py`, `demo_selfcheck`, 巡检, 追踪, 报警.

## Deliverables

- Create `docs/demo-script-2min.md` with the final script.
- Add a light regression test that ensures the file exists and preserves the approved three-part structure.

## Success Criteria

The feature is complete when:

- `docs/demo-script-2min.md` exists
- it contains the approved three-part structure
- the content is clearly written for spoken Chinese delivery in about two minutes
- a regression test protects the section structure and required keywords
