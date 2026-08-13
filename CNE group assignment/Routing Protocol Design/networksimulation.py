
# Simulation: Standard OSPF vs OSPF-RA (Rapid and Authenticated)


import networkx as nx
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import hashlib
import hmac
import time
import random
from dataclasses import dataclass, field
from collections import deque

# NETWORK TOPOLOGY CONFIGURATION

TOPOLOGY = [
    ("R1", "R2", {"base_cost": 10, "bandwidth": 100}),
    ("R2", "R3", {"base_cost": 10, "bandwidth": 100}),
    ("R1", "R4", {"base_cost": 20, "bandwidth":  50}),
    ("R4", "R5", {"base_cost": 20, "bandwidth":  50}),
    ("R5", "R6", {"base_cost": 20, "bandwidth":  50}),
    ("R3", "R6", {"base_cost": 10, "bandwidth": 100}),
]

FAILED_ROUTER = "R3"
SOURCE        = "R1"
DESTINATION   = "R6"
DOMAIN_KEY    = b"shared_secret_domain_key_2026"

# Standard OSPF Timing Parameters
OSPF_HELLO_INTERVAL = 10   
OSPF_DEAD_INTERVAL  = 40   

# Proposed OSPF-RA Protocol Extensions
RAPID_HELLO_INTERVAL = 1    
RAPID_THRESHOLD      = 2    
RECOVERY_THRESHOLD   = 5    
MAX_RAPID_ATTEMPTS   = 5    
LPS_WEIGHT_SUCCESS   = 0.7  
LPS_WEIGHT_LATENCY   = 0.3  
REFERENCE_RTT        = 10.0 
RVF_MAX_AGE          = 60   
SLIDING_WINDOW_N     = 10   

_SEP = "|"

# NEIGHBOR HEALTH STATE TABLE MECHANISMS

@dataclass
class HelloRecord:
    success:       bool
    rtt_ms:        float
    latency_score: float   

@dataclass
class NeighborState:
    neighbor_id:    str
    lps:            float = 1.0
    miss_counter:   int   = 0
    hello_interval: float = float(OSPF_HELLO_INTERVAL)
    last_hello_ts:  float = 0.0
    mode:           str   = "NORMAL"
    recovery_count: int   = 0
    hello_log: deque = field(
        default_factory=lambda: deque(maxlen=SLIDING_WINDOW_N)
    )

    def record_hello(self, success: bool, rtt_ms: float):
        """Records hello outcome and computes the non-linear latency score per entry."""
        ls = min(1.0, REFERENCE_RTT / rtt_ms) if rtt_ms > 0 else 1.0
        self.hello_log.append(HelloRecord(success=success,
                                          rtt_ms=rtt_ms,
                                          latency_score=ls))

    def compute_lps(self) -> float:
        """Derives the running composite Link Performance Score across the sliding window."""
        if not self.hello_log:
            return 1.0
        n             = len(self.hello_log)
        success_rate  = sum(1 for r in self.hello_log if r.success) / n
        avg_lat_score = sum(r.latency_score for r in self.hello_log) / n
        self.lps = round(
            LPS_WEIGHT_SUCCESS * success_rate + LPS_WEIGHT_LATENCY * avg_lat_score,
            4
        )
        return self.lps

    def update_miss_counter(self, responded: bool):
        """Drives protocol mode adjustments based strictly on discrete packet loss tracking."""
        if responded:
            self.miss_counter = 0
            if self.mode == "RAPID":
                self.recovery_count += 1
                if self.recovery_count >= RECOVERY_THRESHOLD:
                    self.mode           = "NORMAL"
                    self.hello_interval = OSPF_HELLO_INTERVAL
                    self.recovery_count = 0
        else:
            self.miss_counter += 1
            if self.miss_counter >= RAPID_THRESHOLD and self.mode == "NORMAL":
                self.mode           = "RAPID"
                self.hello_interval = RAPID_HELLO_INTERVAL
        self.compute_lps()

# TOPOLOGICAL CONVERGENCE SIMULATION

def build_graph(failed_router=None):
    G = nx.Graph()
    for u, v, data in TOPOLOGY:
        if failed_router in (u, v):
            continue
        G.add_edge(u, v, **data)
    for node in ["R1", "R2", "R3", "R4", "R5", "R6"]:
        if node not in G:
            G.add_node(node)
    return G

