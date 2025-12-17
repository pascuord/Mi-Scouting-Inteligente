# src/scouting/etl/main_etl.py
from __future__ import annotations
import argparse
import asyncio
import time
import sys
import pathlib
from dotenv import load_dotenv

# --- Bootstrap para que funcione tanto con `python -m` como con ruta directa ---
# Raíz del proyecto = .../proyectosjg/
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ahora las imports absolutas funcionan en ambos casos
from src.scouting.etl.collect_fotmob import main_async as fotmob_main_async
from scouting.etl.collect_transfermarkt import run as tm_run

from src.scouting.etl.merge_data import run as merge_run
from src.scouting.etl.vector_store_indexing import run as index_run

load_dotenv()

def secs(t0: float) -> str:
    return f"{time.time() - t0:.1f}s"

def main():
    parser = argparse.ArgumentParser(description="Orquestador ETL ProyectosJG")
    parser.add_argument("--skip-fotmob", action="store_true", help="Saltar recolección FotMob")
    parser.add_argument("--skip-tm", action="store_true", help="Saltar recolección Transfermarkt")
    parser.add_argument("--skip-merge", action="store_true", help="Saltar merge")
    parser.add_argument("--skip-index", action="store_true", help="Saltar indexado FAISS")
    args = parser.parse_args()

    total_t0 = time.time()

    # 1) Fotmob
    if not args.skip_fotmob:
        print("\n=== [1/4] FOTMOB ===")
        t0 = time.time()
        asyncio.run(fotmob_main_async())
        print(f"[FOTMOB] Hecho en {secs(t0)}")
    else:
        print("\n=== [1/4] FOTMOB (saltado) ===")

    # 2) Transfermarkt
    if not args.skip_tm:
        print("\n=== [2/4] TRANSFERMARKT ===")
        t0 = time.time()
        tm_run()
        print(f"[TM] Hecho en {secs(t0)}")
    else:
        print("\n=== [2/4] TRANSFERMARKT (saltado) ===")

    # 3) Merge
    if not args.skip_merge:
        print("\n=== [3/4] MERGE ===")
        t0 = time.time()
        merge_run()
        print(f"[MERGE] Hecho en {secs(t0)}")
    else:
        print("\n=== [3/4] MERGE (saltado) ===")

    # 4) Indexado FAISS
    if not args.skip_index:
        print("\n=== [4/4] INDEXADO ===")
        t0 = time.time()
        index_run()
        print(f"[INDEX] Hecho en {secs(t0)}")
    else:
        print("\n=== [4/4] INDEXADO (saltado) ===")

    print(f"\n✅ ETL completa en {secs(total_t0)}")

def cli():
    # reusa tu main actual: parsea argumentos y llama a las fases
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-fotmob", action="store_true")
    parser.add_argument("--skip-tm", action="store_true")
    parser.add_argument("--skip-merge", action="store_true")
    args = parser.parse_args()
    main(skip_fotmob=args.skip_fotmob, skip_tm=args.skip_tm, skip_merge=args.skip_merge)  # o como se llame tu función


if __name__ == "__main__":
    main()
