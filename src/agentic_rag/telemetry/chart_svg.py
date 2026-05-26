"""共享 SVG 图表与仪表盘 HTML（Gradio gr.HTML 兼容：仅用内联 style，不用 class/style 块）。"""

from __future__ import annotations

FONT = "'Microsoft YaHei','PingFang SC','Segoe UI',sans-serif"
C_BG = "#0f1419"
C_CARD = "#1a2332"
C_TEXT = "#e6edf3"
C_MUTED = "#8b949e"
C_ACCENT = "#58a6ff"
C_GOOD = "#3fb950"
C_WARN = "#f0883e"
C_CRIT = "#f85149"
C_NEW = "#a371f7"
C_BORDER = "#30363d"

# 导出 HTML 文件仍可用完整 CSS
DASHBOARD_CSS = ""


def html_escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _tone_color(tone: str) -> str:
    return {
        "accent": C_ACCENT,
        "good": C_GOOD,
        "warn": C_WARN,
        "crit": C_CRIT,
        "new": C_NEW,
    }.get(tone, C_ACCENT)


def _row_bg(tone: str) -> str:
    return {
        "warn": "background:rgba(240,136,62,.12);",
        "crit": "background:rgba(248,81,73,.14);",
        "new": "background:rgba(163,113,247,.12);",
        "active": "background:rgba(88,166,255,.1);",
    }.get(tone, "")


def svg_horizontal_bars(
    title: str,
    labels: list[str],
    values: list[float],
    color: str,
    *,
    chart_w: int = 680,
    row_h: int = 22,
    highlight_indices: set[int] | None = None,
    active_index: int | None = None,
) -> str:
    if not labels:
        return ""
    hi = highlight_indices or set()
    max_v = max(values) or 1.0
    label_w = 52
    bar_x = label_w + 8
    bar_area = chart_w - bar_x - 40
    h = 32 + len(labels) * row_h
    svg_font = 'font-family="Microsoft YaHei, Segoe UI, sans-serif"'
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="{h}" '
        f'viewBox="0 0 {chart_w} {h}" role="img" style="max-width:{chart_w}px;display:block;">',
        f'<text x="8" y="18" fill="{C_ACCENT}" font-size="13" font-weight="600" {svg_font}>'
        f"{html_escape(title)}</text>",
    ]
    for i, (lab, val) in enumerate(zip(labels, values, strict=False)):
        y = 28 + i * row_h
        bw = int(bar_area * (val / max_v)) if val > 0 else 0
        fill = C_CRIT if i in hi and val == max_v and max_v > 0 else color
        if i == active_index:
            fill = C_ACCENT
        parts.append(
            f'<text x="8" y="{y + 13}" fill="{C_MUTED}" font-size="10" {svg_font}>'
            f"{html_escape(lab)}</text>"
        )
        parts.append(
            f'<rect x="{bar_x}" y="{y + 3}" width="{bw}" height="{row_h - 6}" '
            f'fill="{fill}" opacity="0.92" rx="2"/>'
        )
        val_text = f"{val:.1f}" if isinstance(val, float) and val != int(val) else str(int(val))
        parts.append(
            f'<text x="{bar_x + bw + 4}" y="{y + 13}" fill="{C_TEXT}" font-size="10" {svg_font}>'
            f"{html_escape(val_text)}</text>"
        )
        if i in hi:
            parts.append(
                f'<text x="{chart_w - 32}" y="{y + 13}" fill="{C_WARN}" font-size="9" {svg_font}>峰值</text>'
            )
    parts.append("</svg>")
    return "".join(parts)


