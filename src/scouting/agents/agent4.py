# src/scouting/agents/agente4.py
from __future__ import annotations
from typing import Tuple, List, Dict, Any
import plotly.graph_objects as go

class GraphComparisonAgent:
    """
    Construye dos gráficos radar (percentil y percentil_per90) para los 3 jugadores top.
    Supone que 'resultados' viene de Agente2 con las claves:
      - nombre
      - metricas_clave: Dict[str, float]
      - detalle: Dict[str, {raw: {percentile, percentile_per90, ...}, ...}]
    """
    def __init__(self) -> None:
        pass

    def _safe_float(self, x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def _crear_radar_plotly(self, datos: Dict[str, List[float]], metricas: List[str], titulo: str) -> go.Figure:
        fig = go.Figure()

        # Cierra el polígono repitiendo el primer punto
        categorias = metricas + [metricas[0]] if metricas else []

        for nombre, valores in datos.items():
            serie = list(valores) if valores else []
            if metricas and valores:
                serie = serie + [serie[0]]
            fig.add_trace(go.Scatterpolar(
                r=serie,
                theta=categorias,
                fill='toself',
                name=nombre
            ))

        fig.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 100])
            ),
            showlegend=True,
            title=titulo,
            margin=dict(l=40, r=40, t=60, b=40),
        )
        return fig

    def graph_comparison(self, resultados: List[Dict]) -> Tuple[go.Figure, go.Figure]:
        assert len(resultados) == 3, "Se requieren exactamente 3 jugadores para la comparación"

        # Usamos las 8 métricas elegidas globalmente por Agente2 (mismo orden)
        metricas = list(resultados[0].get('metricas_clave', {}).keys())
        nombres = [r.get('nombre', f'Jugador {i+1}') for i, r in enumerate(resultados)]

        # Extraer percentiles y percentiles_per90 con tolerancia a faltantes
        datos_percentil = {}
        datos_per90 = {}
        for r in resultados:
            nombre = r.get('nombre', 'Jugador')
            detalle = r.get('detalle', {}) or {}
            percentiles = []
            percentiles90 = []
            for m in metricas:
                raw = (detalle.get(m, {}) or {}).get('raw', {}) or {}
                percentiles.append(self._safe_float(raw.get('percentile')))
                percentiles90.append(self._safe_float(raw.get('percentile_per90')))
            datos_percentil[nombre] = percentiles
            datos_per90[nombre] = percentiles90

        fig1 = self._crear_radar_plotly(datos_percentil, metricas, "Comparativa percentiles (métricas clave)")
        fig2 = self._crear_radar_plotly(datos_per90, metricas, "Comparativa percentiles por 90' (métricas clave)")
        return fig1, fig2
