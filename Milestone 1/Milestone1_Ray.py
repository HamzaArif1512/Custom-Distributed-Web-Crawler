import time
import asyncio
import aiohttp
from selectolax.parser import HTMLParser
import itertools
from urllib.parse import urlparse
import networkx as nx 
import matplotlib.pyplot as plt
import pandas as pd
import ssl
from collections import defaultdict
#This script builds over the basic one by using aiohttp + 
# asyncio for asynchronous requests, selectolax for html parsing
domain_semaphores = defaultdict(lambda: asyncio.Semaphore(2))
headers = {
    "User-Agent": "PDC-Link-Extractor/1.0 (+https://github.com/witherthrottle; hamzaahmed452071@gmail.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
visited = set()
graph = dict()
async def extract_links(url, session):
    domain = urlparse(url).netloc
    semaphore = domain_semaphores[domain]
    async with semaphore:
        try:
            async with session.get(url, ssl=ssl_context,headers = headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    
                    if response.status == 200:
                        select = HTMLParser(await response.text())
                        visited.add(url)
                        
                    # avoids if conditions by using a css selector
                        valid_links = [a.attributes["href"] for a in select.css('a[href]')
                        if a.attributes.get("href", "").startswith("https://") ]
                        graph.setdefault(url, set()).update(valid_links)
                        return valid_links
                    else:
                        print(response)
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
    begin_time = time.time()
    numOfstartinglinks = 1
    depth = 2
    df = pd.read_csv("majestic_million.csv")
    rows = df[df['TLD'] == 'com'].sample(numOfstartinglinks)
    links = rows['Domain'].tolist()
    links = ['https://' + link for link in links]
    
    
    async with aiohttp.ClientSession(headers=headers) as session:
        # Create a list of taskss
        for i in range(depth):
            task_list = [extract_links(link, session) for link in links]
            #visited.update(links)
            # Gather them to run concurrently
            response = await asyncio.gather(*task_list)
            links = list(itertools.chain.from_iterable(response))
            links = [link for link in links if link not in visited]
    end_time = time.time()
    
    print(f"Total time of the async script of depth={depth} is: ", end_time-begin_time, "seconds.")
    G = nx.DiGraph()
    for node, neighbors in graph.items():
        for neighbor in neighbors:
            G.add_edge(node, neighbor)

    nx.draw(G, with_labels=False)
    plt.show()
if __name__ == "__main__":
    asyncio.run(main())