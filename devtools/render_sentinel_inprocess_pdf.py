#!/usr/bin/env python3
"""Generate docs/diagrams/sentinel_inprocess_architecture.pdf (in-process packages & flows)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


def _box(ax, x: float, y: float, w: float, h: float, text: str, *, fc: str, ec: str, fs: int = 8) -> None:
    p = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.06",
        linewidth=1.0,
        edgecolor=ec,
        facecolor=fc,
    )
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs)


def _arrow(ax, x1: float, y1: float, x2: float, y2: float, *, style: str = "-|>") -> None:
    a = FancyArrowPatch(
        (x1, y1),
        (x2, y2),
        arrowstyle=style,
        mutation_scale=10,
        linewidth=0.9,
        color="#37474F",
    )
    ax.add_patch(a)


def _page1(ax) -> None:
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.text(7, 9.5, "Sentinel — in-process architecture (1/2)", ha="center", fontsize=12, fontweight="bold")
    ax.text(7, 9.05, "Entry, middleware, API, core services", ha="center", fontsize=9, color="#546E7A")

    ax.text(0.4, 8.35, "server.app", fontsize=9, fontweight="bold", color="#1565C0")
    _box(ax, 0.4, 7.55, 4.2, 0.65, "main.py\nFastAPI + StaticFiles /commissioning", fc="#E3F2FD", ec="#1565C0", fs=8)

    ax.text(5.2, 8.35, "server.middleware", fontsize=9, fontweight="bold", color="#6A1B9A")
    _box(ax, 5.2, 7.55, 3.6, 0.65, "CommissioningAuthMiddleware", fc="#F3E5F5", ec="#6A1B9A", fs=8)
    _box(ax, 9.2, 7.55, 4.4, 0.65, "TraceIdMiddleware", fc="#F3E5F5", ec="#6A1B9A", fs=8)

    ax.text(0.4, 7.05, "server.api", fontsize=9, fontweight="bold", color="#2E7D32")
    _box(
        ax,
        0.4,
        4.85,
        13.2,
        2.0,
        "commissioning.py  —  clients, projects, uploads, tech-links, rollups, fails, …\n"
        "commissioning_project_ws.py  —  commissioning WebSocket\n"
        "commissioning_snapshots.py  —  snapshot payloads\n"
        "testing.py  —  /testing HTML, POST /results, testing WS\n"
        "events.py  —  router prefix\n"
        "schemas.py, errors.py  —  bodies + HTTP errors",
        fc="#E8F5E9",
        ec="#2E7D32",
        fs=7,
    )

    ax.text(0.4, 4.35, "server.services", fontsize=9, fontweight="bold", color="#E65100")
    _box(ax, 0.4, 2.95, 4.1, 1.25, "repositories.py\nPostgresRepository | InMemoryRepository", fc="#FFF3E0", ec="#E65100", fs=7)
    _box(ax, 4.8, 2.95, 3.0, 1.25, "ws_broker.py\nProjectEventBroker, seq, replay", fc="#FFF3E0", ec="#E65100", fs=7)
    _box(ax, 8.2, 2.95, 2.6, 1.25, "progress.py\ncommissioning_progress", fc="#FFF3E0", ec="#E65100", fs=7)
    _box(ax, 11.0, 2.95, 2.6, 1.25, "commissioning_rollups.py", fc="#FFF3E0", ec="#E65100", fs=7)
    _box(ax, 0.4, 1.35, 6.2, 1.25, "pipeline.py\nupload → extract → generate (paths, subprocess)", fc="#FFF3E0", ec="#E65100", fs=7)

    # Vertical flow hints
    _arrow(ax, 2.5, 7.55, 2.5, 6.85)
    _arrow(ax, 7.0, 7.55, 5.5, 6.85)
    _arrow(ax, 11.4, 7.55, 9.0, 6.85)
    _arrow(ax, 7.0, 4.85, 2.5, 4.2)
    _arrow(ax, 2.5, 2.95, 2.5, 2.6)
    _arrow(ax, 6.3, 2.95, 6.3, 2.6)


def _page2(ax) -> None:
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis("off")
    ax.text(7, 9.5, "Sentinel — in-process architecture (2/2)", ha="center", fontsize=12, fontweight="bold")
    ax.text(7, 9.05, "Persistence, generation, extraction, UI, contracts", ha="center", fontsize=9, color="#546E7A")

    ax.text(0.4, 8.35, "server.persistence", fontsize=9, fontweight="bold", color="#455A64")
    _box(ax, 0.4, 7.2, 4.2, 0.95, "db.py\nconnect, apply_migrations", fc="#ECEFF1", ec="#455A64", fs=8)
    _box(ax, 4.9, 7.2, 4.2, 0.95, "queries.py\nSQL helpers", fc="#ECEFF1", ec="#455A64", fs=8)
    _box(ax, 9.4, 7.2, 4.2, 0.95, "migrations/*.sql", fc="#ECEFF1", ec="#455A64", fs=8)

    ax.text(0.4, 6.55, "extraction + generation", fontsize=9, fontweight="bold", color="#006064")
    _box(ax, 0.4, 5.35, 3.0, 1.0, "extractor_core.py", fc="#E0F7FA", ec="#006064", fs=8)
    _box(ax, 3.7, 5.35, 3.4, 1.0, "extract_project_data.py", fc="#E0F7FA", ec="#006064", fs=8)
    _box(ax, 7.4, 5.35, 3.2, 1.0, "render_core.py\nHTML + embedded JS", fc="#E0F7FA", ec="#006064", fs=7)
    _box(ax, 10.8, 5.35, 2.8, 1.0, "generate_html.py", fc="#E0F7FA", ec="#006064", fs=8)

    ax.text(0.4, 4.85, "contracts", fontsize=9, fontweight="bold", color="#5D4037")
    _box(ax, 0.4, 3.85, 13.2, 0.85, "apex_project_structure_v4.json, app_ui_structure.json, …", fc="#EFEBE9", ec="#5D4037", fs=8)

    ax.text(0.4, 3.35, "ui / commissioning (static)", fontsize=9, fontweight="bold", color="#1565C0")
    _box(ax, 0.4, 1.85, 5.5, 1.35, "index.html + CSS\n(project_device_static_layout, …)", fc="#E3F2FD", ec="#1565C0", fs=7)
    _box(ax, 6.2, 1.85, 7.4, 1.35, "commissioning.js, commission_tab.js, diagnostics_tab.js", fc="#E3F2FD", ec="#1565C0", fs=7)

    ax.text(0.35, 0.95, "Key flows: commissioning + testing routers → Repository + ws_broker; snapshots → progress + rollups; pipeline → extraction → render_core → disk; main mounts /commissioning UI.", fontsize=7, color="#78909C", wrap=True)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    out = root / "docs" / "diagrams" / "sentinel_inprocess_architecture.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)

    with PdfPages(out) as pdf:
        fig1, ax1 = plt.subplots(figsize=(8.5, 11))
        _page1(ax1)
        pdf.savefig(fig1)
        plt.close(fig1)

        fig2, ax2 = plt.subplots(figsize=(8.5, 11))
        _page2(ax2)
        pdf.savefig(fig2)
        plt.close(fig2)

    print(out)


if __name__ == "__main__":
    main()
