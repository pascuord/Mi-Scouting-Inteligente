# src/scouting/agents/agente4.py
from __future__ import annotations
from typing import Tuple, List, Dict, Any, Optional
import os
import plotly.graph_objects as go
import json, ast, logging


logger = logging.getLogger(__name__)


# --- NUEVO: imports para pizzas (con tolerancia si no están) ---
_MPL_AVAIL = True
try:
    import matplotlib.pyplot as plt
    from PIL import Image, ImageDraw, ImageFont, ImageChops
    from mplsoccer import PyPizza, add_image, FontManager
    from io import BytesIO
    import plotly.io as pio
    
except Exception:
    _MPL_AVAIL = False

# --- NUEVO: constantes de color y posicionamiento para pizzas ---
BLOCK_COLORS_FIELD = {
    "Shooting":   "#1a78cf",  # azul
    "Passing":    "#ff9300",  # naranja
    "Possession": "#7bc8a4",  # verde-agua
    "Defending":  "#d70232",  # rojo
}
BLOCK_COLORS_GK = {
    "Goalkeeping": "#1a78cf",
    "Distribution": "#ff9300",
}

OFFENSIVE_POS = {
    "second striker", "centre-forward", "center forward", "forward",
    "left winger", "right winger", "winger", "attacking midfield", "attacking midfielder"
}
DEF_MID_CB_POS = {"defensive midfield", "defensive midfielder", "centre-back", "center back", "cb"}
CM_FB_POS = {"central midfield", "central midfielder", "full-back", "right-back", "left-back", "rb", "lb"}