def ospf_convergence_time():
    detection = OSPF_DEAD_INTERVAL
    return detection, detection + 2.0 + 1.0

def ospf_ra_convergence_time():
    phase1    = RAPID_THRESHOLD    * OSPF_HELLO_INTERVAL
    phase2    = MAX_RAPID_ATTEMPTS * RAPID_HELLO_INTERVAL
    detection = phase1 + phase2
    return detection, detection + 2.0 + 1.0

def simulate_convergence():
    failure_time = 50
    sim_duration = 120

    ospf_det,    ospf_total    = ospf_convergence_time()
    ospf_ra_det, ospf_ra_total = ospf_ra_convergence_time()

    ospf_conv_at    = failure_time + ospf_total
    ospf_ra_conv_at = failure_time + ospf_ra_total

    timeline      = list(range(sim_duration + 1))
    ospf_state    = []
    ospf_ra_state = []

    for t in timeline:
        if t < failure_time:
            ospf_state.append(0)
            ospf_ra_state.append(0)
        elif t < ospf_conv_at:
            ospf_state.append(1)
            ospf_ra_state.append(1 if t < ospf_ra_conv_at else 2)
        else:
            ospf_state.append(2)
            ospf_ra_state.append(2)

    return {
        "timeline":               timeline,
        "ospf_state":             ospf_state,
        "ospf_ra_state":          ospf_ra_state,
        "failure_time":           failure_time,
        "ospf_converged_at":      ospf_conv_at,
        "ospf_ra_converged_at":   ospf_ra_conv_at,
        "ospf_detection":         ospf_det,
        "ospf_ra_detection":      ospf_ra_det,
        "ospf_convergence":       ospf_total,
        "ospf_ra_convergence":    ospf_ra_total,
        "trace_failure":          _rapid_hello_trace(recover_at=None),
        "trace_recovery":         _rapid_hello_trace(recover_at=2),
    }

def _rapid_hello_trace(recover_at):
    log    = []
    missed = 0
    t      = 0

    while missed < RAPID_THRESHOLD:
        t      += OSPF_HELLO_INTERVAL
        missed += 1
        log.append((t, "NORMAL", f"Hello sent -- no response. miss_counter={missed}"))

    log.append((t, "NORMAL",
                f"miss_counter={missed} >= RAPID_THRESHOLD={RAPID_THRESHOLD} "
                f"-> switching to RAPID mode (interval={RAPID_HELLO_INTERVAL}s)"))

    if recover_at is not None:
        total_attempts = (recover_at - 1) + RECOVERY_THRESHOLD
    else:
        total_attempts = MAX_RAPID_ATTEMPTS

    attempt        = 0
    recovery_count = 0

    while attempt < total_attempts:
        t       += RAPID_HELLO_INTERVAL
        attempt += 1
        responds = (recover_at is not None and attempt >= recover_at)

        if responds:
            recovery_count += 1
            log.append((t, "RAPID",
                        f"Attempt {attempt}: neighbour RESPONDED. "
                        f"recovery_count={recovery_count}/{RECOVERY_THRESHOLD}"))
            if recovery_count >= RECOVERY_THRESHOLD:
                log.append((t, "RAPID",
                            f"recovery_count={recovery_count} >= RECOVERY_THRESHOLD={RECOVERY_THRESHOLD} "
                            f"-> returning to NORMAL mode"))
                break
        else:
            log.append((t, "RAPID", f"Attempt {attempt}: no response. miss_counter increments"))
            if attempt >= MAX_RAPID_ATTEMPTS and recover_at is None:
                log.append((t, "RAPID",
                            f"MAX_RAPID_ATTEMPTS={MAX_RAPID_ATTEMPTS} exhausted "
                            f"-- neighbour declared DEAD. Flooding updated LSA."))
                break

    return log

# COMPOSITE METRIC LINK PERFORMANCE SIMULATION

