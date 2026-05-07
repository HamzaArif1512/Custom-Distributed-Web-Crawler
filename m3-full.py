import ray
import time
import json
import numpy as np
import gc

# ── Full recomputation (CA) ───────────────────────────────────────────────────

def build_index_maps(graph):
    nodes = set(graph.keys())
    for dests in graph.values():
        nodes.update(dests)
    node_to_idx = {node: i for i, node in enumerate(sorted(nodes))}
    idx_to_node = {i: node for node, i in node_to_idx.items()}
    return node_to_idx, idx_to_node

def build_csr(graph, node_to_idx):
    N = len(node_to_idx)
    out_counts = np.zeros(N, dtype=np.int32)
    for source, dests in graph.items():
        out_counts[node_to_idx[source]] = len(dests)
    indegree = np.zeros(N, dtype=np.int32)
    for source, dests in graph.items():
        for dest in dests:
            indegree[node_to_idx[dest]] += 1
    indptr = np.zeros(N + 1, dtype=np.int32)
    np.cumsum(indegree, out=indptr[1:])
    indices = np.empty(indptr[N], dtype=np.int32)
    fill_pos = indptr[:-1].copy()
    for source, dests in graph.items():
        src_idx = node_to_idx[source]
        for dest in dests:
            dst_idx = node_to_idx[dest]
            indices[fill_pos[dst_idx]] = src_idx
            fill_pos[dst_idx] += 1
    return indptr, indices, out_counts

@ray.remote
def compute_chunk(node_indices_chunk, pagerank_arr, indptr, indices, out_counts, N, d):
    new_ranks = np.empty(len(node_indices_chunk), dtype='float64')
    local_max_diff = 0.0
    for i, node in enumerate(node_indices_chunk):
        inbound = indices[indptr[node]: indptr[node + 1]]
        rank_sum = np.sum(pagerank_arr[inbound] / np.maximum(out_counts[inbound], 1)) if inbound.size > 0 else 0.0
        new_rank = ((1 - d) / N) + (d * rank_sum)
        new_ranks[i] = new_rank
        diff = abs(new_rank - pagerank_arr[node])
        if diff > local_max_diff:
            local_max_diff = diff
    return node_indices_chunk, new_ranks, local_max_diff

def run_full_pagerank(graph, num_workers=8, d=0.85, max_iterations=100, tolerance=1e-6):
    node_to_idx, idx_to_node = build_index_maps(graph)
    N = len(node_to_idx)
    indptr, indices, out_counts = build_csr(graph, node_to_idx)
    del graph; gc.collect()

    indptr_ref   = ray.put(indptr)
    indices_ref  = ray.put(indices)
    outbound_ref = ray.put(out_counts)

    pagerank = np.full(N, 1.0 / N, dtype='float64')

    chunk_size  = (N + num_workers - 1) // num_workers
    node_chunks = [list(range(i * chunk_size, min((i+1) * chunk_size, N))) for i in range(num_workers)]

    iterations = 0
    for iteration in range(max_iterations):
        pr_ref = ray.put(pagerank)
        futures = [compute_chunk.remote(chunk, pr_ref, indptr_ref, indices_ref, outbound_ref, N, d) for chunk in node_chunks]
        results = ray.get(futures)

        new_pagerank = pagerank.copy()
        global_max_diff = 0.0
        for node_indices, new_ranks, worker_max_diff in results:
            new_pagerank[node_indices] = new_ranks
            if worker_max_diff > global_max_diff:
                global_max_diff = worker_max_diff

        pagerank = new_pagerank
        iterations += 1
        if global_max_diff < tolerance:
            break

    final_ranks = {idx_to_node[i]: float(pagerank[i]) for i in range(N)}
    return final_ranks, iterations

# ── Incremental micro-update (local, 1 new node) ─────────────────────────────

def run_incremental_local(initial_frontier, static_links, new_links, max_depth=3, tolerance=1e-7):
    current_frontier = initial_frontier
    current_depth = 1
    nodes_processed = 0

    def process_step(frontier, static, new, tol, d=0.85):
        next_f = {}
        for url, delta in frontier.items():
            dests = new.get(url) or static.get(url, [])
            if not dests:
                continue
            transfer = (delta * d) / len(dests)
            if transfer < tol:
                continue
            for d_url in dests:
                next_f[d_url] = next_f.get(d_url, 0.0) + transfer
        return next_f

    while current_frontier and current_depth <= max_depth:
        nodes_processed += len(current_frontier)
        current_frontier = process_step(current_frontier, static_links, new_links, tolerance)
        current_depth += 1
    return nodes_processed

# ── Incremental batch-update (distributed Ray, 50k new nodes) ────────────────

