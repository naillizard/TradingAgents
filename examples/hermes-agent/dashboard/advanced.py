import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import html, dcc

_DARK_BG = "#0f0f0f"
_CARD_BG = "#1a1a1a"
_BORDER = "#2a2a2a"
_TEXT = "#e0e0e0"
_MUTED = "#888"

_CARD = {
    "backgroundColor": _CARD_BG,
    "border": f"1px solid {_BORDER}",
    "borderRadius": "8px",
    "padding": "20px",
    "marginBottom": "16px",
}

_LABEL = {
    "color": _MUTED,
    "fontSize": "11px",
    "fontWeight": "600",
    "letterSpacing": "0.08em",
    "textTransform": "uppercase",
    "marginBottom": "12px",
}


def _equity_drawdown_chart(equity_df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if not equity_df.empty:
        eq = equity_df["account_equity"]
        rolling_max = eq.cummax()
        drawdown = ((eq - rolling_max) / rolling_max * 100).fillna(0)

        fig.add_trace(
            go.Scatter(
                x=equity_df["date"],
                y=eq,
                name="Equity",
                line={"color": "#4ade80", "width": 2},
                hovertemplate="%{x}<br>$%{y:,.0f}<extra></extra>",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=equity_df["date"],
                y=drawdown,
                name="Drawdown %",
                fill="tozeroy",
                line={"color": "#ef4444", "width": 1},
                fillcolor="rgba(239,68,68,0.25)",
                hovertemplate="%{x}<br>%{y:.2f}%<extra></extra>",
            ),
            secondary_y=True,
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_CARD_BG,
        plot_bgcolor=_CARD_BG,
        margin={"l": 50, "r": 50, "t": 10, "b": 40},
        legend={"orientation": "h", "y": -0.15},
        hovermode="x unified",
        height=260,
    )
    fig.update_yaxes(title_text="Account Equity ($)", secondary_y=False, gridcolor=_BORDER)
    fig.update_yaxes(title_text="Drawdown (%)", secondary_y=True, gridcolor=_BORDER)
    return fig


def _sharpe_chart(equity_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    if not equity_df.empty and len(equity_df) > 30:
        returns = equity_df["realized_pnl"].pct_change().fillna(0)
        sharpe = (
            returns.rolling(30)
            .apply(lambda r: (r.mean() / r.std() * (252 ** 0.5)) if r.std() > 0 else 0)
            .fillna(0)
        )
        fig.add_trace(
            go.Scatter(
                x=equity_df["date"],
                y=sharpe,
                name="Rolling Sharpe (30d)",
                line={"color": "#a78bfa", "width": 2},
                hovertemplate="%{x}<br>Sharpe: %{y:.2f}<extra></extra>",
            )
        )
        fig.add_hline(y=0, line_dash="dash", line_color=_MUTED, line_width=1)
        fig.add_hline(y=1, line_dash="dot", line_color="#4ade80", line_width=1, annotation_text="Sharpe=1")

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_CARD_BG,
        plot_bgcolor=_CARD_BG,
        margin={"l": 50, "r": 20, "t": 10, "b": 40},
        height=220,
        showlegend=False,
        yaxis={"gridcolor": _BORDER},
        xaxis={"gridcolor": _BORDER},
    )
    return fig


def _analyst_chart(analyst_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    if not analyst_df.empty:
        df = analyst_df.sort_values("win_rate")
        colors = [
            "#4ade80" if r >= 0.5 else "#ef4444"
            for r in df["win_rate"]
        ]
        fig.add_trace(
            go.Bar(
                x=df["win_rate"],
                y=df["analyst_name"],
                orientation="h",
                marker_color=colors,
                text=[f"{r:.0%}" for r in df["win_rate"]],
                textposition="outside",
                hovertemplate="%{y}<br>Win rate: %{x:.1%}<br>Signals: %{customdata}<extra></extra>",
                customdata=df["total_signals"],
            )
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_CARD_BG,
        plot_bgcolor=_CARD_BG,
        margin={"l": 10, "r": 60, "t": 10, "b": 40},
        height=220,
        xaxis={"tickformat": ".0%", "range": [0, 1.1], "gridcolor": _BORDER},
        yaxis={"gridcolor": _BORDER},
        showlegend=False,
    )
    return fig


def _trade_scatter(trades_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    if not trades_df.empty:
        for outcome, color in [("win", "#4ade80"), ("loss", "#ef4444")]:
            sub = trades_df[trades_df["outcome"] == outcome]
            if sub.empty:
                continue
            shares = sub.get("shares", pd.Series([10] * len(sub))).fillna(10)
            fig.add_trace(
                go.Scatter(
                    x=sub["entry_price"],
                    y=sub["pnl_pct"],
                    mode="markers",
                    name=outcome.capitalize(),
                    marker={
                        "color": color,
                        "size": (shares / shares.max() * 18 + 6).clip(6, 24),
                        "opacity": 0.75,
                        "line": {"width": 0},
                    },
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Entry: $%{x:.2f}<br>"
                        "P&L: %{y:.2%}<br>"
                        "%{customdata[1]}<extra></extra>"
                    ),
                    customdata=list(zip(sub["ticker"], sub.get("signal", [""] * len(sub)))),
                )
            )
        fig.add_hline(y=0, line_dash="dash", line_color=_MUTED, line_width=1)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_CARD_BG,
        plot_bgcolor=_CARD_BG,
        margin={"l": 50, "r": 20, "t": 10, "b": 40},
        height=260,
        legend={"orientation": "h", "y": -0.2},
        yaxis={"tickformat": ".1%", "gridcolor": _BORDER},
        xaxis={"title": "Entry Price ($)", "gridcolor": _BORDER},
    )
    return fig


def _pnl_histogram(trades_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    if not trades_df.empty and "pnl_dollars" in trades_df.columns:
        pnl = trades_df["pnl_dollars"].dropna()
        fig.add_trace(
            go.Histogram(
                x=pnl[pnl >= 0],
                name="Profit",
                marker_color="#4ade80",
                opacity=0.8,
                nbinsx=20,
            )
        )
        fig.add_trace(
            go.Histogram(
                x=pnl[pnl < 0],
                name="Loss",
                marker_color="#ef4444",
                opacity=0.8,
                nbinsx=20,
            )
        )
        fig.add_vline(x=0, line_dash="dash", line_color=_MUTED, line_width=1)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=_CARD_BG,
        plot_bgcolor=_CARD_BG,
        margin={"l": 50, "r": 20, "t": 10, "b": 40},
        height=220,
        barmode="overlay",
        legend={"orientation": "h", "y": -0.2},
        xaxis={"title": "P&L ($)", "gridcolor": _BORDER},
        yaxis={"title": "Count", "gridcolor": _BORDER},
    )
    return fig


def _skill_library_panel(skills: list) -> html.Div:
    if not skills:
        return html.Div("No skills found.", style={"color": _MUTED, "fontSize": "13px"})

    items = []
    for skill in skills:
        name = skill.get("name", "Unnamed")
        description = skill.get("description", "")
        protected = skill.get("protected", False)

        badge = (
            html.Span(
                "\U0001f512 Protected",
                style={
                    "fontSize": "10px",
                    "background": "rgba(239,68,68,0.15)",
                    "color": "#ef4444",
                    "border": "1px solid rgba(239,68,68,0.4)",
                    "borderRadius": "4px",
                    "padding": "1px 6px",
                    "marginLeft": "8px",
                    "verticalAlign": "middle",
                },
            )
            if protected
            else None
        )

        items.append(
            html.Div(
                [
                    html.Div(
                        [html.Span(name, style={"fontWeight": "600", "color": _TEXT}), badge],
                        style={"marginBottom": "2px"},
                    ),
                    html.Div(description, style={"color": _MUTED, "fontSize": "12px"}),
                ],
                style={
                    "padding": "10px 12px",
                    "borderBottom": f"1px solid {_BORDER}",
                },
            )
        )

    return html.Div(items, style={"maxHeight": "300px", "overflowY": "auto"})


def advanced_layout(data: dict) -> html.Div:
    equity_df = data.get("equity_curve", pd.DataFrame())
    analyst_df = data.get("analyst_performance", pd.DataFrame())
    trades_df = data.get("trades_full", pd.DataFrame())
    skills = data.get("skill_library", [])

    grid2 = {"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}

    return html.Div(
        [
            # Row 1: equity + drawdown
            html.Div(
                [
                    html.Div("Equity Curve & Drawdown", style=_LABEL),
                    dcc.Graph(figure=_equity_drawdown_chart(equity_df), config={"displayModeBar": False}),
                ],
                style=_CARD,
            ),
            # Row 2: sharpe + analyst
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Rolling 30-Day Sharpe Ratio", style=_LABEL),
                            dcc.Graph(figure=_sharpe_chart(equity_df), config={"displayModeBar": False}),
                        ],
                        style=_CARD,
                    ),
                    html.Div(
                        [
                            html.Div("Analyst Win Rate", style=_LABEL),
                            dcc.Graph(figure=_analyst_chart(analyst_df), config={"displayModeBar": False}),
                        ],
                        style=_CARD,
                    ),
                ],
                style=grid2,
            ),
            # Row 3: scatter + histogram
            html.Div(
                [
                    html.Div(
                        [
                            html.Div("Trade Scatter (Entry Price vs P&L %)", style=_LABEL),
                            dcc.Graph(figure=_trade_scatter(trades_df), config={"displayModeBar": False}),
                        ],
                        style=_CARD,
                    ),
                    html.Div(
                        [
                            html.Div("P&L Distribution", style=_LABEL),
                            dcc.Graph(figure=_pnl_histogram(trades_df), config={"displayModeBar": False}),
                        ],
                        style=_CARD,
                    ),
                ],
                style=grid2,
            ),
            # Row 4: skill library
            html.Div(
                [
                    html.Div("Hermes Skill Library", style=_LABEL),
                    _skill_library_panel(skills),
                ],
                style=_CARD,
            ),
        ],
        style={"padding": "0 4px"},
    )
