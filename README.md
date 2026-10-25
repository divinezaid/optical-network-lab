# Optical Network Verification Lab

A small simulated packet-optical network plus an automated verification
suite, built to mirror product verification work: build a test environment,
validate features, automate tests in Python, analyse logs and track defects.

## Status

| Stage | Scope | State |
|---|---|---|
| 1 | Link model: QPSK/8-QAM/16-QAM, BER vs OSNR, Monte Carlo cross-check, FEC alarm | Done |
| 2 | Node services (FastAPI + Docker), NBI, fault-injection tests | Next |
| 3 | Log parser, defect entries, HTML report, test plan | — |

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python run.py all                 # tests + HTML report (reports/) + plots (plots/)
```

`make test` / `make plots` do the same on Linux.

## Stage 1 results

![BER vs OSNR](plots/ber_vs_osnr.png)

The lines are the exact Gray-coded BER formulas. The dots are an
independent Monte Carlo simulation over AWGN, and they land on the lines
across five decades. The dashed line is the HD-FEC threshold (3.8e-3).
Where each curve crosses it gives that format's required OSNR at 32 GBaud
dual-polarisation: **QPSK 12.6 dB, 8-QAM 17.2 dB, 16-QAM 19.3 dB**.

![Constellations](plots/constellations.png)

Details and design choices: [docs/stage1-link-model.md](docs/stage1-link-model.md)

## Layout

```
linkmodel/    modulation, OSNR<->SNR, theory BER, Monte Carlo, FEC alarm logic
tests/        pytest suite (functional + model verification)
scripts/      plot generation
plots/        generated figures
nodes/        (stage 2) simulated network elements
defects/      (stage 3) defect entries as JSON
docs/         design notes and test plan
```
