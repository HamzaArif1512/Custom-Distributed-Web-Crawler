# Web Crawler Project Explained (Simple Version)

## 1) Big Picture
This project builds and compares multiple versions of a web crawler.

The goal is to start from a set of seed websites, collect links, and build a link graph. That graph can later be used for analysis such as finding important pages.

The project evolves in stages:
- A basic single-machine crawler
- An async crawler using asyncio
- Distributed crawlers using Ray

---

## 2) Important Concepts (Easy Words)

### What is a web crawler?
A crawler is a bot that:
1. Opens a webpage
2. Reads all links on that page
3. Visits those links again (up to a chosen depth)

### What is depth?
Depth means how many "levels" of links you follow.
- Depth 1: only links from seed pages
- Depth 2: links from those links
- And so on

### Why async (asyncio)?
Network calls are slow because they wait for servers.
Asyncio lets one program handle many waiting requests at once, so crawling becomes much faster than one-by-one requests.

### What is Ray?
Ray is a Python framework for distributed computing.
It helps you run work in parallel across multiple workers/processes using:
- Remote functions and actors
- Task scheduling
- Easy result collection

In this project, Ray is used to create multiple crawler workers that split crawling work.

### What is a crawl graph?
A graph where:
- Node = a URL/page
- Edge = "page A links to page B"

This is saved as JSON and also visualized with NetworkX + Matplotlib.

---

## 3) File-by-File Overview

## Root folder

### basic.py
What it is:
- The simplest baseline crawler.
- Uses requests + BeautifulSoup (synchronous approach).

Skeleton used:
- Queue-based crawl loop with visited set
- Fetch page -> parse links -> push next links
- Early-stop counter

Steps taken:
1. Request Wikipedia main page
2. Extract links containing "wikipedia"
3. Keep crawling links from a queue
4. Stop after early limit
5. Print total time and unique visited links

Objective achieved:
- Build a basic baseline and prove crawling works without async/distribution.
- Used as a simple reference for later optimization.

---

### majestic_million.csv
What it is:
- A popular domain ranking dataset (Majestic Million style).
- Contains ranked domains and backlink-related metrics.

Observed columns include:
- GlobalRank, TldRank
- Domain, TLD
- RefSubNets, RefIPs
- Previous-period ranking/metrics fields

Usefulness in this experiment:
1. Provides realistic seed domains instead of manually typed URLs
2. Enables filtering (for example TLD == com)
3. Lets you sample random starting links for fair experimentation
4. Makes tests repeatable and scalable (small sample or larger sample)

In short: this CSV is the seed source that feeds crawler input.

---

### crawl_graph.json
What it is:
- Output artifact from crawler runs.
- Stores adjacency information: each source page mapped to discovered outgoing links.

Usefulness:
- Persistent result for later analysis
- Can be loaded to rebuild/visualize graph
- Useful for debugging and comparing crawler versions

---

### PROJECT_EXPLANATION.md
What it is:
- This documentation file.

Usefulness:
- Gives quick understanding of architecture, scripts, and objectives.

---

### __pycache__/
What it is:
- Auto-generated Python bytecode cache folder.

Usefulness:
- Speeds up module loading.
- Not part of crawler logic.

---

## Asyncio_Only folder

### Asyncio_Only/async.py
What it is:
- Async crawler version using aiohttp + asyncio + selectolax.
- Focus is concurrent network requests on one machine.

Skeleton used:
- Global state (visited, graph, semaphores)
- Async extractor function with robust exception handling
- Depth-based loop using asyncio.gather for parallel fetches

Steps taken:
1. Load one or more seed domains from CSV
2. Build HTTPS seed URLs
3. For each depth level:
   - Launch parallel fetch tasks for all current links
   - Parse HTML anchors
   - Flatten discovered links
   - Remove already visited links
4. Build and draw graph at the end

Objective achieved:
- Demonstrate performance improvement over sync approach by using concurrency.
- Create graph with an async crawler pipeline.

---

### Asyncio_Only/Milestone1_Asyncio.py
What it is:
- Milestone asyncio implementation, close to async.py.
- Adds better CSV path handling using script directory.

Skeleton used:
- Same core asyncio depth-iterative skeleton
- Per-domain semaphore throttling
- Extract -> gather -> flatten -> deduplicate

