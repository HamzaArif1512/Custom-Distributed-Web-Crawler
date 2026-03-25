# Ray Crawler Files: Focused Comparison

## Scope
This document focuses on:
- Ray/raymasterworker.py
- Ray/raypeertopeer.py

It explains what they do, what input they take, key lines that matter, the role of Ray and alternatives, skeleton classification, differences, and overall summary.

---

## 1) What They Do

## Ray/raymasterworker.py
This file implements a distributed crawler using a centralized Master-Worker model.

- A Master actor keeps global crawl state (queue, visited URLs, graph, domain limits).
- Worker actors fetch pages and extract links concurrently.
- Workers submit results back to Master, which decides what gets scheduled next.

Main behavior:
1. Read seed domains from CSV.
2. Initialize Master with seeds and depth.
3. Spawn workers.
4. Workers request crawl batches, process them, and submit discovered links.
5. Master updates graph and queue under global constraints.
6. Save final graph to JSON and visualize.

## Ray/raypeertopeer.py
This file implements a distributed crawler using a peer-to-peer worker design.

- There is no central scheduling Master for links.
- URL ownership is partitioned by hash, and workers send discovered links directly to owner workers.
- A global CountdownSignal actor coordinates stop timing.

Main behavior:
1. Read seed domains from CSV.
2. Partition seeds by hash across workers.
3. Each worker crawls local frontier by depth.
4. Newly discovered links are hashed and forwarded to target workers.
5. Graphs from all workers are merged in main.
6. Save final graph to JSON and visualize.

---

## 2) Input They Take

## Shared inputs (both files)
1. majestic_million.csv as seed source.
2. Internal constants that control run behavior.
3. Network responses from live websites.

## raymasterworker.py inputs
- NUM_WORKERS = 12 (line 15)
- DEPTH = 3 (line 16)
- MAX_PER_DOMAIN = 50 (line 17)
- BATCH_SIZE = 50 (line 18)
- CSV read from majestic_million.csv (line 172)
- Uses first 10,000 rows and samples com domains as seeds.

## raypeertopeer.py inputs
- NUM_WORKERS = 12 (line 17)
- DEPTH = 2 (line 18)
- MAX_PER_DOMAIN = 50 (line 19)
- Internal BATCH_SIZE = 50 inside worker run (line 162)
- CSV read from majestic_million.csv (line 211)
- Uses first 10,000 rows and samples com domains as seeds.

Note:
Neither file currently takes command-line arguments; configuration is code-level constants.

---

## 3) Key Lines and Why They Matter

## raymasterworker.py key lines
1. Lines 42-74: Master actor state + scheduling policy.
- This is the core control plane.
- Depth and per-domain limits are enforced here.

2. Line 56: get_batch(batch_size=BATCH_SIZE).
- Workers pull work in chunks, enabling load balancing.

3. Lines 65-74: submit_results updates graph and queue.
- This is where discovered links become future crawl tasks.

4. Line 91: Worker actor definition with concurrency control.
- Encapsulates crawling behavior per worker.

5. Line 135 onward: worker run loop.
- Repeated pull, crawl, submit cycle is the main execution loop.

6. Line 152: asyncio.gather on batch URLs.
- Parallel link extraction within each worker.

7. Lines 170-205: main orchestration with Ray actor creation and result collection.
- Starts distributed run and gathers outputs.

8. Line 210: json.dump of graph output.
- Persists experiment result in crawl_graph.json.

## raypeertopeer.py key lines
1. Lines 40-41: hash_id(link).
- Deterministic URL-to-worker partitioning.
- Core of decentralized ownership.

2. Lines 47-62: CountdownSignal actor.
- Global stop coordination across independent workers.

3. Lines 119-124: process(link).
- Applies per-domain cap and assigns links to target worker batches.

4. Line 132 onward: run(self, workers_list, signal).
- Worker receives peer references and signal actor.
- Main decentralized crawl loop lives here.

5. Line 174: asyncio.gather over chunked crawl tasks.
- Parallel page fetching inside each worker.

6. Lines 190-193: peer dispatch to worker.recieve.remote.
- Direct worker-to-worker URL transfer.

7. Lines 217-219: divide_by_id[hash_id(link)].append(link).
- Initial sharding of seed URLs by ownership hash.

8. Line 237: ray.get(futures, timeout=300).
- Global collection with timeout guard.