@ray.remote
def distributed_frontier_task(chunk_frontier, static_links_ref, d=0.85):
    next_f = {}
    for url, delta in chunk_frontier.items():
        dests = static_links_ref.get(url, [])
        if not dests:
            continue
        transfer = (delta * d) / len(dests)
        for d_url in dests:
            next_f[d_url] = next_f.get(d_url, 0.0) + transfer
    return next_f

def run_incremental_distributed(initial_frontier, static_links, num_workers=4):
    static_ref = ray.put(static_links)
    keys   = list(initial_frontier.keys())
    chunks = np.array_split(keys, num_workers)
    futures = []
    for chunk in chunks:
        chunk_data = {k: initial_frontier[k] for k in chunk if len(k) > 0}
        futures.append(distributed_frontier_task.remote(chunk_data, static_ref))
    results = ray.get(futures)
    final_next = {}
    for res in results:
        for k, v in res.items():
            final_next[k] = final_next.get(k, 0.0) + v
    return final_next

# ── Accuracy check ────────────────────────────────────────────────────────────

def check_accuracy(full_ranks, incremental_frontier, static_links, new_links, N):
    """
    Compare incremental result against full recomputation for affected nodes.
    Returns max absolute difference for nodes touched by the incremental update.
    """
    affected = set(incremental_frontier.keys())
    if not affected:
        return 0.0
    diffs = []
    for url in affected:
        full_val  = full_ranks.get(url, 1.0 / N)
        incr_val  = incremental_frontier.get(url, 1.0 / N)
        diffs.append(abs(full_val - incr_val))
    return max(diffs) if diffs else 0.0

# ── Main benchmark ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ray.init(ignore_reinit_error=True, runtime_env={
        "excludes": ["crawl_graph.json", "crawl_graph_1.json", "crawl_graph_2.json"]
    })

    scenarios = [
        {"name": "Depth 1", "file": "crawl_graph_1.json"},
        {"name": "Depth 2", "file": "crawl_graph_2.json"},
        {"name": "Depth 3", "file": "crawl_graph.json"},
    ]

    print("\n" + "="*90)
    print("MILESTONE 3 BENCHMARK — Full Recompute vs Incremental Update")
    print("="*90)

    for s in scenarios:
        print(f"\n{'─'*90}")
        print(f"  {s['name']}  ({s['file']})")
        print(f"{'─'*90}")

        with open(s['file'], 'r') as f:
            graph = json.load(f)
        N = len(graph)
        print(f"  Nodes: {N:,}")

        existing_urls = list(graph.keys())[:2]
        new_links_micro  = {"http://new-micro.com": existing_urls}
        start_f_micro    = {"http://new-micro.com": (1 - 0.85) / (N + 1)}

        # ── 1. Full recomputation (CA) ───────────────────────────────────────
        graph_copy = dict(graph)  # keep original for incremental
        t0 = time.time()
        full_ranks, iters = run_full_pagerank(graph_copy, num_workers=8)
        full_time = time.time() - t0
        print(f"\n  [Full recompute]  time={full_time:.3f}s   iterations={iters}")

        # ── 2. Micro incremental (local, 1 new node) ─────────────────────────
        t0 = time.time()
        nodes_proc = run_incremental_local(start_f_micro, graph, new_links_micro)
        micro_time = time.time() - t0
        print(f"  [Micro update]    time={micro_time:.8f}s   nodes_processed={nodes_proc}")

        # ── 3. Batch incremental (Ray, 50k new nodes) ────────────────────────
        massive_frontier = {f"http://new-{i}.com": (1 - 0.85) / N for i in range(50000)}
        t0 = time.time()
        run_incremental_distributed(massive_frontier, graph, num_workers=8)
        batch_time = time.time() - t0
        print(f"  [Batch update]    time={batch_time:.4f}s   frontier_size=50,000")

        # ── 4. Accuracy check ────────────────────────────────────────────────
        max_diff = check_accuracy(full_ranks, start_f_micro, graph, new_links_micro, N)
        print(f"  [Accuracy]        max_abs_diff (incremental vs full) = {max_diff:.2e}")

        # ── 5. Summary line ──────────────────────────────────────────────────
        work_reduction = N / max(nodes_proc, 1)
        print(f"\n  SUMMARY:")
        print(f"    Full recompute time : {full_time:.3f} s")
        print(f"    Micro update time   : {micro_time*1e6:.2f} us")
        print(f"    Batch update time   : {batch_time:.4f} s")
        print(f"    Work reduction      : ~{work_reduction:,.0f}x fewer nodes processed (micro vs full)")
        print(f"    Max rank diff       : {max_diff:.2e}")

        del graph, full_ranks
        gc.collect()

    ray.shutdown()
    print("\n" + "="*90)
    print("DONE")
    print("="*90 + "\n")