def kpi_grid_html(items: list[tuple[str, str, str, str]]) -> str:
    cells = []
    for item in items:
        v, lbl = item[0], item[1]
        tone = item[2] if len(item) > 2 else "accent"
        extra = item[3] if len(item) > 3 else ""
        val_color = _tone_color(tone)
        border = f"border:1px solid {C_BORDER};"
        if tone == "crit":
            border = f"border:1px solid {C_CRIT};"
        elif tone == "warn":
            border = f"border:1px solid {C_WARN};"
        badge = ""
        sub = ""
        if extra in ("NEW", "进行中", "峰值", "实时"):
            badge = (
                f'<span style="position:absolute;top:4px;right:4px;font-size:10px;padding:1px 5px;'
                f"border-radius:4px;background:{C_NEW};color:#fff;font-weight:600;"
                f'font-family:{FONT};">{html_escape(extra)}</span>'
            )
        elif extra:
            sub = (
                f'<div style="font-size:11px;color:{C_MUTED};margin-top:2px;font-family:{FONT};">'
                f"{html_escape(extra)}</div>"
            )
        cells.append(
            f'<div style="position:relative;text-align:center;padding:8px 6px;background:#21262d;'
            f"border-radius:6px;{border}font-family:{FONT};\">{badge}"
            f'<div style="font-size:18px;font-weight:700;color:{val_color};line-height:1.2;">'
            f"{html_escape(v)}</div>"
            f'<div style="font-size:11px;color:{C_MUTED};margin-top:2px;">{html_escape(lbl)}</div>{sub}</div>'
        )
    return (
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));'
        f'gap:8px;margin-bottom:12px;">{"".join(cells)}</div>'
    )


def alerts_html(alerts: list[tuple[str, str, str]]) -> str:
    if not alerts:
        return ""
    colors = {
        "crit": (C_CRIT, "rgba(248,81,73,.12)"),
        "warn": (C_WARN, "rgba(240,136,62,.12)"),
        "good": (C_GOOD, "rgba(63,185,80,.1)"),
        "info": (C_ACCENT, "rgba(88,166,255,.08)"),
    }
    rows = []
    for lv, t, d in alerts:
        border_c, bg = colors.get(lv, (C_ACCENT, "rgba(88,166,255,.08)"))
        rows.append(
            f'<div style="padding:6px 10px;border-radius:6px;font-size:13px;border-left:3px solid {border_c};'
            f"background:{bg};color:{C_TEXT};font-family:{FONT};margin-bottom:4px;\">"
            f"<b style=\"color:{C_TEXT};\">{html_escape(t)}</b> — {html_escape(d)}</div>"
        )
    return f'<div style="margin-bottom:10px;">{"".join(rows)}</div>'


def static_charts_block(charts: list[str], *, subtitle: str = "") -> str:
    inner = "".join(f'<div style="margin-bottom:10px;">{c}</div>' for c in charts if c)
    sub = (
        f'<p style="color:{C_MUTED};font-size:13px;margin:0 0 8px;font-family:{FONT};">'
        f"{html_escape(subtitle)}</p>"
        if subtitle
        else ""
    )
    return (
        f'<div style="background:{C_CARD};border-radius:8px;padding:12px;margin-bottom:10px;'
        f"border:1px solid {C_BORDER};overflow-x:auto;font-family:{FONT};\">{sub}{inner}</div>"
    )


def dashboard_shell_open(*, title: str) -> str:
    return (
        f'<div style="font-family:{FONT};color:{C_TEXT};background:{C_BG};padding:12px 14px;'
        f'border-radius:8px;border:1px solid {C_BORDER};max-width:100%;overflow-x:auto;">'
        f'<h2 style="font-size:16px;color:{C_ACCENT};border-left:3px solid {C_ACCENT};'
        f'margin:0 0 8px;padding-left:8px;font-weight:600;">{html_escape(title)}</h2>'
    )


def dashboard_shell_close() -> str:
    return "</div>"


def live_line_html(text_html: str, *, in_progress: bool = False) -> str:
    pulse = (
        f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
        f"background:{C_WARN};margin-right:6px;vertical-align:middle;\"></span>"
        if in_progress
        else ""
    )
    return (
        f'<div style="font-size:13px;color:{C_MUTED};margin-bottom:10px;font-family:{FONT};">'
        f"{pulse}{text_html}</div>"
    )


def banner_html(text: str, *, kind: str = "new") -> str:
    border = C_NEW if kind == "new" else C_ACCENT
    bg = "rgba(163,113,247,.12)" if kind == "new" else "rgba(88,166,255,.1)"
    return (
        f'<div style="padding:8px 10px;border-radius:6px;margin-bottom:10px;font-size:14px;'
        f"border:1px solid {border};background:{bg};color:{C_TEXT};font-family:{FONT};\">"
        f"{html_escape(text)}</div>"
    )


def sub_text_html(text: str) -> str:
    return (
        f'<p style="color:{C_MUTED};font-size:13px;margin:0 0 8px;font-family:{FONT};">'
        f"{html_escape(text)}</p>"
    )


