# Web Crawler Project (Milestone 1)

## Overview
This repository contains Milestone 1 work for a web crawler project focused on parallel and distributed crawling performance.

The project compares three crawler designs:
- Sequential crawler
- Ray Master-Worker crawler
- Ray Peer-to-Peer crawler

The main goal is to measure speed and throughput differences against a sequential baseline while building a crawl graph.

## What Is Included
- Ray-based parallelization experiments for Milestone 1
- Sequential baseline implementation for performance comparison
- Asyncio-based crawler experiments (supporting exploration; not required for Milestone 1 submission criteria)
- Benchmark notebooks and plots
- Seed dataset for crawl initialization

## Dataset
The crawler seeds are sampled from majestic_million.csv in the project root.

Source of dataset:
- Majestic Million report: https://majestic.com/reports/majestic-million

## Experimented Techniques
### 1) Sequential
Single-process async crawler used as the baseline.

### 2) Ray Master-Worker
Centralized coordination:
- One master actor holds global queue, visited set, and graph
- Multiple workers fetch and return discovered links

### 3) Ray Peer-to-Peer
Decentralized coordination:
- Workers own partitions of URL space
- Workers exchange discovered links directly
- Final graph is merged after execution

## Important Comparison Notes (Correctness and Fairness)
To avoid misleading conclusions, keep these points in mind:
- Hyperparameter grids are mostly aligned, but not identical across all runs.
- In current experiments, Sequential includes depth 3, while Ray sweeps may run only up to depth 2 in some notebooks/scripts.
- max_per_domain exists in all approaches, but enforcement semantics differ:
  - Sequential and Master-Worker apply a global-style domain cap.
  - Peer-to-Peer applies routing-time/local checks, which may behave less strictly than a single global counter.

Because of these differences, comparisons are strongest when filtered to exactly matching settings (same seeds, depth, and worker assumptions).

## Project Structure
- basic.py: initial baseline crawler prototype
- majestic_million.csv: seed domain dataset
- Milestone1.md: milestone documentation notes
- requirements.txt: Python dependencies
- Asyncio/
  - async.py
  - Milestone1_Asyncio.py
  - Milestone1_Asyncio_Mod.py
  - ASYNCIO_GUIDE.md
- Ray/
  - raymasterworker.py
  - raypeertopeer.py
  - Ray_Overview.md
- Notebooks/
  - crawler_benchmark.ipynb
  - notebook662de1dc8b (1).ipynb
  - notebook662de1dc8b (2).ipynb

## Quick Start
1. Create and activate a Python environment.
2. Install dependencies:
   pip install -r requirements.txt
3. Ensure majestic_million.csv is present in the root directory.
4. Run scripts or notebooks for experiments.

## Running Milestone 1 Experiments
Recommended:
- Use the notebooks in Notebooks/ for benchmark sweeps and visualizations.
- Use Ray scripts in Ray/ for direct architecture runs.

Typical outputs include:
- elapsed time
- URLs crawled
- edge counts
- throughput (URLs/second)
- saved benchmark figures

## Reproducibility Tips
- Keep random seeds fixed when sampling domains.
- Run with comparable depth and seed counts across techniques.
- Keep machine load stable between runs.
- Reinitialize Ray cleanly between independent benchmark sweeps.

## Notes
This repository includes additional exploratory files beyond strict Milestone 1 requirements (especially Asyncio variants), which are useful for understanding design trade-offs and performance behavior.