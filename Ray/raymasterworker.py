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
from collections import defaultdict
import json
import threading

NUM_WORKERS = 12
DEPTH = 3
MAX_PER_DOMAIN = 50
BATCH_SIZE = 50

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

# -------------------------

@ray.remote
class Master:
    def __init__(self, seed_urls, max_depth):
        self.max_depth = max_depth
        self.visited = set()
        self.graph = defaultdict(set)
        self.domain_counts = defaultdict(int)
        self.queue = []

        for url in seed_urls:
            norm = normalize_url(url)
            if norm not in self.visited:
                self.visited.add(norm)
                self.queue.append((norm, 0))

    def get_batch(self, batch_size=BATCH_SIZE):
        """Worker calls this to get a batch of URLs to crawl."""
        batch = []
        while self.queue and len(batch) < batch_size:
            url, depth = self.queue.pop(0)
            batch.append((url, depth))
        return batch

    def submit_results(self, results):
        """Worker submits crawled links. results = [(parent_url, depth, [child_urls])]"""
        for parent_url, depth, child_urls in results:
            for child in child_urls:
                self.graph[parent_url].add(child)
                if depth + 1 <= self.max_depth and child not in self.visited:
                    domain = get_base_domain(child)
                    if self.domain_counts[domain] < MAX_PER_DOMAIN:
                        self.visited.add(child)
                        self.domain_counts[domain] += 1
                        self.queue.append((child, depth + 1))

    def is_done(self):
        return len(self.queue) == 0

    def get_graph(self):
        return dict(self.graph)

    def stats(self):
        return {
            "queue": len(self.queue),
            "visited": len(self.visited),
            "graph_nodes": len(self.graph)
        }


@ray.remote(max_concurrency=2)
class WebCrawler:
    def __init__(self, worker_id):
        self.worker_id = worker_id
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
        self.total_crawled = 0

    async def extract_links(self, url, session):
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
                        return list({normalize_url(link) for link in valid_links})
                    else:
                        return []
            except Exception:
                return []

    async def run(self, master):
        connector = aiohttp.TCPConnector(limit=100, ssl=False)
        async with aiohttp.ClientSession(headers=self.headers, connector=connector) as session:
            empty_polls = 0
            while True:
                batch = await master.get_batch.remote(BATCH_SIZE)

                if not batch:
                    empty_polls += 1
                    if empty_polls > 10:        # tried 10 times, truly done
                        break
                    await asyncio.sleep(1)      # wait for other workers to submit
                    continue

                empty_polls = 0                 # reset on successful batch
                print(f"Worker {self.worker_id}: crawling {len(batch)} URLs")

                response = await asyncio.gather(
                    *[self.extract_links(url, session) for url, _ in batch],
                    return_exceptions=True
                )

                results = []
                for (url, depth), links in zip(batch, response):
                    if isinstance(links, list):
                        results.append((url, depth, links))
                        self.total_crawled += 1
                    else:
                        results.append((url, depth, []))

                await master.submit_results.remote(results)

        return self.total_crawled


async def main():
    numOfstartinglinks = 240
    df = pd.read_csv("majestic_million.csv")
    df = df[:10000]
    rows = df[df['TLD'] == 'com'].sample(numOfstartinglinks)
    links = rows['Domain'].tolist()
    links = [normalize_url('https://' + link) for link in links]

    begin_time = time.time()

    master = Master.remote(links, DEPTH)
    workers = [WebCrawler.remote(i) for i in range(NUM_WORKERS)]

    # background monitor thread
    stop_monitor = threading.Event()
    def monitor():
        while not stop_monitor.is_set():
            try:
                s = ray.get(master.stats.remote())
                elapsed = time.time() - begin_time
                print(f"  [{elapsed:.0f}s] queue={s['queue']} visited={s['visited']} nodes={s['graph_nodes']}")
            except Exception:
                pass
            time.sleep(10)

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()

    futures = [w.run.remote(master) for w in workers]
    totals = ray.get(futures)
    stop_monitor.set()

    print(f"\nURLs crawled per worker: {totals}")
    print(f"Total URLs crawled: {sum(totals)}")

    graph = ray.get(master.get_graph.remote())

    print("\nSaving graph to disk...")
    json_ready_graph = {node: list(neighbors) for node, neighbors in graph.items()}
    with open("crawl_graph.json", "w", encoding="utf-8") as f:
        json.dump(json_ready_graph, f, indent=2)
    print("✅ Graph saved to 'crawl_graph.json'")

    end_time = time.time()
    print(f"\nTotal time (depth={DEPTH}): {end_time - begin_time:.2f} seconds")
    print(f"Source nodes: {len(graph)}")
    print(f"Total edges: {sum(len(v) for v in graph.values())}")

    G = nx.DiGraph()
    for node, neighbors in graph.items():
        for neighbor in neighbors:
            G.add_edge(node, neighbor)

    nx.draw(G, with_labels=False, node_size=10, alpha=0.5)
    plt.show()


if __name__ == "__main__":
    
    ray.init(ignore_reinit_error=True)
    asyncio.run(main())
    ray.shutdown()