def simulate_lps_over_time():
    random.seed(42)
    base_cost = 10

    neighbor      = NeighborState(neighbor_id="R3")
    time_steps    = list(range(60))
    success_rates = []
    rtts          = []
    lps_values    = []
    eff_costs     = []
    modes         = []

    for t in time_steps:
        if t < 20:
            success = True
            rtt     = REFERENCE_RTT + random.uniform(-1.0, 1.0)
        elif t < 40:
            deg     = (t - 20) / 20.0
            success = random.random() > deg * 0.7
            rtt     = REFERENCE_RTT * (1 + deg * 3) + random.uniform(-1, 2)
        else:
            success = random.random() > 0.7
            rtt     = REFERENCE_RTT * 4 + random.uniform(-2, 5)

        rtt = max(rtt, 0.1)

        neighbor.record_hello(success, rtt)
        neighbor.update_miss_counter(success)

        lps = neighbor.lps
        eff = round(base_cost / lps, 2) if lps > 0 else float("inf")
        n   = len(neighbor.hello_log)
        sr  = sum(1 for r in neighbor.hello_log if r.success) / n

        success_rates.append(round(sr, 3))
        rtts.append(round(rtt, 2))
        lps_values.append(lps)
        eff_costs.append(eff)
        modes.append(neighbor.mode)

    return {
        "time_steps":      time_steps,
        "success_rates":   success_rates,
        "rtts":            rtts,
        "lps_values":      lps_values,
        "effective_costs": eff_costs,
        "modes":           modes,
        "base_cost":       base_cost,
        "window_n":        SLIDING_WINDOW_N,
    }

# CRYPTOGRAPHIC RVF SECURITY ENGINE

_rvf_cache: dict = {}

def _clear_rvf_cache():
    _rvf_cache.clear()

def _build_payload(lsa_content: str, router_id: str, timestamp: int) -> bytes:
    return f"{lsa_content}{_SEP}{router_id}{_SEP}{timestamp}".encode()

def generate_rvf(lsa_content: str, router_id: str, domain_key: bytes):
    timestamp = int(time.time())
    rvf = hmac.new(
        domain_key,
        _build_payload(lsa_content, router_id, timestamp),
        hashlib.sha256
    ).hexdigest()
    return rvf, timestamp

def verify_rvf(lsa_content: str, router_id: str, rvf: str,
               timestamp: int, domain_key: bytes, current_time: int):
    # Check-Temporal Anti-Replay Gate
    age = current_time - timestamp
    if age > RVF_MAX_AGE:
        return False, f"Replay attack -- LSA age {age}s > limit {RVF_MAX_AGE}s"

    # Check-Within-Window Duplicate RVF Cache Interception
    if rvf in _rvf_cache.get(router_id, set()):
        return False, "Replay attack -- duplicate RVF in cache (fresh timestamp but already seen)"

    # Check-HMAC Cryptographic Integrity Signature Verification
    expected = hmac.new(
        domain_key,
        _build_payload(lsa_content, router_id, timestamp),
        hashlib.sha256
    ).hexdigest()
    if rvf != expected:
        return False, "RVF mismatch -- LSA falsification detected"

    _rvf_cache.setdefault(router_id, set()).add(rvf)
    return True, "RVF verified successfully"

def simulate_rvf_security():
    _clear_rvf_cache()
    results      = []
    current_time = int(time.time())

    router_id   = "R3"
    lsa_content = "R3:links=[R2:cost=10,R6:cost=10]"

    # Scenario-Legitimate Path
    rvf, ts = generate_rvf(lsa_content, router_id, DOMAIN_KEY)
    valid, reason = verify_rvf(lsa_content, router_id, rvf, ts, DOMAIN_KEY, current_time)
    results.append({"scenario": "Legitimate LSA from R3", "valid": valid, "reason": reason})

    # Scenario-Tampered Payload Signature Validation Attack
    tampered  = "R3:links=[R2:cost=1,R6:cost=1]"
    bad_key   = b"attacker_guessed_key"
    t_rvf     = hmac.new(bad_key, _build_payload(tampered, router_id, ts), hashlib.sha256).hexdigest()
    valid, reason = verify_rvf(tampered, router_id, t_rvf, ts, DOMAIN_KEY, current_time)
    results.append({"scenario": "Tampered LSA (wrong-key RVF)", "valid": valid, "reason": reason})

    # Scenario-Architectural Historic Message Replay Attack
    old_ts  = current_time - 120
    old_rvf = hmac.new(DOMAIN_KEY, _build_payload(lsa_content, router_id, old_ts), hashlib.sha256).hexdigest()
    valid, reason = verify_rvf(lsa_content, router_id, old_rvf, old_ts, DOMAIN_KEY, current_time)
    results.append({"scenario": "Old replayed LSA (timestamp expired)", "valid": valid, "reason": reason})

    # Scenario-Fresh Sliding-Window Replay Cache Attack Vector
    fresh_ts  = current_time - 5
    fresh_rvf = hmac.new(DOMAIN_KEY, _build_payload(lsa_content, router_id, fresh_ts), hashlib.sha256).hexdigest()
    _rvf_cache.setdefault(router_id, set()).add(fresh_rvf)
    valid, reason = verify_rvf(lsa_content, router_id, fresh_rvf, fresh_ts, DOMAIN_KEY, current_time)
    results.append({"scenario": "Fresh replayed LSA (RVF cache hit)", "valid": valid, "reason": reason})

    return results

