import time
import asyncio
import aiohttp
from selectolax.parser import HTMLParser
import itertools
from urllib.parse import urlparse, urljoin, urlunparse, urldefrag
import networkx as nx 
import matplotlib.pyplot as plt
import pandas as pd
import ssl
from collections import defaultdict
import os
from dataclasses import dataclass
#This script builds over the basic one by using aiohttp + 
# asyncio for asynchronous requests, selectolax for html parsing
headers = {
    "User-Agent": "PDC-Link-Extractor/1.0 (+https://github.com/witherthrottle; hamzaahmed452071@gmail.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE


@dataclass
class CrawlConfig:
    num_starting_links: int = 3
    depth: int = 2
    request_timeout: int = 8
    per_domain_concurrency: int = 2
    max_urls_per_domain: int = 100
    same_domain_only: bool = False
    csv_file: str = "majestic_million.csv"
    tld_filter: str = "com"
    random_seed: int = 42


def load_config() -> CrawlConfig:
    # Easy config: defaults + optional environment overrides.
    config = CrawlConfig()
    config.num_starting_links = int(os.getenv("CRAWL_NUM_START", config.num_starting_links))
    config.depth = int(os.getenv("CRAWL_DEPTH", config.depth))
    config.request_timeout = int(os.getenv("CRAWL_TIMEOUT", config.request_timeout))
    config.per_domain_concurrency = int(os.getenv("CRAWL_PER_DOMAIN_CONCURRENCY", config.per_domain_concurrency))
    config.max_urls_per_domain = int(os.getenv("CRAWL_MAX_URLS_PER_DOMAIN", config.max_urls_per_domain))
    config.same_domain_only = os.getenv("CRAWL_SAME_DOMAIN_ONLY", str(config.same_domain_only)).lower() == "true"
    config.tld_filter = os.getenv("CRAWL_TLD", config.tld_filter)
    return config


def normalize_url(base_url, href):
    # Turn relative links into full links and remove small URL differences.
    if not href:
        return None

    raw = href.strip()
    if not raw or raw.startswith(("#", "mailto:", "javascript:", "tel:")):
        return None

    absolute = urljoin(base_url, raw) if base_url else raw
    absolute, _ = urldefrag(absolute)

    parsed = urlparse(absolute)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    # Normalize host and remove default ports.
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return None

    port = parsed.port
    if (parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443):
        netloc = hostname
    elif port:
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    path = parsed.path or "/"
    normalized = urlunparse((parsed.scheme.lower(), netloc, path, "", parsed.query, ""))
    return normalized


def can_visit_url(url, allowed_domains, config, scheduled_per_domain):
    parsed = urlparse(url)
    domain = parsed.netloc

    # Optional rule: stay in domains from the initial seed URLs only.
    if config.same_domain_only and domain not in allowed_domains:
        return False

    # Hard limit to avoid spending all time in one big domain.
    if scheduled_per_domain[domain] >= config.max_urls_per_domain:
        return False

    return True


async def extract_links(url, session, domain_semaphores, config, graph, crawled_ok):
    domain = urlparse(url).netloc
    semaphore = domain_semaphores[domain]
    async with semaphore:
        try:
            async with session.get(
                url,
                ssl=ssl_context,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=config.request_timeout),
            ) as response:
                    
                    if response.status == 200:
                        select = HTMLParser(await response.text())
                        crawled_ok.add(url)
                        
                        # Keep only clean, crawlable links.
                        valid_links = []
                        for a in select.css("a[href]"):
                            normalized = normalize_url(url, a.attributes.get("href", ""))
                            if normalized:
                                valid_links.append(normalized)

                        graph.setdefault(url, set()).update(valid_links)
                        return valid_links
                    else:
                        print(f"Non-200 status {response.status}: {url}")
                        return []
        except aiohttp.ClientConnectorDNSError:
            print(f"DNS failed (dead domain): {url}")
            return []
        except aiohttp.ClientConnectorCertificateError:
            print(f"SSL error: {url}")
            return []
        except aiohttp.ClientConnectorError:          # ← add this
            print(f"Connection refused: {url}")
            return []
        except aiohttp.ClientError as e:
            print(f"Connection error: {url} — {e}")
            return []
        except asyncio.TimeoutError:
            print(f"Timeout: {url}")
            return []
        except Exception as e:
            print(f"Unexpected error: {url} — {e}")
            return []

        


async def main():
    config = load_config()
    begin_time = time.time()

    graph = {}
    crawled_ok = set()
    seen_urls = set()
    scheduled_per_domain = defaultdict(int)

    domain_semaphores = defaultdict(lambda: asyncio.Semaphore(config.per_domain_concurrency))

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(script_dir, config.csv_file)
    df = pd.read_csv(csv_path)
    rows = df[df["TLD"] == config.tld_filter].sample(config.num_starting_links, random_state=config.random_seed)
    links = rows['Domain'].tolist()
    links = [normalize_url(None, "https://" + link) for link in links]
    links = [link for link in links if link]

    allowed_domains = {urlparse(link).netloc for link in links}

    # Mark seed URLs as seen so we don't schedule them twice.
    for link in links:
        seen_urls.add(link)
        scheduled_per_domain[urlparse(link).netloc] += 1
    
    
    async with aiohttp.ClientSession(headers=headers) as session:
        # Breadth-first crawl by depth.
        for i in range(config.depth):
            if not links:
                print(f"Depth {i}: no links left to crawl, stopping early.")
                break

            task_list = [extract_links(link, session, domain_semaphores, config, graph, crawled_ok) for link in links]
            response = await asyncio.gather(*task_list)

            candidate_links = list(itertools.chain.from_iterable(response))
            next_links = []

            # Dedup + domain/depth constraints before next round.
            for link in candidate_links:
                if link in seen_urls:
                    continue
                if not can_visit_url(link, allowed_domains, config, scheduled_per_domain):
                    continue

                seen_urls.add(link)
                scheduled_per_domain[urlparse(link).netloc] += 1
                next_links.append(link)

            links = next_links

    end_time = time.time()
    
    print(f"Total time of the async script of depth={config.depth} is: {end_time-begin_time:.2f} seconds.")
    print(f"Crawled pages with status 200: {len(crawled_ok)}")
    print(f"Unique URLs discovered/scheduled: {len(seen_urls)}")

    G = nx.DiGraph()
    for node, neighbors in graph.items():
        for neighbor in neighbors:
            G.add_edge(node, neighbor)

    if G.number_of_edges() == 0:
        print("Graph is empty. Try increasing seeds/depth or relaxing domain rules.")
        return

    plt.figure(figsize=(12, 8))
    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, with_labels=False, node_size=25, width=0.4)
    plt.title("Crawl Graph")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    asyncio.run(main())