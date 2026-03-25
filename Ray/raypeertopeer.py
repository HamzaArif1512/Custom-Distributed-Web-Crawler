import os
os.environ["RAY_DEDUP_LOGS"] = "0"
import ray
import time
import asyncio
import aiohttp
from selectolax.parser import HTMLParser
from urllib.parse import urlparse, urlunparse, unquote
import networkx as nx
import matplotlib.pyplot as plt
import pandas as pd
import ssl
import hashlib
from collections import defaultdict
import json

NUM_WORKERS = 12
DEPTH = 2
MAX_PER_DOMAIN = 50

# --- Helper functions ---
def normalize_url(url):
    try:
        url = unquote(url).strip()
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        normalized = urlunparse((parsed.scheme, netloc, parsed.path.lower(), '', '', ''))
        return normalized.rstrip('/')
    except Exception:
        return url

def get_base_domain(url):
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith('www.'):
        return netloc[4:]
    return netloc

def hash_id(link):
    return int(hashlib.md5(link.encode()).hexdigest(), 16) % NUM_WORKERS

# -------------------------

# --- NEW: The Global Countdown Signal ---
@ray.remote
class CountdownSignal:
    def __init__(self):
        self.stop_time = None

    def start_countdown(self, delay_seconds):
        # Only the FIRST worker to finish sets this timer
        if self.stop_time is None:
            self.stop_time = time.time() + delay_seconds
            print(f"\n🚨 FIRST WORKER FINISHED! 🚨")
            print(f"Starting {delay_seconds}-second countdown before forcing the rest to stop...\n")

    def is_time_up(self):
        if self.stop_time is None:
            return False
        return time.time() >= self.stop_time


