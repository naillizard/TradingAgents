"""
Simple mode layout for the Hermes trading dashboard.

Export: simple_layout(data: dict) -> dash.html.Div

`data` keys match query function names:
  equity_curve, open_positions, recent_trades, stats,
  analyst_performance, trades_full, skill_library
"""

import pandas as pd
import dash
from dash import html, dcc
import plotly.graph_objects as go

# ── Design tokens ──────────────────────────────────────────────────────────────
BG = "#0f0f0f"
CARD_BG = "#1a1a1a"
BORDER = "#2a2a2a"
TEXT = "#e0e0e0"
MUTED = "#888888"
GREEN = "#22c55e"
RED = "#ef4444"
BLUE = "#3b82f6"
AMBER = "#f59e0b"

CARD = {
    "background": CARD_BG,
    "border": f"1px solid {BORDER}",
    "borderRadius": "8px",
    "padding": "20px",
}
WRAP = {
    "maxWidth": "1200px",
    "margin": "0 auto",
    "padding": "16px",
    "background": BG,
    "minHeight": "100vh",
    "fontFamily": "'Inter', 'Segoe UI', system-ui, sans-serif",
    "color": TEXT,
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pnl_color(value: float) -> str:
    return GREEN if value >= 0 else RED


def _fmt_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.1%}"


def _fmt_dollar(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}${value:,.0f}"


# ── Section 1: Stats row ───────────────────────────────────────────────────────

def _stat_card(label: str, value: str, color: str = TEXT) -> html.Div:
    return html.Div([
        html.P(label, style={"margin": "0 0 6px", "color": MUTED, "fontSize": "12px",
                              "textTransform": "uppercase", "letterSpacing": "0.08em"}),
        html.P(value, style={"margin": 0, "fontSize": "28px", "fontWeight": "700",
                              "color": color, "lineHeight": "1"}),
    ], style={**CARD, "flex": "1", "minWidth": "160px"})


def _stats_row(stats: dict) -> html.Div:
    win_rate = stats.get("win_rate", 0.0)
    total = stats.get("total_trades", 0)
    rpnl = stats.get("realized_pnl", 0.0)
    heat = stats.get("account_heat", 0.0)

    heat_color = GREEN if heat < 0.06 else (AMBER if heat < 0.10 else RED)

    return html.Div(
        [
            _stat_card("Win Rate", f"{win_rate:.0%}", GREEN if win_rate >= 0.5 else RED),
            _stat_card("Total Trades", str(total)),
            _stat_card("Realised P&L", _fmt_dollar(rpnl), _pnl_color(rpnl)),
            _stat_card("Account Heat", f"{heat:.1%}", heat_color),
        ],
        style={"display": "flex", "gap": "12px", "flexWrap": "wrap", "marginBottom": "16px"},
    )


# ── Section 2: Equity curve ────────────────────────────────────────────────────

def _equity_chart(df) -> html.Div:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No data", x=0.5, y=0.5, showarrow=False,
                           font={"color": MUTED, "size": 14})
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["account_equity"],
            mode="lines",
            line={"color": BLUE, "width": 2},
            fill="tozeroy",
            fillcolor="rgba(59,130,246,0.08)",
            name="Equity",
            hovertemplate="%{x|%d %b %Y}<br>$%{y:,.0f}<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["realized_pnl"].cumsum(),
            mode="lines",
            line={"color": GREEN, "width": 1, "dash": "dot"},
            name="Realised P&L",
            hovertemplate="%{x|%d %b %Y}<br>$%{y:,.0f}<extra></extra>",
        ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=CARD_BG,
        plot_bgcolor=CARD_BG,
        margin={"l": 50, "r": 20, "t": 20, "b": 40},
        height=260,
        legend={"orientation": "h", "y": 1.08, "font": {"color": MUTED, "size": 11}},
        xaxis={"showgrid": False, "tickfont": {"color": MUTED, "size": 11}},
        yaxis={"gridcolor": BORDER, "tickfont": {"color": MUTED, "size": 11},
               "tickprefix": "$"},
    )

    return html.Div(
        [
            html.P("Equity Curve", style={"margin": "0 0 12px", "fontWeight": "600",
                                           "color": TEXT, "fontSize": "14px"}),
            dcc.Graph(figure=fig, config={"displayModeBar": False},
                      style={"borderRadius": "6px", "overflow": "hidden"}),
        ],
        style={**CARD, "marginBottom": "16px"},
    )


# ── Section 3: Open positions ──────────────────────────────────────────────────

def _position_card(row) -> html.Div:
    direction = str(row.get("signal", "—")).upper()
    dir_color = GREEN if direction in ("BUY", "LONG") else (RED if direction in ("SELL", "SHORT") else MUTED)
    entry = row.get("entry_price")
    stop = row.get("stop_price")
    shares = row.get("shares")
    risk = abs((entry - stop) * shares) if (entry and stop and shares) else None
    date_opened = row.get("date_open")
    date_str = date_opened.strftime("%d %b %Y") if hasattr(date_opened, "strftime") else str(date_opened or "—")

    return html.Div(
        [
            html.Div(
                [
                    html.Span(str(row.get("ticker", "—")),
                              style={"fontSize": "18px", "fontWeight": "700", "color": TEXT}),
                    html.Span(direction,
                              style={"marginLeft": "10px", "color": dir_color,
                                     "fontSize": "12px", "fontWeight": "600",
                                     "background": f"{dir_color}22", "padding": "2px 8px",
                                     "borderRadius": "4px"}),
                ],
                style={"marginBottom": "10px"},
            ),
            html.Div(
                [
                    _mini_stat("Entry", f"${entry:,.2f}" if entry else "—"),
                    _mini_stat("Stop", f"${stop:,.2f}" if stop else "—"),
                    _mini_stat("Shares", f"{shares:,.0f}" if shares else "—"),
                    _mini_stat("Risk $", f"${risk:,.0f}" if risk else "—"),
                    _mini_stat("Opened", date_str),
                    _mini_stat("Regime", str(row.get("regime") or "—")),
                ],
                style={"display": "flex", "gap": "16px", "flexWrap": "wrap"},
            ),
        ],
        style={**CARD, "marginBottom": "10px"},
    )


