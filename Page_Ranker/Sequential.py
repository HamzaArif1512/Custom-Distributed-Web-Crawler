import json
import time
import numpy as np
import gc


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

    indices  = np.empty(indptr[N], dtype=np.int32)
    fill_pos = indptr[:-1].copy()
    for source, dests in graph.items():
        src_idx = node_to_idx[source]
        for dest in dests:
            dst_idx = node_to_idx[dest]
            indices[fill_pos[dst_idx]] = src_idx
            fill_pos[dst_idx] += 1

    return indptr, indices, out_counts


def run_sequential_pagerank(graph_file, d=0.85, max_iterations=100, tolerance=1e-6):
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
    print(f"CSR built in {time.time() - t0:.1f}s")

    del graph; gc.collect()
    print("Raw graph freed from memory.")

    # single rank vector in RAM — no mmap needed, no Ray, just a numpy array
    pagerank     = np.full(N, 1.0 / N, dtype='float64')
    new_ranks    = np.empty(N, dtype='float64')

    print("Starting sequential PageRank...")
    start_time = time.time()

    for iteration in range(max_iterations):

        # one loop over every node — no workers, no futures, no barriers
        for node in range(N):
            inbound = indices[indptr[node]: indptr[node + 1]]
            if inbound.size > 0:
                rank_sum = np.sum(pagerank[inbound] / np.maximum(out_counts[inbound], 1))
            else:
                rank_sum = 0.0
            new_ranks[node] = (1 - d) / N + d * rank_sum

        # check convergence
        max_diff = np.max(np.abs(new_ranks - pagerank))

        # swap arrays — new becomes current for next iteration
        pagerank, new_ranks = new_ranks, pagerank

        print(f"Iteration {iteration + 1} completed. Max diff: {max_diff:.8f}")

        if max_diff < tolerance:
            print(f"\nConvergence reached after {iteration + 1} iterations.")
            break

    elapsed_time = time.time() - start_time
    print(f"Finished in {elapsed_time:.2f} seconds.")

    final_ranks = {idx_to_node[i]: float(pagerank[i]) for i in range(N)}
    return final_ranks


if __name__ == "__main__":
    try:
        final_ranks = run_sequential_pagerank("crawl_graph.json")

        print("\nTop 5 Pages by Rank:")
        sorted_ranks = sorted(final_ranks.items(), key=lambda item: item[1], reverse=True)
        for url, rank in sorted_ranks[:5]:
            print(f"{url}: {rank:.6f}")

    except FileNotFoundError:
        print("Waiting for crawl_graph.json to be generated...")