# COMPARATIVE EDGE SHORT-PATH ROUTING DECISIONS

def get_routing_paths():
    G_before = build_graph(failed_router=None)
    for u, v, d in TOPOLOGY:
        if G_before.has_edge(u, v):
            G_before[u][v]["weight"] = d["base_cost"]
    path_before = nx.shortest_path(G_before, SOURCE, DESTINATION, weight="weight")
    cost_before = nx.shortest_path_length(G_before, SOURCE, DESTINATION, weight="weight")

    G_after = build_graph(failed_router=FAILED_ROUTER)

    # Standard OSPF Cost Modeling
    for u, v in G_after.edges():
        G_after[u][v]["weight"] = G_after[u][v]["base_cost"]
    path_ospf = nx.shortest_path(G_after, SOURCE, DESTINATION, weight="weight")
    cost_ospf = nx.shortest_path_length(G_after, SOURCE, DESTINATION, weight="weight")

    # OSPF-RA Composite Metrics Allocation
    link_lps = {frozenset(["R4", "R5"]): 0.6}
    for u, v in G_after.edges():
        lps = link_lps.get(frozenset([u, v]), 1.0)
        G_after[u][v]["eff_weight"] = round(G_after[u][v]["base_cost"] / lps, 4)
    path_ra = nx.shortest_path(G_after, SOURCE, DESTINATION, weight="eff_weight")
    cost_ra = nx.shortest_path_length(G_after, SOURCE, DESTINATION, weight="eff_weight")

    return {
        "path_before": path_before, "cost_before": cost_before,
        "path_ospf":   path_ospf,   "cost_ospf":   cost_ospf,
        "path_ra":     path_ra,     "cost_ra":     cost_ra,
        "link_lps":    {f"{sorted(k)[0]}-{sorted(k)[1]}": v for k, v in link_lps.items()},
    }


def plot_all(conv_data, lps_data, rvf_results, path_data):
  
