import requests
from bs4 import BeautifulSoup
from collections import deque
import time


headers = {
    "User-Agent": "PDC-Link-Extractor/1.0 (+https://github.com/witherthrottle; hamzaahmed452071@gmail.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5"
}

def extract_links_basic(url):
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'lxml')
            a_tags = soup.find_all('a', href=True)
            valid_links = [a["href"]  for a in a_tags if a ["href"] and "wikipedia" in a["href"]]

            return valid_links
        else:
            return []
    except:
        return []
        

if __name__ == "__main__":
    begin_time = time.time()
    total_links = list()
    queue = deque()
    queue.extend(extract_links_basic("https://en.wikipedia.org/wiki/Main_Page"))
    visited = set()
    early_stop = 1000
    start = 0
    while len(queue) != 0:
        if start == early_stop:
            break
        x = queue.pop()
        if x in visited or x is None:
            continue
        visited.add(x)
        total_links += extract_links_basic(x)
        start+=1
    end_time = time.time()
    print("Total time of the basic script of depth=1 is: ", end_time-begin_time, "seconds.")
    print("Total unique links visited are: ", len(visited))
        
        
       
       
       