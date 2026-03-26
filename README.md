# MSML606 Project - LegiMap

## Requirements

- Python 3.9+
- pip

---

## Setup

```bash
git clone https://github.com/<your-username>/legimap.git
cd legimap

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---


## Run the web app

```bash
PYTHONPATH=. python src/api/app.py
```

Open **http://localhost:5000** in your browser.

---

## Run individual algorithm modules

```bash
# Preprocessing
PYTHONPATH=. python src/preprocessing/normalise.py
PYTHONPATH=. python src/preprocessing/build_index.py data/toy_cases.jsonl

# Algorithms
PYTHONPATH=. python src/algorithms/hash_table.py
PYTHONPATH=. python src/algorithms/nary_tree.py
PYTHONPATH=. python src/algorithms/seed_expand.py

# Evaluation
PYTHONPATH=. python src/evaluation/eval_hash.py
PYTHONPATH=. python src/evaluation/eval_recall.py
```

---

## Project structure

```
legimap/
├── data/
│   ├── generate_toy_dataset.py
│   ├── toy_cases.jsonl
│   └── toy_cases.json
├── src/
│   ├── preprocessing/
│   │   ├── normalise.py
│   │   ├── ingest.py
│   │   └── build_index.py
│   ├── algorithms/
│   │   ├── hash_table.py
│   │   ├── nary_tree.py
│   │   └── seed_expand.py
│   ├── evaluation/
│   │   ├── eval_hash.py
│   │   └── eval_recall.py
│   └── api/
│       ├── app.py
│       └── templates/index.html
├── demo_notebook.ipynb
└── requirements.txt
```

---

## Windows users

Replace `PYTHONPATH=.` with:

```powershell
$env:PYTHONPATH="."
```

Or run as a module:

```bash
python -m src.evaluation.eval_hash
```

---

## Author

Amey Hengle · UID 122283961 · MSML606 Spring 2026