Steps taken:
1. Resolve CSV path relative to script location
2. Sample seeds from dataset
3. Crawl by depth with concurrent tasks
4. Store directed edges in graph structure
5. Plot resulting graph

Objective achieved:
- Make asyncio milestone runnable in different execution locations.
- Keep async crawling design while improving portability.

---

### Asyncio_Only/Milestone1_Asyncio_Mod.py
What it is:
- More structured and configurable asyncio crawler.
- Most mature single-machine async version in this folder.

Skeleton used:
- Config-driven architecture with dataclass (CrawlConfig)
- Utility-function pipeline:
  - load_config
  - normalize_url
  - can_visit_url
  - extract_links
- BFS-like depth rounds with scheduling constraints

Steps taken:
1. Load config defaults and optional environment overrides
2. Read and sample seed domains from CSV
3. Normalize URLs (relative links, fragments, host casing, default ports)
4. Track seen URLs and per-domain quotas
5. Crawl each depth concurrently with asyncio.gather
6. Apply filtering constraints before next depth scheduling
7. Print crawl statistics and draw graph

Objective achieved:
- Improve correctness (URL normalization, deduplication)
- Improve control (domain caps, same-domain option, configurable timeouts/depth)
- Provide cleaner architecture for future extension

---

### Asyncio_Only/ASYNCIO_GUIDE.md
What it is:
- Conceptual write-up explaining asyncio and milestone comparison.

Usefulness:
- Helps readers understand why async design is faster and how code evolved.
- Useful as learning material and project report support.

---

## Ray folder

### Ray/raymasterworker.py
What it is:
- Distributed crawler using a Master-Worker architecture in Ray.

Skeleton used:
- Central coordinator actor: Master
- Multiple worker actors: WebCrawler
- Pull-based batch scheduling:
  - Workers ask Master for a batch
  - Workers crawl and submit results back

Steps taken:
1. Load seed domains from CSV and normalize URLs
2. Create Master actor with queue + visited + graph state
3. Create multiple WebCrawler actors
4. Workers repeatedly:
   - request batch
   - crawl pages concurrently inside worker
   - return discovered links to Master
5. Master enforces depth and per-domain limits
6. Collect worker totals, fetch graph, save JSON, visualize

Objective achieved:
- Demonstrate distributed workload coordination.
- Keep global crawl policy in one place (Master) for consistency.

---

### Ray/raypeertopeer.py
What it is:
- Distributed crawler using peer-to-peer style worker communication in Ray.

Skeleton used:
- Hash-partitioned worker ownership (MD5-based worker id)
- Worker-local frontier + visited + graph
- Inter-worker URL passing via actor method calls
- Global stop coordination actor (CountdownSignal)

Steps taken:
1. Load many seed domains from CSV
2. Assign each seed to worker by hash_id(url)
3. Start all worker actors with their shard of frontier
4. Each worker crawls by depth and builds local graph
5. Newly found URLs are routed to owner worker based on hash
6. CountdownSignal triggers global timeout once first worker finishes
7. Main merges all local graphs and saves unified crawl_graph.json

Objective achieved:
- Remove central master bottleneck and test decentralized scaling behavior.
- Demonstrate partitioned crawling and eventual graph merge.

Note:
- In the timeout path, cancellation should target existing futures, not launch new run calls.


### crawl_graph.json
What it is:
- It prints all the crawled URLs starting from the base URLs in the majestic_million csv file
- It runs after raymasterworker.py is successfully executed.

---

## 4) What This Project Achieves Overall

1. Shows crawler evolution from simple to advanced
2. Compares synchronous, asynchronous, and distributed patterns
3. Uses realistic input seeds from a large domain dataset
4. Produces a crawl graph for analysis and visualization
5. Demonstrates practical distributed systems ideas:
   - Work partitioning
   - Concurrency limits
   - Failure/timeout handling
   - Data aggregation

---

## 5) Suggested Reading Order
1. basic.py
2. Asyncio_Only/async.py
3. Asyncio_Only/Milestone1_Asyncio.py
4. Asyncio_Only/Milestone1_Asyncio_Mod.py
5. Ray/raymasterworker.py
6. Ray/raypeertopeer.py

This order matches the design maturity and helps understand how each stage improves the previous one.