9. Line 241: ray.cancel(w.run.remote(...), force=True).
- Important bug-prone line: this launches a new run call instead of canceling existing futures.
- Correct behavior should cancel existing refs in futures.

10. Line 264: json.dump of merged graph.
- Persists final merged result.

---

## 4) Role of Ray and Possible Alternatives

## Role of Ray in these files
Ray provides:
1. Actor model for long-lived distributed state and behavior.
2. Remote method invocation between workers and controllers.
3. Simple parallel execution and result collection with ray.get.
4. Scalable architecture from single machine to cluster-style deployment.

Why Ray fits this project:
- Crawler workers are stateful and long-running.
- Coordination patterns (master-worker or peer-to-peer) map naturally to actors.
- Easy experimentation with different distributed designs.

## Possible alternatives
1. Python multiprocessing
- Good local parallelism but weaker distributed ergonomics.
- More manual process/state coordination.

2. Celery + Redis/RabbitMQ
- Good for queued background jobs.
- Better for task queues than low-latency actor-style peer communication.

3. Dask
- Strong for dataframes and task graphs.
- Less natural than Ray actors for this specific actor-to-actor crawler design.

4. Apache Spark
- Excellent for batch data processing.
- Heavy setup and less suitable for fine-grained crawler actor interaction.

5. Go/Rust async services + message broker
- High performance and control.
- Higher development complexity versus Python + Ray.

---

## 5) Skeleton Classification

## Data-based skeletons

### raymasterworker.py
- Map: Workers apply the same extract_links logic over each URL in a batch (line 152).
- Reduce/Aggregate: Master merges worker outputs into global graph and queue (lines 65-74).
- Scan: Not explicitly used as a prefix-scan algorithm.

Conclusion:
- Primarily Map + Reduce style behavior.

### raypeertopeer.py
- Map: Each worker maps extract_links over chunk URLs (line 174).
- Partition/Shuffle-like step: hash_id assigns links to owner worker (lines 40-41, 119, 217-219).
- Reduce/Aggregate: Main merges all worker local graphs after completion.
- Scan: Not explicitly used.

Conclusion:
- Map + partitioned shuffle + final aggregate.

## Task-based skeletons

### raymasterworker.py
- Farm: Yes. Multiple workers process tasks from a shared producer (Master).
- Pipeline: Partial internal pipeline (fetch -> parse -> submit), but not a strict multi-stage distributed pipeline.
- Divide and Conquer: Not the primary pattern.

Conclusion:
- Dominant skeleton is Farm (central queue + worker pool).

### raypeertopeer.py
- Farm: Yes, workers still process URL chunks in parallel.
- Divide and Conquer: Yes, via hash-based ownership partitioning of URL space.
- Pipeline: Not the primary global pattern.

Conclusion:
- Hybrid Farm + Divide and Conquer.

---

## 6) Differences Between the Two Files

1. Coordination model
- raymasterworker.py: centralized coordination through Master actor.
- raypeertopeer.py: decentralized worker-to-worker routing.

2. State ownership
- raymasterworker.py: global queue/visited/graph in Master.
- raypeertopeer.py: local frontier/visited/graph per worker, merged later.

3. Scheduling
- raymasterworker.py: pull-based batch scheduling from Master.
- raypeertopeer.py: hash-based ownership and push-style peer delivery.

4. Fault and timeout handling
- raymasterworker.py: natural completion when queue empties.
- raypeertopeer.py: CountdownSignal and explicit timeout branch.

5. Bottleneck profile
- raymasterworker.py: Master can become bottleneck at scale.
- raypeertopeer.py: lower central bottleneck, higher coordination complexity.

6. Determinism and control
- raymasterworker.py: stronger global control in one place.
- raypeertopeer.py: more distributed behavior and less centralized visibility.

7. Implementation complexity
- raymasterworker.py: simpler to reason about and debug.
- raypeertopeer.py: more complex due to sharding, peer messaging, and global stop signal.

---

## 7) Overall Summary

Both files solve the same core problem: distributed web crawling with depth and domain constraints, outputting a crawl graph.

- raymasterworker.py is best when you want control, clarity, and easier debugging.
- raypeertopeer.py is best when you want to explore decentralized scaling and reduce central coordination pressure.

For coursework and architecture comparison, keeping both is valuable:
- One demonstrates centralized Farm skeleton clearly.
- The other demonstrates hybrid Farm + Divide and Conquer with hash partitioning.

Together, they provide a strong practical comparison of distributed crawler design choices using Ray.
