# Parallel & Distributed Computing - Milestone 0
## Distributed Web Crawler & Page Rank Algorithm

**Hamza Ahmed** - 29265  
**Muhammad Hamza Arif** - 29234  
**Laraib Fatima Farooqui** - 26521  
**Arbaaz Murtaza** - 29052  

---

## Project Understanding

The Project can be broken into two main algorithms: the Web Crawling System and the Page Rank Algorithm. These algorithms combined make up the typical logic behind search engines.

The Distributed Web Crawler System uses multiple workers or nodes to traverse websites in parallel. These workers pull URLs from a queue, fetch the content of those URLs, and then parse the website for further URLs. The System starts with a single (seed) URL, all hyperlinks fetched from this page are added to the URL queue, and we start creating a graph that points from the URL to its hyperlinks. At this point, the parallel work begins: each parallel worker claims one URL from the queue and performs the same operation. We avoid duplication by ensuring that if a hyperlink is already in the graph, it is not pushed into the queue; only an edge is added to the graph. The stopping condition for this system may be either when the queue is empty or when the maximum depth is reached in the graph. The main purpose of the Web Crawler is to gather data to pass to the Page Rank Algorithm.

The Page Rank algorithm follows after the Web Crawling agents have completed their part. It works by counting the number and quality of links to a page to 'rank' that page's importance. The assumption being that the more important a website is, the more links there will be to it. The Page Rank algorithm is an iterative algorithm, which initially assigns each page the same rank (1/N, where N is the number of nodes in the graph). The algorithm parses through the graph created by the Web Crawlers, and on each pass, it updates the rank of all pages, using its mathematical formula:

$$PR(A) = \frac{1-d}{N} + d \left( \frac{PR(T_1)}{C(T_1)} + \ldots + \frac{PR(T_n)}{C(T_n)} \right)$$

where PR(A) is the Page Rank of any page A, N is the total number of nodes in the graph, d is the dampening factor, PR(T_i) is the Page Rank of any page T which is connected to A, and C(T_i) is the number of outbound links from page T_i.

And on each pass, the algorithm checks for convergence. When the algorithm reaches convergence, it terminates and outputs the rank for all nodes in the graph, which is typically a value between 0 and 1.

---

## Task Distribution

The work has been distributed across all milestones. For each milestone, each member will be allocated a set of tasks. This ensures a collective understanding at every phase of the project.

---

### Hamza Ahmed: Infrastructure & Coordination

| Milestone | Responsibilities |
|-----------|-----------------|
| Milestone #1 | - Ray cluster setup and configuration <br> - URL Frontier Manager (Ray Actor) implementation <br> - Visited URL tracking with deduplication <br> - Depth/domain constraint enforcement <br> - URL normalization utilities <br> - Configuration management system |

---

### Muhammad Hamza Arif: Data Processing & Parallelism

| Milestone | Responsibilities |
|-----------|-----------------|
| Milestone #1 | - Fetch & Parse workers (Ray tasks) <br> - HTTP request handling with error recovery <br> - HTML parsing and link extraction <br> - Rate limiting and politeness delays <br> - Robots.txt compliance (optional) <br> - Retry logic for failed requests |
| Milestone #2 | - Graph partitioning algorithms <br> - Data distribution across workers <br> - Load balancing strategies <br> - Partition quality metrics <br> - Communication pattern optimization |
| Milestone #2 | - PageRank coordinator implementation <br> - Iteration control and synchronization barriers <br> - Convergence detection logic <br> - Centralized aggregation strategy <br> - Worker task orchestration |
| Milestone #3 | - Incremental update coordinator <br> - Experiment orchestration framework <br> - System configuration for different scenarios <br> - Integration of all components <br> - Incremental graph updates <br> - Delta computation for new pages <br> - Affected subgraph identification <br> - Parallel delta processing |

---

### Arbaaz Murtaza: Graph Management & Computation

| Milestone | Responsibilities |
|-----------|-----------------|
| Milestone #1 | - Graph Builder (Ray Actor) implementation <br> - Thread-safe edge accumulation <br> - Adjacency list construction <br> - Node ID mapping (URL to integer) <br> - Graph serialization/deserialization <br> - Graph statistics module |
| Milestone #2 | - Sequential PageRank (baseline) <br> - Parallel PageRank computation kernel <br> - Rank update algorithms <br> - Distributed reduction implementation <br> - In-memory graph representations |
| Milestone #3 | - Partial recomputation strategies <br> - Incremental PageRank algorithms <br> - Affected node scoring <br> - Algorithm comparison framework |

---

### Laraib Fatima Farooqui: Testing, Evaluation & Documentation

| Milestone | Responsibilities |
|-----------|-----------------|
| Milestone #1 | - Main crawler coordinator <br> - Task dispatching logic <br> - Progress monitoring and logging <br> - Termination detection <br> - Unit tests for all components <br> - Integration testing framework <br> - Mock servers for testing |
| Milestone #2 | - Performance instrumentation <br> - Speedup and scalability benchmarks <br> - Communication overhead measurement <br> - Execution strategy comparison <br> - Visualization of results <br> - Performance report (Milestone 2) |
| Milestone #3 | - System monitoring dashboard <br> - Comprehensive evaluation suite <br> - Static vs dynamic workload comparison <br> - Trade-off analysis (recomputation vs incremental) <br> - Final report writing <br> - Presentation preparation <br> - Code documentation and README |