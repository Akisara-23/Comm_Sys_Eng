# OSPF vs OSPF-RA Simulation

---

## Overview

This simulation validates the proposed OSPF-RA (Rapid and Authenticated ) protocol against standard OSPF across four demonstration areas:

1. **Rapid Failure Detection** — Adaptive Hello mechanism with miss-counter driven mode switching
2. **Link Performance Score (LPS)** — Composite routing metric using sliding-window Hello success rates and RTT latency
3. **RVF Cryptographic Integrity** — HMAC-SHA256 based LSA authentication using a shared domain key
4. **Replay Attack Prevention** — Timestamp freshness gate combined with a per-router RVF cache

---

## Requirements

### Python Version
Python **3.8 or higher** is required.


---

## Installation

### Step 1 — Download the project

---


### Step 2 — Install required libraries
```
pip install networkx matplotlib
```

---

### Step 3 - Run the Simulation


---

## Expected Output

### Console Output

The simulation prints five clearly labeled sections to the terminal:

```
=================================================================
OSPF vs OSPF-RA Simulation
=================================================================

[1] CONVERGENCE SIMULATION
[2] LINK PERFORMANCE SCORE  ( window N=10)
[3] ROUTING PATH COMPARISON  (R1 -> R6)
[4] RVF SECURITY VERIFICATION  ( 4 scenarios)
[5] GENERATING SEPARATED MULTI-WINDOW PLOTS ...
```

**Section 1** shows detection and convergence times for both protocols after router R3 fails, along with full state-machine traces for the failure and recovery paths.

**Section 2** prints a time-series table of Hello success rate, RTT, LPS value, effective cost, and operating mode across 60 simulated seconds.

**Section 3** compares the routing path selected by standard OSPF and OSPF-RA after the R3 failure, showing how effective cost influences path selection.

**Section 4** reports the result of four RVF security scenarios - legitimate LSA, tampered LSA, expired replay, and fresh duplicate replay.

**Section 5** generates and saves the plot files.

### Generated Plot Files

Two image files are saved to the same directory as the script:

| File | Contents |
|---|---|
| `simulation_performance_trends.png` | Convergence timeline, convergence time comparison bar chart, LPS sliding window profile, effective link cost over time |
| `simulation_security_topology.png` | RVF security verification results table, network graph topology with failed node highlighted |

Both figures also open in interactive matplotlib windows. Close them to fully exit the program.

---

## Configuration

Key simulation parameters are defined at the top of `networksimulation.py` and can be modified.

---

## Team

| Name | Index |
|---|---|
| Abeywarna D.H. | 230013A |
| Chandrakumara H.A.D.C. | 230100M |
| Hansindu M.M.A.D. | 230229P |
| Weerasinghe J.A.H.R. | 230697V |