def _mini_stat(label: str, value: str) -> html.Div:
    return html.Div([
        html.Span(label, style={"fontSize": "10px", "color": MUTED, "display": "block",
                                "textTransform": "uppercase", "letterSpacing": "0.06em"}),
        html.Span(value, style={"fontSize": "14px", "fontWeight": "600", "color": TEXT}),
    ])


def _open_positions_section(df) -> html.Div:
    body = (html.P("No open positions.", style={"color": MUTED, "margin": 0})
            if df.empty else html.Div([_position_card(row) for _, row in df.iterrows()]))
    return html.Div([
        html.P(f"Open Positions ({len(df)})",
               style={"margin": "0 0 12px", "fontWeight": "600", "color": TEXT, "fontSize": "14px"}),
        body,
    ], style={"marginBottom": "16px"})


# ── Section 4: Recent trades table ────────────────────────────────────────────

def _trade_row(row) -> html.Tr:
    outcome = str(row.get("outcome", "")).lower()
    if outcome == "win":
        bg = "#16a34a22"
        badge_color = GREEN
    elif outcome == "loss":
        bg = "#dc262622"
        badge_color = RED
    else:
        bg = "#2a2a2a"
        badge_color = MUTED

    pnl_d = row.get("pnl_dollars")
    pnl_p = row.get("pnl_pct")
    entry = row.get("entry_price")
    date_c = row.get("date_close")
    date_str = date_c.strftime("%d %b %Y") if hasattr(date_c, "strftime") else str(date_c or "—")

    td_style = {"padding": "10px 12px", "fontSize": "13px", "color": TEXT,
                "borderBottom": f"1px solid {BORDER}"}

    return html.Tr(
        [
            html.Td(str(row.get("ticker", "—")),
                    style={**td_style, "fontWeight": "700"}),
            html.Td(str(row.get("signal", "—")).upper(), style=td_style),
            html.Td(f"${entry:,.2f}" if entry else "—", style=td_style),
            html.Td(_fmt_dollar(pnl_d) if pnl_d is not None else "—",
                    style={**td_style, "color": _pnl_color(pnl_d) if pnl_d else MUTED}),
            html.Td(_fmt_pct(pnl_p) if pnl_p is not None else "—",
                    style={**td_style, "color": _pnl_color(pnl_p) if pnl_p else MUTED}),
            html.Td(
                html.Span(outcome.capitalize(),
                           style={"color": badge_color, "fontWeight": "600",
                                  "fontSize": "12px"}),
                style=td_style,
            ),
            html.Td(date_str, style={**td_style, "color": MUTED}),
        ],
        style={"background": bg},
    )


def _recent_trades_section(df) -> html.Div:
    hs = {"padding": "10px 12px", "fontSize": "11px", "color": MUTED, "fontWeight": "600",
          "textTransform": "uppercase", "letterSpacing": "0.07em",
          "borderBottom": f"1px solid {BORDER}"}
    headers = ["Ticker", "Signal", "Entry", "P&L $", "P&L %", "Outcome", "Closed"]
    body_rows = (
        [html.Tr(html.Td("No closed trades yet.", colSpan=7,
                          style={"padding": "20px 12px", "color": MUTED, "textAlign": "center"}))]
        if df.empty else [_trade_row(row) for _, row in df.iterrows()]
    )
    table = html.Table([
        html.Thead(html.Tr([html.Th(h, style=hs) for h in headers])),
        html.Tbody(body_rows),
    ], style={"width": "100%", "borderCollapse": "collapse"})
    return html.Div([
        html.P("Recent Trades", style={"margin": "0 0 12px", "fontWeight": "600",
                                        "color": TEXT, "fontSize": "14px"}),
        html.Div(table, style={"overflowX": "auto"}),
    ], style={**CARD, "marginBottom": "16px"})


# ── Public export ──────────────────────────────────────────────────────────────

def simple_layout(data: dict) -> dash.html.Div:
    """
    Build the simple mode layout from pre-fetched data.

    Expected keys in `data`:
      stats, equity_curve, open_positions, recent_trades
    """
    _e = pd.DataFrame()
    stats = data.get("stats") or {}
    equity_df = data.get("equity_curve") if data.get("equity_curve") is not None else _e
    positions_df = data.get("open_positions") if data.get("open_positions") is not None else _e
    trades_df = data.get("recent_trades") if data.get("recent_trades") is not None else _e

    return html.Div([
        html.H1("Hermes Dashboard",
                style={"margin": "0 0 20px", "fontSize": "22px", "fontWeight": "700", "color": TEXT}),
        _stats_row(stats),
        _equity_chart(equity_df),
        _open_positions_section(positions_df),
        _recent_trades_section(trades_df),
    ], style=WRAP)
