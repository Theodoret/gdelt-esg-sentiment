# ESG Media Sentiment Analysis Pipeline (GDELT)

Analyzes GDELT Global Knowledge Graph (GKG) data to measure ESG (Environmental,
Social, Governance) sentiment in media coverage, attributed by country and
tracked over time. The pipeline is orchestrated from `main.ipynb`; each stage
is a standalone module:

| Stage | Module | Purpose |
| :--- | :--- | :--- |
| Download | `download_raw.py` | Fetch GDELT GKG batches from the official server |
| Fetch | `fetch_raw.py` | Load raw `.gkg.csv` files, filter by date range |
| Preprocess | `preprocess.py` | NA handling, dedup, column retention |
| ESG classify | `esg_classify.py` | Multi-label E/S/G tagging |
| Tone | `tone.py` | Extract tone / sentiment from `V2Tone` |
| Geo attribute | `geo_attr.py` | Attribute media source & location to countries |
| Aggregate | `aggregate.py` | Aggregate metrics by date x country x ESG category |
| Visualize | `viz_map.py` | Interactive choropleth maps with time slider |

---

## Virtual Environment Setup

The project uses a Python 3.13 virtual environment at `main/.venv`. Two files
make it reproducible on any machine:

- `requirements.txt` — all dependencies pinned to exact versions
- `setup_venv.sh` — creates the venv and installs the dependencies

### Quick start (recommended)

```bash
cd main
./setup_venv.sh
```

This creates `.venv` (if missing) and installs everything from
`requirements.txt`. It uses `uv` when available (much faster) and falls back
to `python3 -m venv` + `pip` otherwise.

### Recreating from scratch

If `.venv` is broken or you want a clean environment:

```bash
cd main
./setup_venv.sh --force
```

`--force` deletes the existing `.venv` and recreates it.

### Manual setup

If you prefer to do it by hand:

```bash
cd main

# Option A: uv (fast)
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements.txt

# Option B: pip
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

### Requirements

- **Python 3.13** (the venv is pinned to it; `uv` will fetch it automatically
  if not installed)
- **uv** (optional but recommended) or **pip**
- Internet access on first install (packages are fetched from PyPI)

### Running the notebook

```bash
cd main
.venv/bin/jupyter notebook main.ipynb
```

Or open `main.ipynb` in VS Code and select the `.venv` kernel
(`main/.venv/bin/python`).

> **Important**: after pulling updated code, restart the kernel
> (Kernel → Restart & Run All) so the modules are re-imported. A stale kernel
> keeps old module versions in memory and causes confusing errors.

### Troubleshooting

| Problem | Fix |
| :--- | :--- |
| `uv: command not found` | Install uv (`curl -LsSf https://astral.sh/uv/install.sh \| sh`) or rely on the pip fallback |
| `Python 3.13 not found` | Install Python 3.13, or let uv download it (`uv python install 3.13`) |
| Old code still running | Kernel → Restart & Run All |
| Missing packages after setup | Re-run `./setup_venv.sh` (it re-installs from `requirements.txt`) |

---

## Data Layout

```
main/
├── data/
│   ├── raw/        # downloaded GDELT .gkg.csv batches
│   ├── processed/  # cleaned intermediate data
│   └── output/     # aggregated metrics + interactive map HTML
├── *.py            # pipeline modules
├── main.ipynb      # orchestrator notebook
├── requirements.txt
└── setup_venv.sh
```
