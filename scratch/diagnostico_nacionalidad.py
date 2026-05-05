
import json
import polars as pl
from scouting.agents.agent1 import Agente1HardFilter

def test_diagnostic():
    print("--- Diagnóstico Técnico: Filtrado de Nacionalidad ---")
    
    # 1. Cargar datos
    db_path = "data/processed/merged/db_porteros.json"
    with open(db_path, "r") as f:
        data = json.load(f)
    
    df = pl.DataFrame(data)
    total_porteros = len(df)
    empty_nac = len(df.filter(pl.col("nacionalidad") == ""))
    
    print(f"Total porteros en DB: {total_porteros}")
    print(f"Porteros con 'nacionalidad' vacía: {empty_nac}")
    
    if total_porteros == empty_nac:
        print("CRÍTICO: El 100% de los porteros tienen la nacionalidad vacía.")
    
    # 2. Probar extracción del Agente 1
    a1 = Agente1HardFilter()
    query = "porteros italianos"
    nac_canon = a1.extraer_nacionalidades(query)
    print(f"\nConsulta: '{query}'")
    print(f"Nacionalidades extraídas por el Agente 1: {nac_canon}")
    
    # 3. Simular filtrado
    if nac_canon:
        # Esto es lo que hace el Agente 1 internamente
        from scouting.agents.agent1 import _norm_text
        nacionalidades_norm = set(_norm_text(n) for n in nac_canon)
        
        df_nac = df.with_columns(
            pl.col("nacionalidad").map_elements(_norm_text, return_dtype=pl.Utf8).alias("nacionalidad_norm")
        )
        
        df_final = df_nac.filter(pl.col("nacionalidad_norm").is_in(nacionalidades_norm))
        print(f"Resultados tras filtrar por nacionalidad '{nac_canon[0]}': {len(df_final)}")
    
    # 4. Mostrar diferencia con 'pais' (liga)
    print("\n--- Comparación con campo 'pais' (Liga) ---")
    query_pais = "porteros en Italia"
    paises_liga = a1.extraer_paises_de_liga(query_pais)
    print(f"Consulta: '{query_pais}'")
    print(f"Países de liga extraídos: {paises_liga}")
    
    if paises_liga:
        # Agente 1 usa ALIAS_TO_NACIONALIDAD para normalizar antes de filtrar por 'pais'
        from scouting.agents.agent1 import ALIAS_TO_NACIONALIDAD
        canon_targets = set()
        for p in paises_liga:
            norm_p = _norm_text(p)
            # Simplificamos la lógica del agente para el test
            for k, v in ALIAS_TO_NACIONALIDAD.items():
                if _norm_text(k) == norm_p or _norm_text(v) == norm_p:
                    canon_targets.add(v)
        
        df_pais = df.filter(pl.col("pais").is_in(canon_targets))
        print(f"Resultados tras filtrar por país de liga '{list(canon_targets)}': {len(df_pais)}")
        if len(df_pais) > 0:
            print("Ejemplo de portero encontrado:")
            print(f"  Nombre: {df_pais[0]['nombre']}")
            print(f"  Liga: {df_pais[0]['liga']}")
            print(f"  País (Liga): {df_pais[0]['pais']}")

if __name__ == "__main__":
    test_diagnostic()
