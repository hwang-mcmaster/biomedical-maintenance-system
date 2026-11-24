# Frontend and backend completion update

## Implemented

- Four versioned recommendation categories. Low/medium/high repair intensity maps to monitoring/inspection/maintenance. Reached reference life or recorded historical maintenance cost at least equal to recorded replacement cost requests replacement review. These are provisional engineering rules, not learned failure labels or an automatic replacement decision.
- Optional Routine/Important/Critical equipment criticality, stored in PostgreSQL and editable in equipment details. Important imposes a Medium task-priority floor; Critical imposes High. A manual override cannot bypass that floor. Unknown criticality remains explicitly unknown.
- Accepted/rejected/deferred engineering reviews with fresh assessment snapshot, equipment version, actor, rationale and timestamp. Reviews do not book work or approve clinical use.
- Equipment service policies with approved interval source, qualification, duration, priority and last service date. Generation creates one pending task per equipment/due-date cycle. Completing that exact policy-generated task advances the policy and creates its next pending task atomically. Paused policies do not recur. There is no timer that books work automatically.
- Confirmed scheduled assignments can be moved/reassigned with reason and an optimistic start-time check. Started work and stale equipment are rejected. Existing database triggers enforce qualification, availability and booking conflicts. Late edits require explicit acknowledgement. Original schedule results remain immutable generation evidence; current assignments and status events record later changes.
- Completed work can be applied once to lifecycle cost totals, with an optional repair-event increment and a coordinator explanation. Routine service is not automatically counted as a repair. This updates equipment version so outdated assessment/tasks must be reviewed again.

## Required database setup

The frontend/backend require `database/migrations/006_review_workflow.sql` (formerly `backend/005_review_workflow.sql`), which adds one equipment column, two tables and one history flag and preserves existing records. It has been applied to the development database. `python -m app.migrate` applies 002–006 in order, including the authentication schema (005, formerly `backend/AUTH_DATABASE_TASKS.sql`), and records each file in `schema_migrations`.

Verify the equipment API, review controls, recurrence, reconciliation and rescheduling against that database before the demo. Existing installations without migration 005 cannot run the updated equipment/workflow queries.

## Validation and remaining work

Twelve focused backend tests pass: eight policy/schema/transaction tests and four independent scheduling-validation tests. Frontend production build, lint, account/validation/preview tests and new review/service-policy/generation/reconciliation UI tests pass. Live database acceptance tests were not rerun. These checks do not establish clinical accuracy or operational savings.

Still required outside the completed application features:

1. Bootstrap accounts if needed, then run live PostgreSQL/HTTP/browser acceptance tests against the migrated database. Include automatic next-cycle creation and simultaneous edits/confirmations.
2. AI team: decide the lifecycle target, obtain suitable representative labels, train/evaluate independently, and support additional device categories. The unchanged model is cost regression plus repair intensity, not remaining-life/failure prediction.
3. Approve the provisional recommendation and criticality policies against engineering/manufacturer guidance. A cumulative-cost ratio of 1 is a transparent review trigger, not an established replacement threshold.
4. Measure actual completed work, approved labour/parts costs, downtime and multi-day fixed-interval policy outcomes. Existing baseline comparison remains same-input single-day placement.
5. Recover the original Week 2 checklist and complete requirement-to-test traceability; carry out usability/accessibility assessment and finalize report/demo evidence.
6. Keep the AI service private and background legacy scheduling disabled. Its independent manual optimizer endpoint still exists because AI files were outside this change. It bypasses coordinator review and is not the technician-aware workflow. Remove/protect it in a separate AI-service change before any public deployment.
7. Optional further work: automatic multi-day optimization, workload balancing, server-side pagination, emailed notifications/recovery, external identity and broader concurrency/performance testing.

Historical maintenance imported before these controls may already be included in equipment aggregates. Review provenance before applying reconciliation; the software cannot infer that history reliably.
