# Parallel PageRank Project (Milestone 2)

## Overview
This repository contains Milestone 2 work focused on parallel and distributed PageRank computation.

The project implements and benchmarks three PageRank strategies on a real web-crawl graph:
- **Sequential**: Single-process, single-thread baseline.
- **Centralized Aggregation (Ray)**: Workers compute chunks; a centralized driver aggregates results.
- **Distributed Reduction (Ray)**: Workers compute chunks; a tree-reduction step merges results directly across workers without driver involvement.

The main goal is to evaluate the execution time, speedup, and communication overhead of these strategies under different termination policies.

## What Is Included
- Ray-based parallel PageRank implementations
- Sequential baseline PageRank for performance comparison
- Graph utility functions to build Compressed Sparse Row (CSR) representations
- Jupyter notebook with full benchmarking sweeps, degree distribution analysis, and visualizations
- Analytical results regarding Amdahl's Law and parallel efficiency

## Dataset
The PageRank algorithm processes a directed web graph (`crawl_graph.json`) generated from previous crawling stages.
- **Total Nodes**: ~1,573,482
- **Total Directed Edges**: ~7,598,137
- **Graph Format**: JSON adjacency list converted to CSR (indptr, indices, out_counts) arrays to optimize memory and access speed.

## Experimented Techniques
### 1) Sequential PageRank
A standard iterative approach running on a single thread. Used to establish the baseline execution time and rank correctness.

### 2) Centralized Aggregation (Ray)
- **Coordination**: The driver collects all worker results each iteration via `ray.get()`.
- **Data Handling**: CSR structures are pushed to the Ray object store. Workers read from a shared memory-mapped file (`pagerank.dat`).
- **Trade-off**: Simpler to implement but incurs high communication overhead (~96% of total time) due to the centralized bottleneck.

### 3) Distributed Reduction (Ray)
- **Coordination**: Uses a tree-reduction strategy to merge partial results in Ray worker tasks. Only the final merged root result crosses the object store to the driver.
- **Trade-off**: Significantly reduces communication overhead (to ~0%) and scales better for larger graphs and higher worker counts.

## Termination Policies
Each strategy is evaluated under two conditions:
1. **Fixed Iteration Count**: Always runs exactly `FIXED_ITERS` (e.g., 25). Useful for strict wall-clock budgeting and reproducibility.
2. **Convergence-Based**: Stops when the maximum absolute difference in ranks between iterations falls below a `TOLERANCE` threshold (e.g., 1e-6). Saves unnecessary work (e.g., converging in 11 iterations) and ensures rank quality.

## Important Comparison Notes (Correctness and Fairness)
- All three algorithms produce identical PageRank scores and top-page rankings (within a floating-point tolerance of `1e-5`).
- **Communication Overhead**: Centralized aggregation scales poorly due to O(W) communication, while distributed reduction uses O(log W) communication.
- **Hardware Context**: Tuned for a 4 physical core / 8 logical processor environment. Performance speedups (~1.35x) reflect this constraint but demonstrate parallel viability.

## Quick Start
1. Create and activate a Python environment.
2. Install dependencies:
   ```bash
   pip install ray numpy pandas matplotlib