# FIGURE 1

    fig1 = plt.figure(num="Figure 1: Performance Trends", figsize=(18, 12))
    fig1.suptitle(
        "OSPF vs OSPF-RA: Simulation Performance Metrics",
        fontsize=14, fontweight="bold", y=0.98,
    )
    
    gs1 = gridspec.GridSpec(2, 3, figure=fig1, hspace=0.45, wspace=0.35)

    # Subplot-Convergence Timeline Trace
    ax1 = fig1.add_subplot(gs1[0, :2])
    ft   = conv_data["failure_time"]
    oct_ = conv_data["ospf_converged_at"]
    tct  = conv_data["ospf_ra_converged_at"]

    ax1.axvline(ft,   color="red",       linestyle="--", linewidth=1.5, label=f"R3 fails (t={ft}s)")
    ax1.axvline(oct_, color="steelblue", linestyle=":",  linewidth=1.5, label=f"OSPF converges (t={oct_}s)")
    ax1.axvline(tct,  color="seagreen",  linestyle=":",  linewidth=1.5, label=f"OSPF-RA converges (t={tct}s)")
    ax1.axvspan(ft, oct_, alpha=0.10, color="steelblue", label=f"OSPF outage ({conv_data['ospf_convergence']}s)")
    ax1.axvspan(ft, tct,  alpha=0.18, color="seagreen", label=f"OSPF-RA outage ({conv_data['ospf_ra_convergence']}s)")
    
    rapid_start = ft + RAPID_THRESHOLD * OSPF_HELLO_INTERVAL
    ax1.axvspan(rapid_start, tct, alpha=0.28, color="gold", label=f"Rapid hello phase ({MAX_RAPID_ATTEMPTS}s)")
    ax1.text(rapid_start + 0.4, 0.55, "Rapid\nmode", fontsize=7, color="goldenrod", va="center")
    
    ax1.set_xlim(0, 120)
    ax1.set_ylim(0, 1)
    ax1.set_xlabel("Time (seconds)")
    ax1.set_title("Convergence Timeline After Router Failure", fontweight="bold")
    ax1.legend(fontsize=8, loc="upper right")
    ax1.set_yticks([])
    ax1.grid(axis="x", alpha=0.3)

    # Subplot-Convergence Delta Performance Comparison Bar Chart
    ax2 = fig1.add_subplot(gs1[0, 2])
    protocols   = ["Standard OSPF", "OSPF-RA"]
    det_times   = [conv_data["ospf_detection"],   conv_data["ospf_ra_detection"]]
    extra_times = [conv_data["ospf_convergence"]  - conv_data["ospf_detection"],
                   conv_data["ospf_ra_convergence"] - conv_data["ospf_ra_detection"]]
    
    bars1 = ax2.bar(protocols, det_times, color=["steelblue", "seagreen"], label="Detection time")
    bars2 = ax2.bar(protocols, extra_times, bottom=det_times, color=["lightsteelblue", "lightgreen"], label="Flood + SPF time")
    
    for bar, val in zip(bars1, det_times):
        ax2.text(bar.get_x() + bar.get_width() / 2, val / 2, f"{val}s", ha="center", va="center", fontsize=9, fontweight="bold", color="white")
    totals = [conv_data["ospf_convergence"], conv_data["ospf_ra_convergence"]]
    for bar, tot in zip(bars2, totals):
        ax2.text(bar.get_x() + bar.get_width() / 2, tot + 0.4, f"Total: {tot}s", ha="center", va="bottom", fontsize=9, fontweight="bold")
        
    ax2.set_ylabel("Time (seconds)")
    ax2.set_title("Convergence Time Comparison", fontweight="bold")
    ax2.legend(fontsize=8)
    ax2.grid(axis="y", alpha=0.3)

    # Subplot-LPS Sliding Window Variable Performance Tracking
    ax3 = fig1.add_subplot(gs1[1, :2])
    ts   = lps_data["time_steps"]
    lpsv = lps_data["lps_values"]
    srv  = lps_data["success_rates"]

    ax3.plot(ts, lpsv, color="darkorange", linewidth=2, label=f"LPS (sliding window N={lps_data['window_n']}, per-Hello latency)")
    ax3.plot(ts, srv,  color="gray", linewidth=1, linestyle="--", alpha=0.7, label="Window Hello success rate")
    ax3.axhline(0.7, color="red", linestyle=":", linewidth=1.2, label="LPS=0.7 reference")
    ax3.fill_between(ts, lpsv, alpha=0.12, color="darkorange")
    ax3.axvspan(0,  20, alpha=0.05, color="green",  label="Healthy phase")
    ax3.axvspan(20, 40, alpha=0.07, color="orange", label="Degradation phase")
    ax3.axvspan(40, 60, alpha=0.07, color="red",    label="Critical phase")

    in_rapid = False
    r_start  = None
    for t_, m in zip(ts, lps_data["modes"]):
        if m == "RAPID" and not in_rapid:
            r_start, in_rapid = t_, True
        elif m == "NORMAL" and in_rapid:
            ax3.axvspan(r_start, t_, alpha=0.20, color="gold")
            in_rapid = False
    if in_rapid:
        ax3.axvspan(r_start, ts[-1], alpha=0.20, color="gold", label="Rapid hello active (miss_counter driven)")

    ax3.set_xlabel("Time (seconds)")
    ax3.set_ylabel("Score (0-1)")
    ax3.set_title(f"Link Performance Score on R2-R3 (Sliding Window Profile)", fontweight="bold")
    ax3.set_ylim(-0.05, 1.15)
    ax3.legend(fontsize=7, loc="lower left", ncol=2)
    ax3.grid(alpha=0.3)

    # Subplot-Dynamic Base-Metric Cost Inflation Scaling
    ax4 = fig1.add_subplot(gs1[1, 2])
    capped = [min(c, 60) for c in lps_data["effective_costs"]]
    ax4.plot(ts, capped, color="purple", linewidth=2, label="Effective cost (base/LPS)")
    ax4.axhline(lps_data["base_cost"], color="gray", linestyle="--", linewidth=1, label=f"Base cost ({lps_data['base_cost']})")
    ax4.fill_between(ts, lps_data["base_cost"], capped, where=[c > lps_data["base_cost"] for c in capped], alpha=0.15, color="purple", label="Cost penalty vs base")
    
    ax4.set_xlabel("Time (seconds)")
    ax4.set_ylabel("Effective Cost")
    ax4.set_title("Effective Link Cost (Base Cost / LPS)", fontweight="bold")
    ax4.legend(fontsize=8)
    ax4.grid(alpha=0.3)
    
    fig1.savefig("simulation_performance_trends.png", dpi=150, bbox_inches="tight", facecolor="white")
    print("  Performance Trends plot saved -> simulation_performance_trends.png")

    # FIGURE 2
    
    fig2 = plt.figure(num="Figure 2: Network Routing Topology Graph", figsize=(18, 7))
    fig2.suptitle(
        "OSPF-RA: Trust Layer Architecture and Graph Topology Routing Map",
        fontsize=14, fontweight="bold", y=0.96,
    )
    
    gs2 = gridspec.GridSpec(1, 3, figure=fig2, wspace=0.40)

    # Subplot-Security Matrix Matrix Representation
    ax5 = fig2.add_subplot(gs2[0, :2])
    ax5.axis("off")
    ax5.set_title("RVF Security Verification Results (4 scenarios)", fontweight="bold", pad=10)
    
    col_labels  = ["Scenario", "Result", "Reason"]
    table_data  = []
    cell_colors = []
    
    for r in rvf_results:
        label = "ACCEPTED" if r["valid"] else "REJECTED"
        table_data.append([r["scenario"], label, r["reason"]])
        rc = (["#f0fff0", "#d4edda", "#f0fff0"] if r["valid"] else ["#fff0f0", "#f8d7da", "#fff0f0"])
        cell_colors.append(rc)
        
    tbl = ax5.table(cellText=table_data, colLabels=col_labels, cellLoc="left", loc="center", cellColours=cell_colors)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.5)
    tbl.scale(1, 2.2)
    tbl.auto_set_column_width([0, 1, 2])

    # Subplot-Topographic Connectivity Infrastructure Mapping
    ax6 = fig2.add_subplot(gs2[0, 2])
    G_d = nx.Graph()
    for u, v, d in TOPOLOGY:
        G_d.add_edge(u, v, base_cost=d["base_cost"])
        
    pos = {"R1": (0,1), "R2": (1,1), "R3": (2,1), "R4": (0,0), "R5": (1,0), "R6": (2,0)}
    nc = ["#e84545" if n == FAILED_ROUTER else "steelblue" for n in G_d.nodes()]
    
    nx.draw_networkx_nodes(G_d, pos, ax=ax6, node_color=nc, node_size=700, alpha=0.92)
    nx.draw_networkx_labels(G_d, pos, ax=ax6, font_color="white", font_weight="bold", font_size=9)
    
    ne = [(u,v) for u,v in G_d.edges() if FAILED_ROUTER not in (u,v)]
    fe = [(u,v) for u,v in G_d.edges() if FAILED_ROUTER     in (u,v)]
    
    nx.draw_networkx_edges(G_d, pos, edgelist=ne, ax=ax6, edge_color="steelblue", width=2, alpha=0.7)
    nx.draw_networkx_edges(G_d, pos, edgelist=fe, ax=ax6, edge_color="#e84545", width=2, style="dashed")
    
    nx.draw_networkx_edge_labels(
        G_d, pos,
        edge_labels={(u,v): f"c={d['base_cost']}" for u,v,d in TOPOLOGY},
        ax=ax6, font_size=7
    )
    ax6.set_title(f"Network Graph Layout Topology\n(Red Node = {FAILED_ROUTER} Failure)", fontweight="bold")
    ax6.axis("off")

    fig2.savefig("simulation_security_topology.png", dpi=150, bbox_inches="tight", facecolor="white")
    print("  Security and Topology plot saved -> simulation_security_topology.png")
    
    plt.show()