@ray.remote(max_concurrency=100)
class WebCrawler:
    def __init__(self, id, list_param):
        self.domain_semaphores = defaultdict(lambda: asyncio.Semaphore(3))
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE
        self.visited = set()
        self.queued = set()
        self.id = id
        self.batches = [[] for _ in range(NUM_WORKERS)]
        self.frontier = [normalize_url(link) for link in list_param]
        self.workers = []
        self.graph = defaultdict(set)
        self.total_links_visited = []

    async def extract_links(self, url, session):
        self.total_links_visited.append(url)
        domain = urlparse(url).netloc
        semaphore = self.domain_semaphores[domain]
        async with semaphore:
            try:
                async with session.get(
                    url,
                    ssl=self.ssl_context,
                    headers=self.headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    content_type = response.headers.get("Content-Type", "")
                    if "text/html" not in content_type:
                        return []
                    if response.status == 200:
                        select = HTMLParser(await response.text())
                        valid_links = [
                            a.attributes["href"]
                            for a in select.css('a[href]')
                            if a.attributes.get("href", "") and "https://" in a.attributes.get("href", "")
                        ]
                        normalized_unique_links = list({normalize_url(link) for link in valid_links})
                        self.graph[url].update(normalized_unique_links)
                        return normalized_unique_links
                    else:
                        return []
            except Exception:
                return []

    def process(self, link):
        worker_id = hash_id(link)
        domain = get_base_domain(link)
        domain_count = sum(1 for l in self.batches[worker_id] if get_base_domain(l) == domain)

        if domain_count < MAX_PER_DOMAIN:
            self.batches[worker_id].append(link)

    async def recieve(self, links):
        for link in links:
            if link not in self.visited and link not in self.queued:
                self.queued.add(link)
                self.frontier.append(link)

    async def run(self, workers_list, signal):
        self.workers = workers_list
        connector = aiohttp.TCPConnector(limit=100, ssl=False)
        async with aiohttp.ClientSession(headers=self.headers, connector=connector) as session:
            for i in range(DEPTH):
                # Before starting a depth, check if the global timer is up
                if await signal.is_time_up.remote():
                    print(f"🛑 Worker {self.id} halting before Depth {i} due to global timeout.")
                    break

                unique_frontier = list(set(self.frontier))
                
                # Without a barrier, a fast worker might arrive here before slow workers send it URLs.
                # If the frontier is empty, wait 5 seconds just in case URLs are in transit.
                if not unique_frontier:
                    await asyncio.sleep(5)
                    unique_frontier = list(set(self.frontier))

                print(f"Worker {self.id} depth {i}: {len(unique_frontier)} URLs in frontier")

                to_crawl = []
                for link in unique_frontier:
                    if link not in self.visited:
                        self.visited.add(link)
                        to_crawl.append(link)

                self.frontier = []
                self.queued = set()
                self.batches = [[] for _ in range(NUM_WORKERS)]

                BATCH_SIZE = 50
                response = []
                
                for chunk_start in range(0, len(to_crawl), BATCH_SIZE):
                    # Check global timer during the crawl to exit cleanly
                    if await signal.is_time_up.remote():
                        print(f"🛑 Worker {self.id} halting mid-depth due to global timeout.")
                        break
                        
                    chunk = to_crawl[chunk_start : chunk_start + BATCH_SIZE]
                    print(f"Worker {self.id} crawling batch of {len(chunk)} (Progress: {chunk_start}/{len(to_crawl)})")
                    
                    chunk_responses = await asyncio.gather(
                        *[self.extract_links(link, session) for link in chunk],
                        return_exceptions=True
                    )
                    response.extend(chunk_responses)

                links = [
                    link
                    for sublist in response
                    if isinstance(sublist, list)
                    for link in sublist
                ]

                for link in links:
                    self.process(link)

                for worker in range(NUM_WORKERS):
                    unique_batch = list(set(self.batches[worker]))
                    if unique_batch:
                        await self.workers[worker].recieve.remote(unique_batch)

                # Wait slightly so async network messages fire
                await asyncio.sleep(0.5)

            # --- END OF DEPTH LOOP ---
            # If a worker naturally finishes all its depths, it triggers the 2-minute countdown.
            await signal.start_countdown.remote(120)

        # Returns whatever graph it successfully built before stopping
        return dict(self.graph)

    def get_total_visited(self):
        return self.total_links_visited


async def main():
    numOfstartinglinks = 240
    df = pd.read_csv("majestic_million.csv")
    df = df[:10000]
    rows = df[df['TLD'] == 'com'].sample(numOfstartinglinks)
    links = rows['Domain'].tolist()
    links = ['https://' + link for link in links]

    divide_by_id = {key: [] for key in range(NUM_WORKERS)}
    for link in links:
        divide_by_id[hash_id(link)].append(link)

    print("Seed distribution (Hashed by URL):")
    for k, v in divide_by_id.items():
        print(f"  Worker {k}: {len(v)} seeds")

    begin_time = time.time()
    
    # 1. Initialize our Signal instead of Barrier
    signal = CountdownSignal.remote()
    workers = [WebCrawler.remote(i, divide_by_id[i]) for i in range(NUM_WORKERS)]
    
    # 2. Pass signal into run
    futures = [w.run.remote(workers, signal) for w in workers]
    
    # 3. Ray.get automatically waits for all workers to return their graphs.
    # When the 2 minute timer hits, the remaining workers break out of their loops and return.
    try:
        graphs = ray.get(futures, timeout=300)
    except ray.exceptions.GetTimeoutError:
    # Cancel remaining workers and collect partial results
        for w in workers:
            ray.cancel(w.run.remote(...), force=True)
        graphs = []
        for f in futures:
            try:
                graphs.append(ray.get(f, timeout=1))
            except Exception:
                graphs.append({})


    visited_futures = [w.get_total_visited.remote() for w in workers]
    individual_totals = ray.get(visited_futures)
    print("\nURLs crawled per worker:")
    for i in range(NUM_WORKERS):
        print(f"  Worker {i}: {len(individual_totals[i])}")

    graph = defaultdict(set)
    for d in graphs:
        for k, v in d.items():
            graph[k].update(v)

    print("\nSaving graph to disk...")
    json_ready_graph = {node: list(neighbors) for node, neighbors in graph.items()}
    with open("crawl_graph.json", "w", encoding="utf-8") as f:
        json.dump(json_ready_graph, f, indent=2)
    print("✅ Graph saved to 'crawl_graph.json'")

    end_time = time.time()
    print(f"\nTotal time (depth={DEPTH}): {end_time - begin_time:.2f} seconds")
    print(f"Source nodes: {len(graph)}")
    total_edges = sum(len(v) for v in graph.values())
    print(f"Total edges: {total_edges}")

    G = nx.DiGraph()
    for node, neighbors in graph.items():
        for neighbor in neighbors:
            G.add_edge(node, neighbor)

    nx.draw(G, with_labels=False, node_size=10, alpha=0.5)
    plt.show()

if __name__ == "__main__":
    ray.init(ignore_reinit_error=True, runtime_env={"env_vars": {"RAY_DEDUP_LOGS": "0"}})
    asyncio.run(main())
    ray.shutdown()