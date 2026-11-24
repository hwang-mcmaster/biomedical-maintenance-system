# Recorded results — 2026-11-19

## Functional validation

- **67 backend tests passed**, with PostgreSQL, AI, workflow and scale flags enabled;
  no skips in this run. See `backend-test-results.txt` for individual cases.
- Frontend production build, authenticated page/role checks, preview isolation,
  200-record pagination/filtering, 100-task cohort selection, error/session handling,
  direct edit-page loading and lint passed.
- Real React → HTTP/session/CSRF → PostgreSQL → AI assessment → reviewed task →
  technician → preview/baseline → confirmation → reload flow passed. React was
  rendered in JSDOM; browser layout was reviewed separately with labelled sample
  data. See `authenticated-ui-results.json` and `ui-comparison-preview.jpg`.
- Temporary fixture equipment, tasks, technicians, schedules and accounts were
  cleaned up. Existing project credentials and records were preserved.

## Synthetic scheduling comparison

Five technicians have split availability, mixed qualifications, task durations
30/45/60/90 minutes and a known booking. Priorities are explicitly synthetic test
labels. Both strategies receive identical inputs. Each timing is the mean of 20
engine runs and excludes DB, AI and HTTP time.

| Inventory / cohort | Order | Assigned | Unassigned | High priority within target | Selected utilization | Conflicts | Mean engine ms |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 50 | Risk | 36 | 14 | 7 | 95.00% | 0 | 0.842 |
| 50 | Fixed interval | 39 | 11 | 6 | 86.43% | 0 | 0.850 |
| 100 | Risk | 41 | 59 | 15 | 95.00% | 0 | 1.582 |
| 100 | Fixed interval | 49 | 51 | 4 | 88.57% | 0 | 1.683 |
| 200 / first 100 | Risk | 41 | 59 | 15 | 95.00% | 0 | 1.637 |
| 200 / first 100 | Fixed interval | 49 | 51 | 4 | 88.57% | 0 | 1.771 |
| 200 / second 100 | Risk | 39 | 61 | 15 | 94.29% | 0 | 1.644 |
| 200 / second 100 | Fixed interval | 49 | 51 | 4 | 88.57% | 0 | 1.755 |

Risk ordering places more high-priority work within target in these scenarios.
Due-date ordering places more tasks overall, including shorter tasks. Neither
heuristic is globally optimal. The 200-record cohorts are **independent capacity
experiments**, not two sets of assignments that can be combined into one day.

Overdue intervals remain in the inputs. These numbers are planned placements,
not completed maintenance, clinical outcomes or evidence of avoided failures.
Raw inputs, full outputs, service-lateness counts and model provenance are in
`prototype-results.json`; the compact table is in `prototype-summary.csv`.

## Real PostgreSQL inventory scale

| Temporary records | Total inventory including existing item | Authenticated list API ms | JSON response bytes |
| ---: | ---: | ---: | ---: |
| 50 | 51 | 277.47 | 34,287 |
| 100 | 101 | 270.50 | 68,017 |
| 200 | 201 | 290.81 | 135,477 |

Single observations on this machine, using in-process FastAPI requests and real
PostgreSQL. They include account/DB overhead and exclude browser/HTTP transport.
They are not a concurrent-user load test. Detail retrieval and leading-zero
serial preservation were also checked. Source: `scale-api-results.json`.

## AI interpretation

The existing model metadata reports leave-one-out MAE **147.35 CAD/year**, RMSE
**184.69 CAD/year**, R² **0.241**, on **24 synthetic records**; fleet-mean baseline
MAE is **193.14**. These values were copied for provenance and were **not
independently recomputed** by the frontend/backend work. Selection and validation
use the same small dataset, so independent representative validation is pending.

Recall, F1 and false-negative rate remain not applicable: there is no labelled
failure classifier. Relative repair intensity is not failure probability.
Workload and planned equipment downtime are estimates; approved cost inputs and
real completed-work/outcome data are still needed to validate savings.

See `../VALIDATION.md` for repeatable commands, current limits and the demo guide.
