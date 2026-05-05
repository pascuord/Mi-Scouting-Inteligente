
import unicodedata
import json

def _norm_text(s: str) -> str:
    t = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")

nacionalidades_canon = ["Italia"]
nacionalidades_norm = set(_norm_text(n) for n in nacionalidades_canon)

print(f"Norm: {nacionalidades_norm}")

val_db = "Italia"
val_norm = _norm_text(val_db)
print(f"Val DB Norm: {val_norm}")
print(f"Match: {val_norm in nacionalidades_norm}")

val_db_accent = "España"
val_norm_accent = _norm_text(val_db_accent)
print(f"Val DB Accent Norm: {val_norm_accent}")
print(f"Match Accent: {val_norm_accent in set(_norm_text(n) for n in ['España'])}")