def _norm_pos(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _short_label(s: str) -> str:
    """
    Parte la etiqueta en como mucho 2 líneas, sin romper palabras,
    equilibrando el nº de caracteres por línea y aplicando overrides
    para casos conocidos.
    """
    if not s:
        return s

    # Normalización de typos comunes
    s = s.replace("Possesion", "Possession").strip()

    # Overrides manuales (prioritarios)
    overrides = {
        "Possession won final 3rd": "Possession won\nfinal 3rd",
        "Touches in opposition box": "Touches in\nopposition box",
        "Successful crosses": "Successful\ncrosses",
        "Accurate long balls": "Accurate\nlong balls",
        "xG excl. penalty": "xG excl.\npenalty",
        "Duels won %": "Duels won\n%",
        "Dribbles success rate": "Dribbles\nsuccess rate",
        "Aerials won %": "Aerials won\n%",
        "Shots on target": "Shots\non target",
    }
    if s in overrides:
        return overrides[s]

    words = s.split()
    if len(words) <= 2:
        # corto: una sola línea
        return s

    # límites suaves para evitar líneas muy desiguales
    MAX_LINE = 14    # máx. chars por línea
    # probamos todos los cortes posibles y elegimos el más equilibrado
    candidates = []
    for i in range(1, len(words)):
        left = " ".join(words[:i])
        right = " ".join(words[i:])
        len_l, len_r = len(left), len(right)
        # preferimos soluciones dentro del límite por línea
        in_bounds = (len_l <= MAX_LINE and len_r <= MAX_LINE)
        diff = abs(len_l - len_r)
        # penalizamos un poco si se sale del límite
        penalty = 10 if not in_bounds else 0
        score = diff + penalty
        candidates.append((score, penalty, diff, i, left, right))

    # el mejor: menor score, y si empata menor diff
    candidates.sort(key=lambda x: (x[0], x[2]))
    _, _, _, i_best, left_best, right_best = candidates[0]
    return left_best + "\n" + right_best


def _to_float(x: Any) -> float:
    try:
        return float(x)
    except Exception:
        return 0.0

def _pick_percentile(rec: Dict[str, Any], use_per90: bool) -> int:
    key = "percentile_per90" if use_per90 else "percentile"
    try:
        return int(round(float((rec or {}).get(key, 0))))
    except Exception:
        return 0

# --- NUEVO: listas de estadísticas exactas según tu especificación ---

# Jugadores
SHOOTING_STATS = [
    "Goals", "xGOT", "xG excl. penalty", "Shots", "Shots on target",
]
PASSING_STATS = [
    "Assists", "xA", "Pass accuracy", "Accurate long balls", "Chances created", "Successful crosses",
]
POSSESSION_BASE = [
    "Dribbles", "Dribbles success rate", "Dispossessed", "Fouls won",
    # + ("Touches in opposition box" si ofensivo, si no "Touches")
]
DEFENDING_COMMON = ["Duels won %", "Aerials won %", "Interceptions", "Recoveries"]
DEFENDING_OF     = ["Possession won final 3rd"]
DEFENDING_DM_CB  = ["Blocked scoring attempt"]
DEFENDING_CM_FB  = ["Dribbled past"]

# Porteros
GOALKEEPING_STATS = [
    "Conceded", "Clean sheets", "Penalties saved", "Saves", "Save percentage",
    "Goals prevented", "Penalty goals faced", "Penalty goals conceded", "Penalty goals saves",
    "Error led to goal", "Acted as sweeper", "High claims",
]
DISTRIBUTION_STATS = ["Pass accuracy", "Accurate long balls", "Long ball accuracy"]


class GraphComparisonAgent:
    """
    Construye dos gráficos radar (percentil y percentil_per90) para los 3 jugadores top
    y (NUEVO) un collage 3×pizza de perfil (resumen por bloques) con reglas de posición.
    """
    def __init__(self, per90_minutes_threshold: int = 750) -> None:
        self.per90_minutes_threshold = per90_minutes_threshold

        # fuentes (solo si hay mplsoccer)
        if _MPL_AVAIL:
            try:
                self.font_normal = FontManager(
                    'https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Regular.ttf'
                )
                self.font_italic = FontManager(
                    'https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Italic.ttf'
                )
                self.font_bold = FontManager(
                    'https://raw.githubusercontent.com/google/fonts/main/apache/robotoslab/RobotoSlab[wght].ttf'
                )
                self.font_title = FontManager(
                    'https://github.com/google/fonts/blob/main/ofl/bungeeinline/BungeeInline-Regular.ttf?raw=true'
                )
            except Exception:
                self.font_normal = self.font_italic = self.font_bold = self.font_title = None

    # ---------------- RADARES (tu código original) ----------------
    def _safe_float(self, x: Any) -> float:
        try:
            return float(x)
        except Exception:
            return 0.0

    def _crear_radar_plotly(
                            self,
                            datos: Dict[str, List[float]],
                            metricas: List[str],
                            titulo: str,
                            showlegend: bool = True,
                            palette: List[str] | None = None,
                        ) -> go.Figure:
        fig = go.Figure()
        categorias = metricas + [metricas[0]] if metricas else []
        if palette is None:
            palette = ["#1f77b4", "#ff7f0e", "#2ca02c"]  # azul / naranja / verde

        for idx, (nombre, valores) in enumerate(datos.items()):
            serie = list(valores) if valores else []
            if metricas and valores:
                serie = serie + [serie[0]]
            color = palette[idx % len(palette)]
            fig.add_trace(go.Scatterpolar(
                r=serie,
                theta=categorias,
                fill='toself',
                name=nombre,
                line=dict(color=color),
                fillcolor=color.replace("#", "rgba(") if False else None  # mantenemos estilo por defecto
            ))

        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=showlegend,
            title=titulo,
            margin=dict(l=40, r=40, t=60, b=40),
        )
        return fig

    def build_radar_collage(
                            self,
                            resultados: List[Dict],
                            out_dir: str,
                            filename: str = "radars_collage.png",
                            width: int = 1200,        # ancho base de CADA radar
                            legend_width: int = 240   # panel de leyenda (estrecho, solo texto grande)
                        ) -> str:
        """
        Collage vertical con:
        - Título global MUY grande arriba (rojo)
        - Subtítulo centrado de 'Total Percentiles' por ENCIMA del primer radar (azul)
        - Subtítulo centrado de 'Percentiles per 90' por ENCIMA del segundo radar (azul)
        - Leyenda grande a la derecha, alineada a la altura del subtítulo superior (verde)
        - Márgenes compactos (negro)
        """
        assert len(resultados) == 3, "Se requieren exactamente 3 jugadores para la comparación"
        palette = ["#1f77b4", "#ff7f0e", "#2ca02c"]
        L_MARGIN = 12   # margen izquierdo interno del radar
        R_MARGIN = 12   # margen derecho interno del radar (usado para alinear la leyenda)


        # ======== datos ========
        metricas = list(resultados[0].get('metricas_clave', {}).keys())
        nombres  = [r.get('nombre', f'Jugador {i+1}') for i, r in enumerate(resultados)]

        datos_total, datos_p90 = {}, {}
        for r in resultados:
            nombre  = r.get('nombre', 'Jugador')
            detalle = r.get('detalle', {}) or {}
            t, p90 = [], []
            for m in metricas:
                raw = (detalle.get(m, {}) or {}).get('raw', {}) or {}
                t.append(self._safe_float(raw.get('percentile')))
                p90.append(self._safe_float(raw.get('percentile_per90')))
            datos_total[nombre] = t
            datos_p90[nombre]   = p90

        # ======== radar helper sin títulos ni leyenda, márgenes mínimos ========
        def _radar(datos):
            fig = go.Figure()
            cats = metricas + [metricas[0]] if metricas else []
            for idx, (nombre, vals) in enumerate(datos.items()):
                serie = list(vals) if vals else []
                if metricas and vals:
                    serie = serie + [serie[0]]
                color = palette[idx % len(palette)]
                fig.add_trace(go.Scatterpolar(
                    r=serie, theta=cats, fill='toself', name=nombre,
                    line=dict(color=color)
                ))
            fig.update_layout(
                showlegend=False,
                margin=dict(l=L_MARGIN, r=R_MARGIN, t=18, b=18),  # muy compacto
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            )
            return fig

        fig1 = _radar(datos_total)
        fig2 = _radar(datos_p90)

        # Render nítido sin “scale” para controlar el ancho exacto
        h_each = int(width * 0.68)
        img1 = Image.open(BytesIO(pio.to_image(fig1, format="png", scale=1, width=width, height=h_each)))
        img2 = Image.open(BytesIO(pio.to_image(fig2, format="png", scale=1, width=width, height=h_each)))

        img_w = max(img1.width, img2.width)  # ancho real

        # ======== layout del lienzo ========
        GLOBAL_TITLE_H = 90   # banda superior reservada
        SUB_H          = 60   # banda de subtítulo por radar (azul)
        GAP_RADARS     = 25   # espacio vertical entre radar1 y radar2

        stack_w = img_w
        stack_h = SUB_H + img1.height + GAP_RADARS + SUB_H + img2.height
        total_w = img_w + legend_width
        total_h = GLOBAL_TITLE_H + stack_h

        canvas = Image.new("RGB", (total_w, total_h), (255, 255, 255))
        draw   = ImageDraw.Draw(canvas)

        # ======== fuentes grandes (usa Liberation si está; fallback a default) ========
        def _load_font(name: str, size: int):
            candidates = [
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            ]
            for p in candidates:
                try:
                    return ImageFont.truetype(p, size=size)
                except Exception:
                    continue
            return ImageFont.load_default()

        FONT_GLOBAL = _load_font("global", 34)   
        FONT_SUB    = _load_font("sub",    22)   
        FONT_LEG    = _load_font("leg",    22)   

        # ======== título global (rojo) muy grande y centrado arriba ========
        title = "Percentiles Comparative in Key Metrics"
        draw.text(((total_w // 2)-20, 20), title, fill=(20,20,20), anchor="mm", font=FONT_GLOBAL)

        # ======== subtítulos centrados por ENCIMA de cada radar (azul) ========
        # posiciones de las bandas de subtítulo:
        top_sub_y = GLOBAL_TITLE_H + SUB_H // 2
        bot_sub_y = GLOBAL_TITLE_H + SUB_H + img1.height + GAP_RADARS + SUB_H // 2

        draw.text((stack_w // 2, top_sub_y), "Total Percentiles",      fill=(40,40,40), anchor="mm", font=FONT_SUB)
        draw.text((stack_w // 2, bot_sub_y), "Percentiles per 90",     fill=(40,40,40), anchor="mm", font=FONT_SUB)

        # ======== pegar los radares justo DEBAJO de cada banda de subtítulo ========
        y0 = GLOBAL_TITLE_H + SUB_H
        canvas.paste(img1, (0, y0))
        y1 = GLOBAL_TITLE_H + SUB_H + img1.height + GAP_RADARS + SUB_H
        canvas.paste(img2, (0, y1))

        # ======== leyenda grande, alineada a la altura del subtítulo superior ========
                # Leyenda a la derecha: arranca justo a la misma x que el borde derecho del radar
        GUTTER = 2  # separa 2 px si quieres un pelín de aire
        legend_x = img_w - 20*R_MARGIN + GUTTER   # alineado con el borde derecho del radar
        legend_y = top_sub_y - 14              # altura como ya tenías (te gusta así)

        box     = 20
        space   = 12
        line_h  = 28
        for i, name in enumerate(nombres):
            color_hex = palette[i % len(palette)]
            rgb = tuple(int(color_hex[j:j+2], 16) for j in (1,3,5))
            y = legend_y + i * line_h
            # cuadro de color
            draw.rectangle([legend_x, y, legend_x + box, y + box], fill=rgb, outline=(80,80,80))
            # texto
            draw.text((legend_x + box + space, y + box // 2), name, fill=(25,25,25), anchor="lm", font=FONT_LEG)



        def _trim_whitespace(img: Image.Image, pad_left=24, pad_right=24, pad_top=12, pad_bottom=12) -> Image.Image:
            """
            Recorta blancos en torno al contenido y deja el padding indicado.
            """
            bg = Image.new(img.mode, img.size, (255, 255, 255))
            diff = ImageChops.difference(img, bg)
            bbox = diff.getbbox()
            if not bbox:  # si no detecta diferencias, no recorta
                return img
            l, t, r, b = bbox
            l = max(0, l - pad_left)
            t = max(0, t - pad_top)
            r = min(img.width,  r + pad_right)
            b = min(img.height, b + pad_bottom)
            return img.crop((l, t, r, b))

        # === recorte final con el margen que quieres (ajusta estos números a tu gusto) ===
        canvas = _trim_whitespace(canvas, pad_left=15, pad_right=15, pad_top=12, pad_bottom=12)


        # ======== clamp Telegram ========
        MAX_SIDE = 3840
        w, h = canvas.size
        if max(w, h) > MAX_SIDE:
            scale = MAX_SIDE / max(w, h)
            canvas = canvas.resize((int(w*scale), int(h*scale)), Image.LANCZOS)

        os.makedirs(os.path.abspath(out_dir), exist_ok=True)
        out_path = os.path.join(out_dir, filename)
        canvas.save(out_path, format="PNG", optimize=True)
        return out_path





    def graph_comparison(self, resultados: List[Dict]) -> Tuple[go.Figure, go.Figure]:
        assert len(resultados) == 3, "Se requieren exactamente 3 jugadores para la comparación"
        metricas = list(resultados[0].get('metricas_clave', {}).keys())
        datos_percentil, datos_per90 = {}, {}
        for r in resultados:
            nombre = r.get('nombre', 'Jugador')
            detalle = r.get('detalle', {}) or {}
            percentiles, percentiles90 = [], []
            for m in metricas:
                raw = (detalle.get(m, {}) or {}).get('raw', {}) or {}
                percentiles.append(self._safe_float(raw.get('percentile')))
                percentiles90.append(self._safe_float(raw.get('percentile_per90')))
            datos_percentil[nombre] = percentiles
            datos_per90[nombre] = percentiles90
        fig1 = self._crear_radar_plotly(datos_percentil, metricas, "Comparativa percentiles (métricas clave)")
        fig2 = self._crear_radar_plotly(datos_per90, metricas, "Comparativa percentiles por 90' (métricas clave)")
        return fig1, fig2

    # ---------------- NUEVO: PIZZAS DE PERFIL ----------------
    def _build_single_pizza(self, r: Dict[str, Any]):
        if not _MPL_AVAIL:
            raise RuntimeError("mplsoccer/Pillow no disponibles: omito pizzas de perfil.")

        if not isinstance(r, dict):
            raise TypeError(f"[Agente4] Resultado no es dict: {type(r)} -> {r}")

        nombre = r.get("nombre", "Jugador")
        main_pos = _norm_pos(r.get("main_position", ""))

        # Acepta 'estadisticas' o 'estadísticas'; y maneja str (JSON o dict-like)
        raw_est = r.get("estadisticas", None)
        if raw_est is None:
            raw_est = r.get("estadísticas", {})
        est = raw_est
        if isinstance(raw_est, str):
            parsed = None
            # 1) JSON estricto
            try:
                parsed = json.loads(raw_est)
            except Exception:
                pass
            # 2) dict-like con comillas simples (de Polars/pretty)
            if parsed is None:
                try:
                    parsed = ast.literal_eval(raw_est)
                except Exception:
                    parsed = {}
            est = parsed
        if not isinstance(est, dict):
            logger.warning(f"[Agente4] Estadisticas no-dict para {nombre}: tipo={type(raw_est)}. Uso est={{}}")
            est = {}

        # Minutes / Rating
        minutes_val = (est.get("Minutes", {}) or {}).get("value")
        rating_val  = (est.get("Rating", {}) or {}).get("value")
        minutes_num = _to_float(minutes_val)
        use_per90 = minutes_val is not None and minutes_num < self.per90_minutes_threshold

        is_gk = "goalkeeper" in main_pos

        if is_gk:
            blocks = [("Goalkeeping", GOALKEEPING_STATS), ("Distribution", DISTRIBUTION_STATS)]
            block_colors = BLOCK_COLORS_GK
        else:
            possession_extra = "Touches in opposition box" if main_pos in OFFENSIVE_POS else "Touches"
            possession_stats = POSSESSION_BASE + [possession_extra]

            if main_pos in OFFENSIVE_POS:
                defending_extra = DEFENDING_OF
            elif main_pos in DEF_MID_CB_POS:
                defending_extra = DEFENDING_DM_CB
            elif main_pos in CM_FB_POS:
                defending_extra = DEFENDING_CM_FB
            else:
                defending_extra = DEFENDING_OF

            defending_stats = DEFENDING_COMMON + defending_extra
            blocks = [
                ("Shooting", SHOOTING_STATS),
                ("Passing",  PASSING_STATS),
                ("Possession", possession_stats),
                ("Defending", defending_stats),
            ]
            block_colors = BLOCK_COLORS_FIELD

        # Debug de cobertura de métricas
        try:
            for bname, stats in blocks:
                faltan = [s for s in stats if s not in est]
                if len(faltan) == len(stats):
                    logger.warning(f"[Agente4] {nombre} · bloque '{bname}': 0/{len(stats)} métricas presentes (todas faltan).")
                elif faltan:
                    logger.debug(f"[Agente4] {nombre} · bloque '{bname}': faltan {len(faltan)} -> {faltan}")
        except Exception:
            pass

        params, values, slice_colors, value_text_colors = [], [], [], []
        for block_name, stats in blocks:
            for stat in stats:
                params.append(_short_label(stat))
                rec = est.get(stat, {})
                if not isinstance(rec, dict):
                    rec = {}
                values.append(_pick_percentile(rec, use_per90))
                slice_colors.append(block_colors[block_name])
                value_text_colors.append("#F2F2F2")

        # --- Figura (mejora legibilidad) ---
        baker = PyPizza(
            params=params,
            background_color="#222222",
            straight_line_color="#000000",
            straight_line_lw=1,
            last_circle_color="#000000",
            last_circle_lw=1,
            other_circle_lw=0,
            inner_circle_size=20
        )

        fig, ax = baker.make_pizza(
            values,
            figsize=(8.8, 9.4),  # antes (8, 8.5)
            color_blank_space="same",
            slice_colors=slice_colors,
            value_colors=value_text_colors,
            value_bck_colors=slice_colors,
            blank_alpha=0.4,
            kwargs_slices=dict(edgecolor="#000000", zorder=2, linewidth=1),
            kwargs_params=dict(color="#F2F2F2", fontsize=11,
                            fontproperties=getattr(self, "font_bold", None).prop if getattr(self, "font_bold", None) else None,
                            va="center"),
            kwargs_values=dict(color="#F2F2F2", fontsize=12,
                            fontproperties=getattr(self, "font_normal", None).prop if getattr(self, "font_normal", None) else None,
                            zorder=3,
                            bbox=dict(edgecolor="#000000", facecolor="cornflowerblue",
                                        boxstyle="round,pad=0.2", lw=1))
        )

        # === TÍTULO (1 punto menos y más separado) ===
        TITLE_SIZE = 33  # antes ~34
        TITLE_Y = 0.976  # un poco más arriba para despegar de la leyenda
        fig.text(
            0.515, TITLE_Y, nombre, size=TITLE_SIZE, ha="center",
            fontproperties=getattr(self, "font_title", None).prop if getattr(self, "font_title", None) else None,
            color="#F2F2F2"
        )

        # === LEYENDA DE BLOQUES (centrada y expandida a todo el ancho) ===
        # Distribuimos los items equiespaciados entre 0.12 y 0.88 del ancho.
        legend_items = [bname for bname, _ in blocks]
        n_items = len(legend_items)

        LEGEND_Y = 0.932         # un pelín más alta para despegar de la info
        X_START, X_END = 0.12, 0.88
        xs = []
        if n_items == 1:
            xs = [0.5]
        elif n_items == 2:
            xs = [0.40, 0.60]
        else:
            step = (X_END - X_START) / (n_items - 1)
            xs = [X_START + i * step for i in range(n_items)]

        box_w, box_h = 0.030, 0.022
        LABEL_OFFSET = 0.010
        LEGEND_FONTSIZE = 16

        for x, bname in zip(xs, legend_items):
            # cajita de color
            fig.patches.extend([
                plt.Rectangle((x - box_w/2, LEGEND_Y), box_w, box_h, fill=True,
                            color=block_colors[bname],
                            transform=fig.transFigure, figure=fig)
            ])
            # texto de la leyenda
            fig.text(x + box_w/2 + LABEL_OFFSET, LEGEND_Y + 0.002, bname, size=LEGEND_FONTSIZE,
                    fontproperties=getattr(self, "font_bold", None).prop if getattr(self, "font_bold", None) else None,
                    color="#F2F2F2", ha="left", va="bottom")

        # === INFO LINE: Rating · Minutes · Mode (más separada del gráfico) ===
        mode_text = "Perc90" if use_per90 else "Perc total"
        rating_str  = f"Rating: {rating_val}"   if rating_val  is not None else None
        minutes_str = f"Minutes: {minutes_val}" if minutes_val is not None else None
        parts = [p for p in (rating_str, minutes_str, f"Mode: {mode_text}") if p]
        info_line = " · ".join(parts)

        INFO_Y = 0.905   # antes ~0.905: bajamos para que no se pegue al anillo/etiquetas
        if info_line:
            fig.text(0.515, INFO_Y, info_line, size=12, ha="center",
                    fontproperties=getattr(self, "font_normal", None).prop if getattr(self, "font_normal", None) else None,
                    color="#CFCFCF")



        return fig



    def build_pizza_collage(
        self,
        resultados: Any,
        out_dir: str,
        filename_collage: str = "profiles_comparison.png",
        save_individual: bool = True,
        layout: str = "column",
        dpi: int = 300
                    ) -> Tuple[str, List[str]]:

        if not _MPL_AVAIL:
            raise RuntimeError("mplsoccer/Pillow no disponibles: omito pizzas de perfil.")

        cand = resultados
        if isinstance(cand, tuple) and len(cand) > 0:
            logger.warning("[Agente4] resultados llegó como tuple; uso el primer elemento.")
            cand = cand[0]
        if isinstance(cand, dict):
            logger.warning("[Agente4] resultados llegó como dict; uso values().")
            cand = list(cand.values())
        if not isinstance(cand, list):
            raise TypeError(f"'resultados' no es lista: {type(cand)}")

        cand = cand[:3]
        if len(cand) != 3:
            raise AssertionError(f"Se requieren 3 jugadores/porteros; llegaron: {len(cand)}")

        print(f"[Agente4] build_pizza_collage start · n={len(cand)} · layout={layout}")

        from PIL import Image
        out = os.path.abspath(out_dir)
        os.makedirs(out, exist_ok=True)

        # --- RENDER SIEMPRE A BYTES (robusto en headless) ---

        figs, paths, imgs = [], [], []
        for r in cand:
            fig = self._build_single_pizza(r)

            # guarda individual si se pidió
            if save_individual:
                safe_name = (r.get('nombre','player') or 'player').replace(" ", "_")
                fp = os.path.join(out, f"{safe_name}_profile.png")
                fig.savefig(fp, dpi=dpi, bbox_inches="tight")
                paths.append(fp)

            # PNG en memoria -> PIL
            buf = BytesIO()
            fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
            buf.seek(0)
            imgs.append(Image.open(buf).convert("RGB"))
            plt.close(fig)


        if layout == "row":
            min_h = min(im.height for im in imgs)
            resized = [im.resize((int(im.width * (min_h / im.height)), min_h), Image.LANCZOS) for im in imgs]
            total_w = sum(im.width for im in resized)
            collage = Image.new('RGB', (total_w, min_h), (34, 34, 34))
            x = 0
            for im in resized:
                collage.paste(im, (x, 0)); x += im.width
        else:
            max_w = max(im.width for im in imgs)
            resized = [im.resize((max_w, int(im.height * (max_w / im.width))), Image.LANCZOS) for im in imgs]
            total_h = sum(im.height for im in resized)
            collage = Image.new('RGB', (max_w, total_h), (34, 34, 34))
            y = 0
            for im in resized:
                collage.paste(im, (0, y)); y += im.height

        # --- NUEVO: clamp duro para Telegram (sendPhoto) ---
        MAX_SIDE = 3840  # margen seguro para Telegram
        w, h = collage.size
        if max(w, h) > MAX_SIDE:
            scale = MAX_SIDE / max(w, h)
            new_size = (int(w * scale), int(h * scale))
            collage = collage.resize(new_size, Image.LANCZOS)
            print(f"[Agente4] collage redimensionado a: {new_size}")


        collage_fp = os.path.join(out, filename_collage.replace(".png", ".jpg"))
        collage = collage.convert("RGB")  # por si hubiese alpha
        collage.save(collage_fp, format="JPEG", quality=90, optimize=True)
        print(f"[Agente4] collage guardado en: {collage_fp}")
        return collage_fp, paths

