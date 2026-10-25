# Stage 2: Network elements, NBI and fault injection

What it does: four simulated optical nodes in a ring. Each one is
configured and monitored through a REST northbound interface (NBI). A test
suite provisions links, injects faults, and checks that each node raises
the right alarm within a time limit.

```
          a-b               b-c
 node-a ─────────  node-b ─────────  node-c
   │ L2       L1 ─ L2              L1   │
   │                                    │ c-d
   └──────────────  node-d ─────────────┘
          d-a
```

## Pieces

### 1. Node state (`nodes/state.py`)
The behaviour of one network element, in plain Python with no web
framework, so it can be unit-tested directly.
- **Ports**: L1 and L2. Each is either free or owned by one link.
- **Links**: config (port, peer, format, OSNR) plus operational state:
  `INIT → UP / DEGRADED / DOWN`.
- **Evaluation tick**: every 0.2–0.5 s, the node recomputes BER for each
  link using the Stage 1 link model and updates alarms.
- **Alarm rules**:
  - A fiber cut raises `LOS` (critical) and sets the link to DOWN.
  - BER over the FEC limit raises `PRE_FEC_BER_EXCEEDS_THRESHOLD` (major)
    and sets the link to DEGRADED.
  - With format set to AUTO, the node steps down a modulation format
    before it alarms.
- **Alarm correlation**: LOS masks the BER alarm. With no light, a BER
  alarm is a symptom, not a cause, and showing both sends the operator
  chasing the wrong problem.
- **Deduplication**: alarms are keyed by (type, resource). A fault that
  persists over many ticks stays one alarm with a stable ID, and it clears
  automatically when the condition goes away.

### 2. NBI (`nodes/app.py`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| GET | `/ports` | Port inventory and which link owns each |
| GET/PUT/DELETE | `/links/{id}` | Read, provision or replace, delete a link |
| GET | `/alarms?resource=` | Active alarms |
| POST | `/sim/links/{id}/fiber-cut`, `/repair` | Test set: fiber faults |
| PUT | `/sim/links/{id}/osnr` | Test set: OSNR degradation |

- **PUT is idempotent**: create returns 201, replace returns 200. That's
  how config APIs like RESTCONF behave.
- **Errors are specific**:
  - 404: unknown port or link
  - 409: port already in use
  - 422: invalid body, such as a bad format or OSNR out of range
- A rejected request leaves no half-created state behind.
- **`/sim` is not part of the NBI.** It stands in for lab equipment, such
  as a variable optical attenuator or a fiber switch, that causes faults
  on demand. Keeping it separate means the device API stays honest.
- **Structured logs** (`nodes/events.py`): every state change is one JSON
  line (`LINK_PROVISIONED`, `ALARM_RAISED`, `MODULATION_CHANGED`,
  `REQUEST_REJECTED`, and so on), written to `logs/<node>.log`. Stage 3
  parses these.

### 3. Deployment (`Dockerfile`, `docker-compose.yml`)
- There is one image, and each container gets its identity from
  environment variables (`NODE_ID`, `PORTS`). The host maps them to ports
  8001–8004, and logs go to a shared `./logs` volume.
- The tests also run without Docker: by default they start the four nodes
  as local processes. Set `NBI_URLS` to run the same tests against the
  containers instead. Same tests, different test bed.

### 4. Verification toolkit (`verification/`)
This is kept separate from the device code, the way a real test framework
is separate from the product.
- `nbi_client.py`: a typed wrapper around the REST calls. A 4xx/5xx
  response raises an exception, so a test can't quietly ignore an error.
- `waits.py`: `wait_for(condition, timeout_s)`. A device reacts
  asynchronously, so checking straight after an action is flaky, and a
  fixed sleep is either slow or too short. Polling with a deadline is
  both fast and reliable.
- `topology.py`: the ring, plus span-level actions. Provisioning a span
  configures both ends. A fiber cut also hits both ends, like a real
  backhoe.

## Tests (30 new, 83 total, about 12 s)

| File | What it verifies |
|---|---|
| `test_node_state.py` | State machine with no HTTP: turn-up, port conflicts, LOS raise and clear, no duplicate alarms, BER alarm, LOS masking, AUTO step-down, delete clears alarms |
| `nbi/test_provisioning.py` | Functional: health, port inventory, provision → UP, AUTO picks 16-QAM, idempotent PUT, delete frees the port, 4 invalid requests rejected with the right code, port conflict, full ring comes up clean |
| `nbi/test_fault_injection.py` | Fiber cut → LOS on **both** ends within 3 s, repair clears it, OSNR drop → BER alarm on a fixed format, AUTO steps 16-QAM → 8-QAM → QPSK → alarm, LOS masks BER, alarm ID stays stable, two simultaneous cuts stay isolated |

Every fault test checks three things:
1. The right alarm appears on the right resource, in time.
2. **No stray alarms** appear anywhere else (fault isolation).
3. The alarm **clears** once the fault is fixed.

**Proof the tests catch bugs:** when I deliberately broke the LOS masking
rule, `test_fiber_cut_masks_ber_alarm` failed with
`timed out after 3.0s waiting for ['LOS'] on node-a/a-b`.

## Questions you might get

- **Why poll instead of subscribing to notifications?** Polling is
  simpler and enough here. Real gear also pushes notifications (NETCONF,
  gNMI streaming, SNMP traps). A next step would be a notification
  endpoint and a test that the alarm arrives without polling.
- **How did you pick the 3 s timeout?** It's much longer than the
  evaluation tick (0.2 s locally, 0.5 s in Docker), so slow CI machines
  don't fail by accident, and still short enough that a node that never
  alarms fails quickly. In a real test plan, that number comes from the
  product spec, such as "LOS reported within 100 ms".
- **Why can't tests affect each other?** An autouse fixture wipes every
  link before and after each test, so each test starts from a clean
  network and can run in any order.
- **What isn't modelled?** Protection switching (moving traffic to a
  backup path after a cut), propagation of alarms between nodes, and real
  timing.
- **How does this map to SVT/PV work?** It's the same test pattern: a
  device under test, its management interface, a test set that injects
  faults, automated pass/fail checks with timing criteria, and logs kept
  for triage.
