---
applyTo: "docs/thesis/**"
---

# Thesis Writing Instructions — Arbocensus

Document: `docs/thesis/main.tex` — Trabajo de Titulación de Tipo Producto,
Ingeniería Civil en Ciencias de la Computación, Universidad de Los Andes.

---

## Language and style

- Spanish, **third person**, academic register.
  ✓ "se desarrolló", "el sistema implementa", "se observa que"
  ✗ "desarrollé", "implementamos", "básicamente"
- Formal only. No colloquial phrases, no filler, no hedging.
- Past tense for work done; present for established facts and system descriptions.

---

## Citations

- Harvard style via natbib.
- `\citep{key}` → (Autor, año) — parenthetical.
- `\citet{key}` → Autor (año) — inline.
- All keys must exist in `bibliography.bib`. Never invent keys.

---

## LaTeX safety

- Escape in prose: `%` → `\%`, `$` → `\$`, `_` → `\_`, `&` → `\&`.
- Inline code or identifiers: `\texttt{RouteStop}`, `\texttt{PointField}`.
- Foreign / technical terms: `\textit{Open mTSP}`, `\textit{dummy depot}`.
- Math inline: `$T_{\min}$`, `$n \times n$`. Display: `\begin{equation}...\end{equation}`.

---

## Do NOT invent data

Placeholders like `[COMPLETAR CON DATOS REALES]` and `% TODO:` are intentional.
Never fill them with fabricated metrics, times, or percentages.

---

## Formatting (Universidad de Los Andes template)

| Element       | Style                                  |
|---------------|----------------------------------------|
| Chapter title | UPPERCASE, bold, centered — `\chapter{}` |
| Section title | UPPERCASE, no bold — `\section{}`      |
| Subsection    | Sentence case, no bold — `\subsection{}` |
| Body          | Times New Roman 12pt, 1.5 spacing, no indent |
| Margins       | 2.5 cm top/bottom · 3 cm left/right   |
| Enumeration   | `itemize` / `enumerate`; nested → lowercase Roman (i, ii, iii) |

---

## Figures and tables

```latex
% Figure
\begin{figure}[H]
  \centering
  \includegraphics[width=0.9\textwidth]{img/name.png}
  \caption{Descripción de la ilustración.}
  \label{fig:name}
\end{figure}
% Reference: Figura~\ref{fig:name}

% Table
\begin{table}[H]
  \centering
  \caption{Título de la tabla.}
  \label{tab:name}
  \begin{tabularx}{\textwidth}{lXX}
    \toprule ... \midrule ... \bottomrule
  \end{tabularx}
\end{table}
% Reference: Tabla~\ref{tab:name}
```

---

## Key technical facts — never contradict in prose

| Fact | Value |
|------|-------|
| T\_max constraint | **Hard** (AddDimension capacity) |
| T\_min constraint | **Soft** penalty coeff 10,000 (SetCumulVarSoftLowerBound) |
| Dummy depot | Node index 0; real nodes 1..n; extract: `IndexToNode(i) - 1` |
| k (route count) | Determined **automatically** by OR-Tools — never input manually |
| Walking distances | Real OSM data via OSRM — NOT Google Maps, NOT Euclidean |
| DistanceMatrix cache key | SHA-256 of sorted active tree IDs |
| Visit order source | `RouteStop.sequence` — no redundant `tree_sequence` in Route |
| Default time limits | T\_min = 7200 s (2 h), T\_max = 10800 s (3 h) — configurable |
| Fixed vehicle cost | 100,000 s per active vehicle |
| Solver time limit | 180 s default |
| OSRM coordinate order | lon,lat in URL — NOT lat,lon |

---

## Chapter structure (adapted template, no Modelo de Negocios)

```
Frontmatter (roman): Agradecimientos · Índice General · Índice Tablas · Índice Ilustraciones · Resumen
1. PROBLEMÁTICA
   1.1 Descripción de la Problemática
   1.2 Estado Actual del Problema
   1.3 Solución Planteada
2. DISEÑO DEL PRODUCTO
   2.1 Arquitectura del Sistema
   2.2 Modelo de Datos
   2.3 Motor de Optimización
       2.3.1 Formulación del Problema
       2.3.2 Construcción de la Matriz de Costos
       2.3.3 Estimación del Número de Rutas
       2.3.4 Solver VRP con OR-Tools
   2.4 API REST
   2.5 Interfaz de Usuario
3. RESULTADOS OBTENIDOS Y POSIBLES MEJORAS
   3.1 Resultados Obtenidos
       3.1.1 Métricas de Calidad de Rutas
       3.1.2 Comparación con Solución Greedy
   3.2 Posibles Mejoras
BIBLIOGRAFÍA
ANEXOS
  Anexo 1. Documentación de la API REST
  Anexo 2. Script de Demostración
```

---

## Compilation

```bash
# From docs/thesis/
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```
