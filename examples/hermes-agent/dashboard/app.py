import os
import sys
from datetime import datetime

import dash
from dash import dcc, html, Input, Output, State

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, "/opt/dashboard")

from simple import simple_layout
from advanced import advanced_layout

try:
    import queries as _q
    _QUERIES_OK = True
except ImportError:
    _QUERIES_OK = False

import pandas as pd

_PORT = int(os.environ.get("DASHBOARD_PORT", 8050))
_BG, _CARD_BG, _BORDER, _TEXT, _MUTED = "#0f0f0f", "#1a1a1a", "#2a2a2a", "#e0e0e0", "#888"

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "TradingAgents"

def _dot(color="#4ade80"):
    return {
        "display": "inline-block", "width": "8px", "height": "8px",
        "borderRadius": "50%", "backgroundColor": color,
        "marginRight": "10px", "verticalAlign": "middle",
    }

app.layout = html.Div([
    dcc.Store(id="mode-store", storage_type="session", data="simple"),
    dcc.Interval(id="refresh-interval", interval=60_000, n_intervals=0),

    # Header
    html.Div([
        html.Div([
            html.Span(id="health-dot", style=_dot()),
            html.Span("TradingAgents", style={"color": _TEXT, "fontSize": "16px", "fontWeight": "700"}),
        ], style={"display": "flex", "alignItems": "center"}),
        html.Button(
            id="toggle-btn", children="Switch to Advanced",
            style={
                "background": "none", "border": f"1px solid {_BORDER}", "color": _TEXT,
                "padding": "6px 16px", "borderRadius": "6px", "cursor": "pointer",
                "fontSize": "13px", "fontWeight": "500",
            },
        ),
    ], style={
        "display": "flex", "alignItems": "center", "justifyContent": "space-between",
        "padding": "12px 24px", "borderBottom": f"1px solid {_BORDER}",
        "backgroundColor": _CARD_BG, "position": "sticky", "top": 0, "zIndex": 100,
    }),

    # Main content
    html.Div(id="main-content", style={"padding": "24px", "minHeight": "calc(100vh - 120px)"}),

    # Footer
    html.Div([
        html.Span("Auto-refreshing every 60s", style={"color": _MUTED, "fontSize": "11px"}),
        html.Span(" | ", style={"color": _BORDER, "margin": "0 6px"}),
        html.Span(id="last-updated", style={"color": _MUTED, "fontSize": "11px"}),
    ], style={
        "padding": "10px 24px", "borderTop": f"1px solid {_BORDER}",
        "backgroundColor": _CARD_BG, "display": "flex", "alignItems": "center",
    }),
], style={"backgroundColor": _BG, "fontFamily": "'Inter', system-ui, sans-serif", "minHeight": "100vh"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_data() -> tuple[dict, bool]:
    if not _QUERIES_OK:
        return {}, False
    try:
        return {
            "equity_curve": _q.get_equity_curve(days=90),
            "open_positions": _q.get_open_positions(),
            "recent_trades": _q.get_recent_trades(limit=10),
            "stats": _q.get_stats(),
            "analyst_performance": _q.get_analyst_performance(),
            "trades_full": _q.get_trades_full(),
            "skill_library": _q.get_skill_library(),
        }, True
    except Exception:
        return {}, False


def _empty_data() -> dict:
    return {
        "equity_curve": pd.DataFrame(), "open_positions": pd.DataFrame(),
        "recent_trades": pd.DataFrame(), "stats": {},
        "analyst_performance": pd.DataFrame(), "trades_full": pd.DataFrame(),
        "skill_library": [],
    }


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@app.callback(
    Output("mode-store", "data"),
    Output("toggle-btn", "children"),
    Input("toggle-btn", "n_clicks"),
    State("mode-store", "data"),
    prevent_initial_call=True,
)
def toggle_mode(n_clicks, current):
    if current == "simple":
        return "advanced", "Switch to Simple"
    return "simple", "Switch to Advanced"


@app.callback(
    Output("main-content", "children"),
    Output("last-updated", "children"),
    Output("health-dot", "style"),
    Input("refresh-interval", "n_intervals"),
    Input("mode-store", "data"),
)
def update_dashboard(n_intervals, mode):
    data, healthy = _fetch_data()
    if not healthy:
        data = _empty_data()

    timestamp = f"Last updated: {datetime.now().strftime('%H:%M:%S')}"
    dot_style = _dot("#4ade80" if healthy else "#ef4444")
    content = advanced_layout(data) if mode == "advanced" else simple_layout(data)
    return content, timestamp, dot_style


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=_PORT)
