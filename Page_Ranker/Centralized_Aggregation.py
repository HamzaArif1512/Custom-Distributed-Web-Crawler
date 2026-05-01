import ray
import json
import time
import numpy as np
import tempfile
import os
import gc


@ray.remote
def compute_pagerank_chunk(node_indices_chunk, pagerank_mmap_path, indptr_ref, indices_ref, outbound_ref, N, d):
    # Each worker opens its own read-only view of the mmap — no copying
    pagerank      = np.memmap(pagerank_mmap_path, dtype='float64', mode='r', shape=(N,))
    indptr        = indptr_ref
    indices       = indices_ref
    out_counts    = outbound_ref

    new_ranks      = np.empty(len(node_indices_chunk), dtype='float64')
    local_max_diff = 0.0

    for i, node in enumerate(node_indices_chunk):
        inbound = indices[indptr[node]: indptr[node + 1]]
        if inbound.size > 0:
            rank_sum = np.sum(pagerank[inbound] / np.maximum(out_counts[inbound], 1))
        else:
            rank_sum = 0.0

        new_rank      = ((1 - d) / N) + (d * rank_sum)
        new_ranks[i]  = new_rank
        diff          = abs(new_rank - pagerank[node])
        if diff > local_max_diff:
            local_max_diff = diff

    del pagerank
    return node_indices_chunk, new_ranks, local_max_diff


def build_index_maps(graph):
    """Assign each unique node a stable integer index."""
    nodes = set(graph.keys())
    for dests in graph.values():
        nodes.update(dests)
    node_to_idx = {node: i for i, node in enumerate(sorted(nodes))}
    idx_to_node = {i: node for node, i in node_to_idx.items()}
    return node_to_idx, idx_to_node


def build_csr(graph, node_to_idx):
    """
    Build inbound CSR and outbound count array.

    Returns three flat numpy arrays instead of Python dicts/lists,
    cutting memory from ~6-8 GB to ~100-200 MB for a 1.5M-node graph.

      indptr      shape (N+1,)  — indptr[i]:indptr[i+1] is the slice of
                                  inbound neighbours for node i
      indices     shape (E,)    — concatenated inbound neighbour lists
      out_counts  shape (N,)    — number of outbound links per node
    """
    N = len(node_to_idx)

    # outbound counts
    out_counts = np.zeros(N, dtype=np.int32)
    for source, dests in graph.items():
        out_counts[node_to_idx[source]] = len(dests)

    # inbound degree per node
    indegree = np.zeros(N, dtype=np.int32)
    for source, dests in graph.items():
        for dest in dests:
            indegree[node_to_idx[dest]] += 1

    # index pointer array
    indptr = np.zeros(N + 1, dtype=np.int32)
    np.cumsum(indegree, out=indptr[1:])

    # fill neighbour index array
    indices  = np.empty(indptr[N], dtype=np.int32)
    fill_pos = indptr[:-1].copy()
    for source, dests in graph.items():
        src_idx = node_to_idx[source]
        for dest in dests:
            dst_idx = node_to_idx[dest]
            indices[fill_pos[dst_idx]] = src_idx
            fill_pos[dst_idx] += 1

    return indptr, indices, out_counts


def run_parallel_pagerank(graph_file, num_workers=8, d=0.85, max_iterations=100, tolerance=1e-6):
    print(f"Loading graph from {graph_file}...")
    with open(graph_file, 'r') as f:
        graph = json.load(f)

    print("Building index maps...")
    node_to_idx, idx_to_node = build_index_maps(graph)
    N = len(node_to_idx)
    print(f"Graph has {N:,} nodes.")

    print("Building CSR structures...")
    t0 = time.time()
    indptr, indices, out_counts = build_csr(graph, node_to_idx)
    print(f"CSR built in {time.time() - t0:.1f}s  "
          f"| indptr {indptr.nbytes/1e6:.1f} MB  "
          f"| indices {indices.nbytes/1e6:.1f} MB  "
          f"| out_counts {out_counts.nbytes/1e6:.1f} MB")

    # free the raw graph — no longer needed
    del graph; gc.collect()
    print("Raw graph freed from memory.")

    # push CSR arrays into Ray shared memory — zero-copy for workers
    indptr_ref   = ray.put(indptr)
    indices_ref  = ray.put(indices)
    outbound_ref = ray.put(out_counts)
    del indptr, indices, out_counts; gc.collect()

    # write initial pagerank to mmap on disk
    tmp_dir            = tempfile.mkdtemp()
    mmap_path          = os.path.join(tmp_dir, "pagerank.dat")
    pagerank_mmap      = np.memmap(mmap_path, dtype='float64', mode='w+', shape=(N,))
    pagerank_mmap[:]   = 1.0 / N
    pagerank_mmap.flush()
    del pagerank_mmap

    # split node indices into chunks
    all_indices = list(range(N))
    chunk_size  = (N + num_workers - 1) // num_workers
    node_chunks = [all_indices[i * chunk_size:(i + 1) * chunk_size] for i in range(num_workers)]

    print(f"Starting parallel PageRank with {num_workers} workers...")
    start_time = time.time()

    for iteration in range(max_iterations):
        futures = [
            compute_pagerank_chunk.remote(
                chunk, mmap_path, indptr_ref, indices_ref, outbound_ref, N, d
            )
            for chunk in node_chunks
        ]

        results = ray.get(futures)

        # write results back to mmap in one controlled pass
        pagerank_mmap   = np.memmap(mmap_path, dtype='float64', mode='r+', shape=(N,))
        global_max_diff = 0.0

        for node_indices, new_ranks, worker_max_diff in results:
            pagerank_mmap[node_indices] = new_ranks
            if worker_max_diff > global_max_diff:
                global_max_diff = worker_max_diff

        pagerank_mmap.flush()
        del pagerank_mmap; gc.collect()

        print(f"Iteration {iteration + 1} completed. Max diff: {global_max_diff:.8f}")

        if global_max_diff < tolerance:
            print(f"\nConvergence reached after {iteration + 1} iterations.")
            break

    elapsed_time = time.time() - start_time
    print(f"Finished in {elapsed_time:.2f} seconds.")

    # read final results and map indices back to node names
    final_mmap  = np.memmap(mmap_path, dtype='float64', mode='r', shape=(N,))
    final_ranks = {idx_to_node[i]: float(final_mmap[i]) for i in range(N)}

    del final_mmap
    os.remove(mmap_path)
    os.rmdir(tmp_dir)

    return final_ranks


if __name__ == "__main__":
    ray.init(ignore_reinit_error=True)

    try:
        final_ranks = run_parallel_pagerank("crawl_graph.json", num_workers=8)

        print("\nTop 5 Pages by Rank:")
        sorted_ranks = sorted(final_ranks.items(), key=lambda item: item[1], reverse=True)
        for url, rank in sorted_ranks[:5]:
            print(f"{url}: {rank:.6f}")

    except FileNotFoundError:
        print("Waiting for crawl_graph.json to be generated...")

    ray.shutdown()