def metrics_table_html(headers: list[str], rows_html: str, *, title: str = "逐轮关键指标") -> str:
    ths = "".join(
        f'<th style="padding:6px 8px;text-align:left;color:{C_MUTED};font-weight:600;'
        f'border-bottom:1px solid {C_BORDER};font-size:13px;">{html_escape(h)}</th>'
        for h in headers
    )
    return (
        f'<div style="background:{C_CARD};border-radius:8px;padding:12px;margin-bottom:8px;'
        f'border:1px solid {C_BORDER};overflow-x:auto;font-family:{FONT};">'
        f'<div style="font-size:15px;color:{C_ACCENT};font-weight:600;margin-bottom:8px;">'
        f"{html_escape(title)}</div>"
        f'<table style="width:100%;border-collapse:collapse;font-size:13px;color:{C_TEXT};">'
        f"<thead><tr>{ths}</tr></thead><tbody>{rows_html}</tbody></table></div>"
    )


def table_row_html(cells: list[str], *, tone: str = "") -> str:
    bg = _row_bg(tone)
    tds = "".join(
        f'<td style="padding:6px 8px;border-bottom:1px solid {C_BORDER};color:{C_TEXT};{bg}">'
        f"{c}</td>"
        for c in cells
    )
    return f"<tr>{tds}</tr>"


def tag_html(label: str, *, kind: str = "new") -> str:
    styles = {
        "new": f"background:{C_NEW};color:#fff;",
        "live": f"background:{C_WARN};color:#111;",
        "peak": f"background:#30363d;color:{C_WARN};border:1px solid {C_WARN};",
    }
    st = styles.get(kind, styles["new"])
    return (
        f'<span style="display:inline-block;font-size:10px;padding:1px 6px;border-radius:4px;'
        f"margin-left:4px;font-weight:600;{st}font-family:{FONT};\">{html_escape(label)}</span>"
    )


def kv_grid_html(rows: list[tuple[str, str]], *, columns: int = 2) -> str:
    """键值对网格，用于轮次详情。"""
    if not rows:
        return ""
    cells = []
    for k, v in rows:
        cells.append(
            f'<div style="padding:6px 8px;background:#21262d;border-radius:4px;'
            f'border:1px solid {C_BORDER};min-width:0;">'
            f'<div style="font-size:11px;color:{C_MUTED};margin-bottom:2px;">{html_escape(k)}</div>'
            f'<div style="font-size:13px;color:{C_TEXT};word-break:break-word;">{html_escape(v)}</div></div>'
        )
    return (
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));'
        f'gap:6px;margin-bottom:8px;">{"".join(cells)}</div>'
    )


def detail_block_html(title: str, body_html: str) -> str:
    return (
        f'<div style="margin-bottom:10px;">'
        f'<div style="font-size:13px;color:{C_ACCENT};font-weight:600;margin-bottom:4px;">'
        f"{html_escape(title)}</div>"
        f'<div style="font-size:13px;color:{C_TEXT};line-height:1.5;word-break:break-word;">'
        f"{body_html}</div></div>"
    )


def tool_bars_html(tool_counts: dict[str, int]) -> str:
    if not tool_counts:
        return f'<span style="color:{C_MUTED};">无</span>'
    max_v = max(tool_counts.values()) or 1
    parts = []
    for name, cnt in sorted(tool_counts.items(), key=lambda x: -x[1]):
        bw = int(120 * cnt / max_v) if cnt else 0
        parts.append(
            f'<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:12px;">'
            f'<span style="width:120px;color:{C_MUTED};flex-shrink:0;">{html_escape(name)}</span>'
            f'<span style="display:inline-block;height:14px;width:{max(bw,4)}px;background:{C_ACCENT};'
            f'border-radius:2px;"></span>'
            f'<span style="color:{C_TEXT};">x{cnt}</span></div>'
        )
    return "".join(parts)


def turn_detail_panel_html(title: str, inner_html: str) -> str:
    return (
        f'<div style="background:{C_CARD};border-radius:8px;padding:12px;margin-top:10px;'
        f'border:1px solid {C_BORDER};font-family:{FONT};">'
        f'<div style="font-size:15px;color:{C_ACCENT};font-weight:600;margin-bottom:10px;'
        f'border-bottom:1px solid {C_BORDER};padding-bottom:6px;">{html_escape(title)}</div>'
        f"{inner_html}</div>"
    )
