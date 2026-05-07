

## Milestone 3 — Incremental PageRank & Benchmarks

Overview
- **Goal:** Compare full PageRank recomputation against incremental update strategies (micro local updates and distributed batch updates) to measure work reduction and runtime savings.

What changed
- **New script:** `m3-full.py` implements three benchmark modes: full recomputation (distributed with Ray), a micro incremental local update for a single new node, and a distributed batch incremental frontier update using Ray workers.
- **Graph inputs:** The script expects `crawl_graph.json`, `crawl_graph_1.json`, and `crawl_graph_2.json` in the repository root as scenario inputs.

How it works (high level)
- **Full recompute:** Builds CSR representations of the crawl graph, runs PageRank across the full node set using Ray worker tasks, and returns final ranks and iteration counts.
- **Micro incremental:** Simulates adding a single new node and performs a bounded-depth local propagation to measure nodes touched and time taken.
- **Batch incremental:** Uses Ray actors to process large frontiers (e.g. 50k new nodes) in parallel and merges the next frontier across workers.

Quick start
- **Install dependencies:** See [requirements.txt](requirements.txt) and run:

```
pip install -r requirements.txt
```

- **Run the milestone 3 benchmark:**

```
python m3-full.py
```

Notes and expectations
- The script uses `ray` for parallelism and `numpy` for numerical arrays — ensure Ray is initialized on your machine (single-node or cluster). The run prints timings, iteration counts, and an accuracy check comparing incremental vs full recompute.
- If your machine lacks Ray or you prefer a single-process run, you can adapt the script by replacing `ray.put`/remote calls with local function calls (not provided here).

Files of interest
- [`m3-full.py`](m3-full.py): the main Milestone 3 benchmark driver.
- [`requirements.txt`](requirements.txt): dependency list (updated to include `numpy`).
- `crawl_graph.json`, `crawl_graph_1.json`, `crawl_graph_2.json`: example graph inputs used by the benchmark.

If you'd like, I can also add a short notebook showing results plots or add argument parsing to `m3-full.py` to control worker counts and scenario selection.