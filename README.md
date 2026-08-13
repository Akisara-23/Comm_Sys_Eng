# Comm_Sys_Eng — CNE Group Assignment (ElectroSquad)

This repository contains group work by "ElectroSquad" for EN2150 (Communication Systems Engineering). It includes network design reports, Cisco Packet Tracer topology files, and a Python simulation that compares standard OSPF with a proposed OSPF-RA (Rapid & Authenticated) extension.

## Table of contents
- Project overview
- Repository structure
- Files and descriptions
- Prerequisites
- Running the simulation
- Expected outputs
- Packet Tracer files
- Reports
- Notes & suggestions
- Authors / Contributors
- License (suggested)

## Project overview
The work in this repository demonstrates topology design and routing experiments for course assignments. The major deliverables are:
- Written reports (PDF) describing the design and results for separate assignments.
- Cisco Packet Tracer (.pkt) saved topologies for the university backbone and ENTC local area network.
- A Python simulation (networksimulation.py) that models OSPF behavior vs a proposed OSPF-RA variant, including:
  - Convergence timeline simulation,
  - Link Performance Score (LPS) sliding-window model,
  - HMAC-based RVF security verification scenarios,
  - Topology routing comparisons and plotted outputs.

## Repository structure
CNE group assignment/
- Routing Protocol Design/
  - EN2150_ElectroSquad_A04.pdf — Final report for routing protocol design (Assignment A04).
  - README.md — (folder-level) additional notes included by the group.
  - networksimulation.py — Python simulation comparing OSPF vs OSPF-RA (generates plots and prints summaries).
- UOM Backbone and ENTC Local Area Network/
  - ENTC_LAN.pkt — Cisco Packet Tracer file for ENTC LAN topology.
  - ElectroSquad_EN2150_A03_Report.pdf — Report for the university backbone / LAN design (Assignment A03).
  - university backbone.pkt — Cisco Packet Tracer file for the university backbone topology.

## Files and brief descriptions
- CNE group assignment/Routing Protocol Design/networksimulation.py
  - Simulation script that:
    - Builds a sample network topology.
    - Simulates failure detection & convergence for OSPF and OSPF-RA.
    - Computes Link Performance Score (LPS) using a sliding window.
    - Demonstrates a simple HMAC-based RVF verification (anti-replay + integrity).
    - Produces PNG figures: `simulation_performance_trends.png` and `simulation_security_topology.png`.
  - Console output prints convergence stats, LPS table and RVF verification scenarios.

- PDF reports
  - `EN2150_ElectroSquad_A04.pdf` and `ElectroSquad_EN2150_A03_Report.pdf` — formal writeups (design, methodology, results).

- Packet Tracer files
  - `.pkt` files are Cisco Packet Tracer topology files. Open with Cisco Packet Tracer.

## Prerequisites
- Python 3.8+ (3.10/3.11 recommended)
- Python packages:
  - networkx
  - matplotlib
- Cisco Packet Tracer (to open `.pkt` files)

Install required Python packages:
```bash
python -m pip install --upgrade pip
python -m pip install networkx matplotlib
