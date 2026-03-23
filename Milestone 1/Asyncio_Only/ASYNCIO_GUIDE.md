# Understanding Asyncio: Web Crawler Implementation Guide

## Table of Contents
1. [Fundamentals of Asyncio](#fundamentals-of-asyncio)
2. [Project Goals](#project-goals)
3. [Basic Implementation (Milestone1_Asyncio.py)](#basic-implementation)
4. [Enhanced Implementation (Milestone1_Asyncio_Mod.py)](#enhanced-implementation)
5. [Key Differences](#key-differences)
6. [When to Use Which](#when-to-use-which)

---

## Fundamentals of Asyncio

### What is Async/Await?

Think of a restaurant:
- **Synchronous (old way)**: One waiter takes an order, waits for the kitchen to finish cooking, serves the meal, then takes the next order. Super slow!
- **Asynchronous (new way)**: One waiter takes an order, immediately moves to the next customer while the kitchen starts cooking. When food is ready, it gets served. Much faster!

### Asyncio in Python

**Asyncio** is Python's built-in tool that lets you write code that does many things at the same time, but on a single thread (one processor core).

**Key concepts:**

| Term | Simple Explanation |
|------|-------------------|
| **async function** | A function that can pause and let other code run while it waits |
| **await** | "Pause here until this slow operation finishes, then continue" |
| **Event loop** | A manager that keeps track of all tasks and decides which one to run next |
| **Coroutine** | The actual async function waiting to be executed |
| **Semaphore** | A traffic cop that says "only 2 of you can go at the same time" |

### Why Use Async for Web Crawling?

Web crawling involves lots of **waiting**:
- Waiting for network response from a server
- Waiting for DNS lookup
- Waiting for page to load

While you wait for one website's response, you can fetch other websites! This makes crawling **much faster**.

---

## Project Goals

### The Big Picture

We're building a **distributed web crawler** that:

1. **Starts with seed URLs** (a few starting websites)
2. **Downloads and parses pages** to extract links
3. **Follows links recursively** up to a certain depth
4. **Builds a graph** showing which page links to which page
5. **Later runs PageRank** to find the most important pages

### Why It Matters

This is exactly how search engines work (Google, Bing, etc.):
- Crawlers fetch pages from across the internet
- They build a graph of how pages link to each other
- PageRank algorithm figures out which pages are most trustworthy/important
- Search results are ranked by importance

---

## Basic Implementation

### File: `Milestone1_Asyncio.py`

This is the **simple, straightforward** version.

#### How It Works

```python
async def extract_links(url, session):
    # Fetch ONE page and extract links from it
    response = await session.get(url)  # Wait for response
    # Parse HTML to find links
    # Return list of links found
```

**The main crawl loop:**

```python
for i in range(depth):  # For each level
    task_list = [
        extract_links(link, session) 
        for link in links  # Create tasks for ALL current links
    ]
    response = await asyncio.gather(*task_list)  # Run ALL at once
    links = [...]  # Get ready for next depth level
```

#### Key Features

✅ **Simple and easy to understand** - minimal code  
✅ **Works** - fetches pages and builds a graph  
✅ **Uses aiohttp** - async HTTP library  
✅ **Per-domain rate limiting** - doesn't hammer one domain  

#### Limitations

❌ **Hardcoded settings** - can't easily change parameters  
❌ **URL filtering is too strict** - only accepts `https://` links, rejects relative links  
❌ **No URL normalization** - treats `example.com/page` and `example.com/page/` as different  
❌ **Weak deduplication** - URLs only marked as visited after successful fetch  
❌ **No depth controls** - visits all links without domain restrictions  

---

## Enhanced Implementation

### File: `Milestone1_Asyncio_Mod.py`

This is the **production-ready, flexible** version with all the missing features.

#### New Features Added

### 1. Configuration Management

```python
@dataclass
class CrawlConfig:
    num_starting_links: int = 3          # How many seed URLs
    depth: int = 2                       # How many levels deep
    request_timeout: int = 8             # Timeout for each request
    per_domain_concurrency: int = 2      # Max simultaneous requests per site
    max_urls_per_domain: int = 100       # Don't crawl more than this from one site
    same_domain_only: bool = False       # Stay in seed domains only?
```

**Why this matters:** You can now change behavior without editing code!

```bash
# Set via environment variables
export CRAWL_DEPTH=3
export CRAWL_NUM_START=5
python Milestone1_Asyncio_Mod.py
```

### 2. URL Normalization

**Problem:** These should be treated as the same URL, but aren't:
- `https://example.com/page`
- `https://example.com/page#section`
- `Example.Com/page` (different case)
- `https://example.com:443/page` (default HTTPS port)

**Solution:**
```python
def normalize_url(base_url, href):
    # Convert relative to absolute: /page → https://example.com/page
    # Remove fragments: #section → gone
    # Lowercase domain: Example.Com → example.com
    # Remove default ports: :443 → gone
    # Return clean, comparable URL
```

### 3. Smart Link Filtering

**Old approach:** Only accept `https://` links

**New approach:** 
```python
# Accept both http:// and https://
# Resolve relative links (e.g., /about → https://example.com/about)
# Skip fake links (mailto:, javascript:, #anchors)
# Extract from proper <a href="..."> tags
```

This dramatically increases the number of links found!

### 4. Better Deduplication

**Old approach:**
```python
visited = set()
if link in visited:
    skip it
```

**New approach:**
```python
seen_urls = set()           # URLs we already scheduled for crawling
crawled_ok = set()          # URLs that returned 200 status
scheduled_per_domain = {}   # Track how many URLs per domain
```

This prevents:
- Scheduling the same URL twice
- Crawling too many pages from one domain
- Wasting time on dead URLs

### 5. Depth and Domain Constraints

```python
def can_visit_url(url, allowed_domains, config, scheduled_per_domain):
    # Don't visit if already over domain limit
    if scheduled_per_domain[domain] >= config.max_urls_per_domain:
        return False
    
    # Optional: only stay in seed domains
    if config.same_domain_only and domain not in allowed_domains:
        return False
    
    return True
```

---

## Key Differences

### Side-by-Side Comparison

| Feature | Asyncio.py | Asyncio_Mod.py |
|---------|-----------|----------------|
| **Config system** | Hardcoded | Flexible (env vars + defaults) |
| **URL normalization** | None | Full (relative, fragments, case, ports) |
| **Link filtering** | Only https:// | Both http/https, resolves relative |
| **Deduplication** | Weak (post-fetch) | Strong (pre-fetch, per-domain limit) |
| **Domain constraints** | None | Optional same-domain mode + per-domain cap |
| **Error messages** | Basic | Detailed status and progress |
| **Code size** | ~80 lines | ~150 lines |
| **Easy to test** | Hard | Easy (pass config object) |
| **Production ready** | No | Yes |

### Code Architecture

**Asyncio.py structure:**
```
Global variables (domain_semaphores, visited, graph)
    ↓
extract_links() function
    ↓
main() - hardcoded settings
```

**Asyncio_Mod.py structure:**
```
CrawlConfig dataclass
    ↓
load_config() function
    ↓
normalize_url() utility
    ↓
can_visit_url() utility
    ↓
extract_links() - takes config parameter
    ↓
main() - uses config everywhere
```

### Real Example: What Gets Crawled?

**Starting with:** `https://example.com`

**Page 1 has these links:**
```html
<a href="https://example.com/page1">Page 1</a>
<a href="/page2">Relative link (current domain)</a>
<a href="https://other-site.com/news">External site</a>
<a href="#section">Anchor (not real page)</a>
<a href="javascript:void(0)">Fake link</a>
<a href="HTTPS://EXAMPLE.COM/PAGE1">Same as page 1 (different case)</a>
```

**Asyncio.py finds:**
- ✅ `https://example.com/page1`
- ❌ `/page2` (relative, rejected)
- ✅ `https://other-site.com/news`
- ❌ `#section` (starts with #)
- ❌ `javascript:...` (caught by exception)
- ❌ Duplicate due to case difference

**Result:** 2 links, misses internal link

**Asyncio_Mod.py finds:**
- ✅ `https://example.com/page1`
- ✅ `https://example.com/page2` (resolved!)
- ✅ `https://other-site.com/news`
- ❌ `#section` (filtered)
- ❌ `javascript:...` (filtered)
- ✅ Detects duplicate (normalized to same URL)

**Result:** 3 unique links, found internal link!

---

## When to Use Which

### Use `Asyncio.py` if:
- You're learning how async crawling works
- You want minimal code to understand the concepts
- You're running quick tests
- It's a school assignment focused on async/await fundamentals

### Use `Asyncio_Mod.py` if:
- You need a real crawler that finds more links
- You want to adjust parameters without rewriting code
- You're building something that might grow/change
- You need proper deduplication and domain control
- You want to avoid crawling the same page twice
- You're going to extend it (add more features)

---

## How They Both Use Asyncio

Both versions share the same **core async pattern:**

```python
async def main():
    async with aiohttp.ClientSession() as session:
        for depth_level in range(depth):
            # Create async tasks for all current URLs
            tasks = [fetch_and_parse(url, session) for url in current_urls]
            
            # Wait for ALL to complete at same time
            results = await asyncio.gather(*tasks)
            
            # Combine results and prepare next level
            current_urls = combine_and_deduplicate(results)
```

**Why this is fast:**
- Instead of: fetch 1 page (5 sec) → fetch next (5 sec) → ...
- We do: fetch 10 pages **at the same time** (5 sec total)

With 100 pages at depth 2:
- **Sequential:** ~500 seconds (8+ minutes)
- **Asyncio:** ~10 seconds (50x faster!)

---

## Summary

| Aspect | Simple Answer |
|--------|---------------|
| **What is Asyncio?** | Python's way to do many things at once without threads |
| **Why use it here?** | Web requests spend time waiting - do other work while waiting |
| **Which to use?** | `Asyncio_Mod.py` for anything real, `Asyncio.py` for learning |
| **Main improvement?** | Better config, URL handling, and deduplication |

Both are **async** - the difference is in features and flexibility, not speed fundamentals.

---

## Next Steps

1. Run `Asyncio.py` with 1 seed to see basic crawling
2. Run `Asyncio_Mod.py` with more seeds and greater depth
3. Try environment variables:
   ```bash
   export CRAWL_DEPTH=3
   export CRAWL_NUM_START=10
   python Milestone1_Asyncio_Mod.py
   ```
4. Compare the graph output - Mod version will have more edges!
