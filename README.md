# Distributed Web Crawling and Parallel Page Ranking
### All milestone work has been completed in separate branches (M0, M1, M2, and M3)

## Overview
This project presents the design, implementation, and evaluation of a distributed web crawling and parallel PageRank system built using the Ray framework and Python asynchronous programming.

The project is divided into three milestones:

1. **Milestone 1 — Distributed Web Crawling**
   - Sequential crawler
   - Ray Master-Worker crawler
   - Ray Peer-to-Peer crawler
   - Hyperparameter benchmarking across crawl depth, seed counts, and worker counts

2. **Milestone 2 — Parallel PageRank**
   - Centralised Aggregation (CA)
   - Distributed Reduction (DR)
   - CSR-based memory optimization
   - Parallel convergence computation

3. **Milestone 3 — Incremental Graph Updates**
   - Adaptive incremental PageRank updates
   - 2-Stage MapReduce edge partitioning
   - Efficient micro-update propagation
   - Reduced recomputation overhead

---

## Features

- Distributed web crawling using Ray
- Asynchronous HTTP requests using `aiohttp`
- Parallel graph construction
- Scalable PageRank computation
- Incremental graph update support
- CSR graph representation for memory efficiency
- Benchmarking and performance analysis

---

## Technologies Used

- Python
- Ray
- asyncio
- aiohttp
- NumPy
- SciPy
- NetworkX

---

## System Architecture

### Milestone 1: Crawling Architectures
- Sequential asynchronous crawler
- Ray Master-Worker architecture
- Ray Peer-to-Peer architecture

### Milestone 2: PageRank Architectures
- Centralised Aggregation (CA)
- Distributed Reduction (DR)

### Milestone 3: Incremental Updates
- MapReduce-based edge partitioning
- Incremental rank propagation

---

## Experimental Setup

Experiments were conducted using:
- Multiple crawl depths (1–3)
- Seed counts (10, 20, 40)
- Worker counts (4–12)

Graphs ranging from:
- ~54K nodes
- up to ~1.5M nodes

---

## Key Results

### Crawling Performance
- Master-Worker achieved up to **425% throughput improvement**
- Peer-to-Peer achieved up to **128% improvement**

### PageRank Performance
- Distributed Reduction achieved up to **2.70× speedup**
- CSR representation reduced memory usage by **20–30×**

### Incremental Updates
- Single-page updates executed in approximately **20 µs**
- Full recomputation required approximately **24 s**
- Incremental updates reduced processed nodes by approximately **1.57 million×**

---

## Repository Structure

```text
.
├── Milestone1/
│   ├── Sequential Crawler
│   ├── Master-Worker Crawler
│   └── Peer-to-Peer Crawler
│
├── Milestone2/
│   ├── Centralised Aggregation
│   └── Distributed Reduction
│
├── Milestone3/
│   ├── Incremental Updates
│   └── MapReduce Partitioning
│
└── Report/
    └── Distributed_Web_Crawling_and_Parallel_Graph_Construction.pdf
```

---

## How to Run

### 1. Install Dependencies

```bash
pip install ray aiohttp numpy scipy networkx
```

### 2. Start Ray

```bash
ray start --head
```

### 3. Run a Milestone

Example:

```bash
python milestone1_master_worker.py
```

---

## Research Objectives

- Compare centralized and decentralized crawling strategies
- Analyze scalability under varying workloads
- Evaluate distributed PageRank performance
- Investigate efficient incremental graph updates

---

## Authors

- Hamza Ahmed
- Muhammad Hamza Arif
- Laraib Fatima Farooqui
- Arbaaz Murtaza

---

## References

Key references include:
- PageRank by Brin & Page
- Ray Distributed Runtime
- Distributed Web Crawling literature
- Async I/O systems

See the full report bibliography for detailed citations.

---

## License

This project is intended for academic and educational purposes.