# RUNTIME ENTRY SIMULATION CONTROL INTERFACE

def main():
    SEP = "=" * 65
    print(SEP)
    print("OSPF vs OSPF-RA Simulation")
    print(SEP)

    # 1. Convergence Metrics Analysis
    print("\n[1] CONVERGENCE SIMULATION")
    print("-" * 45)
    conv = simulate_convergence()
    print(f"  Router {FAILED_ROUTER} fails at t = {conv['failure_time']}s")
    print(f"\n  Standard OSPF:")
    print(f"    Detection  : {conv['ospf_detection']}s  (full Dead Interval = 4xHello)")
    print(f"    Total      : {conv['ospf_convergence']}s")
    print(f"    Converged  : t = {conv['ospf_converged_at']}s")
    print(f"\n  OSPF-RA (Rapid Hello):")
    print(f"    Phase 1    : {RAPID_THRESHOLD} missed x {OSPF_HELLO_INTERVAL}s = {RAPID_THRESHOLD * OSPF_HELLO_INTERVAL}s  (normal mode)")
    print(f"    Phase 2    : {MAX_RAPID_ATTEMPTS} rapid x {RAPID_HELLO_INTERVAL}s = {MAX_RAPID_ATTEMPTS * RAPID_HELLO_INTERVAL}s  (rapid mode)")
    print(f"    Detection  : {conv['ospf_ra_detection']}s")
    print(f"    Total      : {conv['ospf_ra_convergence']}s")
    print(f"    Converged  : t = {conv['ospf_ra_converged_at']}s")
    saved = conv["ospf_convergence"] - conv["ospf_ra_convergence"]
    pct   = round(saved / conv["ospf_convergence"] * 100, 1)
    print(f"\n  Improvement : {saved}s faster  ({pct}% outage reduction)")

    print(f"\n  [1b] State-machine trace -- FULL FAILURE path:")
    for tick, mode, event in conv["trace_failure"]:
        print(f"    t+{tick:>3}s [{mode:>6}]  {event}")

    print(f"\n  [1c] State-machine trace -- RECOVERY path:")
    for tick, mode, event in conv["trace_recovery"]:
        print(f"    t+{tick:>3}s [{mode:>6}]  {event}")

    # 2. Sliding Window LPS Simulation Matrix
    print(f"\n[2] LINK PERFORMANCE SCORE  ( window N={SLIDING_WINDOW_N})")
    print("-" * 55)
    lps_data = simulate_lps_over_time()
    hdr = f"  {'Time':>5}  {'Win SR':>7}  {'RTT(ms)':>9}  {'LPS':>7}  {'Eff Cost':>9}  {'Mode':>7}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for t in [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 59]:
        mark = " <- RAPID" if lps_data["modes"][t] == "RAPID" else ""
        print(f"  {t:>5}s  {lps_data['success_rates'][t]:>7.3f}  "
              f"{lps_data['rtts'][t]:>9.1f}  {lps_data['lps_values'][t]:>7.4f}  "
              f"{min(lps_data['effective_costs'][t], 999):>9.2f}  "
              f"{lps_data['modes'][t]:>7}{mark}")

    # 3. Routing Layer Cost Engine Processing Paths
    print(f"\n[3] ROUTING PATH COMPARISON  ({SOURCE} -> {DESTINATION})")
    print("-" * 45)
    paths = get_routing_paths()
    print(f"  Before failure:")
    print(f"    {' -> '.join(paths['path_before'])}  (base cost: {paths['cost_before']})")
    print(f"\n  After {FAILED_ROUTER} failure -- Standard OSPF:")
    print(f"    {' -> '.join(paths['path_ospf'])}  (base cost: {paths['cost_ospf']})")
    print(f"\n  After {FAILED_ROUTER} failure -- OSPF-RA (effective cost):")
    for lnk, lv in paths["link_lps"].items():
        print(f"    Link {lnk}: LPS={lv} -> eff cost = {round(20/lv,2)} (vs base 20)")
    print(f"    {' -> '.join(paths['path_ra'])}  (eff cost: {round(paths['cost_ra'],2)})")

    # 4. HMAC Cryptographic Vector Validations
    print(f"\n[4] RVF SECURITY VERIFICATION  ( 4 scenarios)")
    print("-" * 45)
    rvf_results = simulate_rvf_security()
    for i, r in enumerate(rvf_results, 1):
        status = "ACCEPTED" if r["valid"] else "REJECTED"
        print(f"  [{i}] {r['scenario']}")
        print(f"      Result : {status}")
        print(f"      Reason : {r['reason']}")
        print()

    # 5. Image Generation Interface Execution
    print("[5] GENERATING SEPARATED MULTI-WINDOW PLOTS ...")
    plot_all(conv, lps_data, rvf_results, paths)
    print("\nDone.")
    print(SEP)

if __name__ == "__main__":
    main()
