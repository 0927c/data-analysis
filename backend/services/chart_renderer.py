"""将结构化数据转为 ECharts option JSON，替代 AntV Studio 外部 API。"""

from __future__ import annotations
from typing import Optional


# 亮色主题色板（适配白色背景）
COLORS = [
    '#2979ff', '#ff5252', '#ffab00', '#00c853', '#7c4dff',
    '#ff6e40', '#00bfa5', '#d50000', '#1976d2', '#f57c00',
    '#388e3c', '#651fff', '#00897b', '#e65100', '#1565c0',
    '#c62828', '#2e7d32', '#757575',
]

# 亮色主题：文字用深色，背景用白色
TEXT_COLOR = '#1a2332'
TEXT_SECONDARY = '#5a6a7a'
AXIS_LINE_COLOR = '#d0d5dd'
SPLIT_LINE_COLOR = '#e8ecf1'
CARD_BORDER_COLOR = '#e2e6ed'
TOOLTIP_BG = 'rgba(255, 255, 255, 0.96)'
TOOLTIP_BORDER = '#e2e6ed'

TOOLTIP_STYLE = {
    'backgroundColor': TOOLTIP_BG,
    'borderColor': TOOLTIP_BORDER,
    'borderWidth': 1,
    'textStyle': {'color': TEXT_COLOR, 'fontSize': 13},
    'padding': [10, 14],
    'extraCssText': 'box-shadow: 0 2px 12px rgba(0,0,0,0.1); border-radius: 8px;',
}

AXIS_STYLE = {
    'axisLine': {'lineStyle': {'color': AXIS_LINE_COLOR}},
    'axisLabel': {'color': TEXT_SECONDARY},
    'splitLine': {'lineStyle': {'color': SPLIT_LINE_COLOR}},
}

ANIMATION_DEFAULTS = {
    'animationDuration': 800,
    'animationEasing': 'cubicOut',
}


def _gradient_bar(start: str = '#2979ff', end: str = '#64b5f6') -> dict:
    return {
        'color': {
            'type': 'linear',
            'x': 0, 'y': 0, 'x2': 1, 'y2': 0,
            'colorStops': [
                {'offset': 0, 'color': start},
                {'offset': 1, 'color': end},
            ],
        }
    }


def render_horizontal_bar(labels: list, values: list, title: str = '', color: Optional[str] = None) -> dict:
    """横向柱状图（产品线分布等）。"""
    rev_labels = list(reversed(labels))
    rev_values = list(reversed(values))
    grad = color or ('#2979ff', '#64b5f6')
    item_style = _gradient_bar(*grad) if isinstance(grad, tuple) else grad

    return {
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}, **TOOLTIP_STYLE},
        'grid': {'left': 120, 'right': 60, 'top': 10, 'bottom': 30},
        'xAxis': {'type': 'value', **AXIS_STYLE},
        'yAxis': {
            'type': 'category',
            'data': rev_labels,
            'axisLine': {'lineStyle': {'color': AXIS_LINE_COLOR}},
            'axisLabel': {'color': TEXT_COLOR, 'fontSize': 13, 'fontWeight': 500},
        },
        'series': [{
            'type': 'bar',
            'data': rev_values,
            'itemStyle': {
                **item_style,
                'borderRadius': [0, 4, 4, 0],
            },
            'barWidth': 20,
            'label': {'show': True, 'position': 'right', 'color': TEXT_SECONDARY, 'fontSize': 12, 'fontWeight': 600},
            **ANIMATION_DEFAULTS,
        }],
    }


def render_pie(labels: list, values: list, title: str = '') -> dict:
    """环形饼图（原因大类占比等）。"""
    data = [
        {'name': l, 'value': v, 'itemStyle': {'color': COLORS[i % len(COLORS)]}}
        for i, (l, v) in enumerate(zip(labels, values))
    ]
    return {
        'tooltip': {
            'trigger': 'item',
            'formatter': '{b}: {c}件 ({d}%)',
            **TOOLTIP_STYLE,
        },
        'legend': {
            'orient': 'vertical', 'right': 10, 'top': 'center',
            'textStyle': {'color': TEXT_COLOR, 'fontSize': 12},
            'itemWidth': 12, 'itemHeight': 12,
        },
        'series': [{
            'type': 'pie',
            'radius': ['40%', '70%'],
            'center': ['40%', '50%'],
            'avoidLabelOverlap': True,
            'itemStyle': {'borderRadius': 6, 'borderColor': '#fff', 'borderWidth': 2},
            'label': {'show': True, 'color': TEXT_COLOR, 'fontSize': 12, 'formatter': '{b}\n{d}%', 'fontWeight': 500},
            'labelLine': {'lineStyle': {'color': CARD_BORDER_COLOR}},
            'data': data,
            **ANIMATION_DEFAULTS,
        }],
    }


def render_bar(labels: list, values: list, title: str = '', horizontal: bool = False) -> dict:
    """纵向/横向柱状图（不良类型 TOP15 等）。"""
    if horizontal:
        return render_horizontal_bar(labels, values, title)

    item_style_data = []
    for i, v in enumerate(values):
        if v >= 200:
            grad = _gradient_bar('#d32f2f', '#ef5350')
        elif v >= 80:
            grad = _gradient_bar('#f57c00', '#ffb74d')
        else:
            grad = _gradient_bar('#2979ff', '#64b5f6')
        item_style_data.append({
            'value': v,
            'itemStyle': {**grad, 'borderRadius': [0, 4, 4, 0]},
        })

    return {
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}, **TOOLTIP_STYLE},
        'grid': {'left': 120, 'right': 60, 'top': 10, 'bottom': 30},
        'xAxis': {'type': 'value', **AXIS_STYLE},
        'yAxis': {
            'type': 'category',
            'data': list(reversed(labels)),
            'axisLine': {'lineStyle': {'color': AXIS_LINE_COLOR}},
            'axisLabel': {'color': TEXT_COLOR, 'fontSize': 13, 'fontWeight': 500},
        },
        'series': [{
            'type': 'bar',
            'data': item_style_data,
            'barWidth': 18,
            'label': {'show': True, 'position': 'right', 'color': TEXT_SECONDARY, 'fontSize': 12, 'fontWeight': 600},
            **ANIMATION_DEFAULTS,
        }],
    }


def render_stacked_bar(products: list, causes: dict, title: str = '') -> dict:
    """堆叠柱状图（产品线 × 原因交叉）。"""
    cause_names = list(causes.keys())
    series = []
    for i, cn in enumerate(cause_names):
        series.append({
            'name': cn,
            'type': 'bar',
            'stack': 'total',
            'emphasis': {'focus': 'series'},
            'itemStyle': {'color': COLORS[i % len(COLORS)]},
            'data': [int(causes[cn].get(p, 0)) for p in products],
            **ANIMATION_DEFAULTS,
        })

    return {
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'shadow'}, **TOOLTIP_STYLE},
        'legend': {
            'top': 0,
            'textStyle': {'color': TEXT_COLOR, 'fontSize': 11},
            'itemWidth': 12, 'itemHeight': 12,
        },
        'grid': {'left': 50, 'right': 20, 'top': 40, 'bottom': 60},
        'xAxis': {
            'type': 'category',
            'data': products,
            'axisLabel': {'color': TEXT_COLOR, 'fontSize': 11, 'rotate': 30, 'fontWeight': 500},
            'axisLine': {'lineStyle': {'color': AXIS_LINE_COLOR}},
        },
        'yAxis': {'type': 'value', **AXIS_STYLE},
        'series': series,
    }


def render_rose(labels: list, values: list, title: str = '') -> dict:
    """南丁格尔玫瑰图（制造/研发原因细分）。"""
    data = [
        {'name': l, 'value': v, 'itemStyle': {'color': COLORS[i % len(COLORS)]}}
        for i, (l, v) in enumerate(zip(labels, values))
    ]
    return {
        'tooltip': {
            'trigger': 'item',
            'formatter': '{b}: {c}件 ({d}%)',
            **TOOLTIP_STYLE,
        },
        'legend': {
            'orient': 'vertical', 'right': 0, 'top': 'middle',
            'textStyle': {'color': TEXT_COLOR, 'fontSize': 11},
            'itemWidth': 10, 'itemHeight': 10,
        },
        'series': [{
            'type': 'pie',
            'radius': ['35%', '65%'],
            'center': ['35%', '50%'],
            'roseType': 'radius',
            'itemStyle': {'borderRadius': 5, 'borderColor': '#fff', 'borderWidth': 2},
            'label': {'color': TEXT_COLOR, 'fontSize': 11, 'formatter': '{b}', 'fontWeight': 500},
            'data': data,
            **ANIMATION_DEFAULTS,
        }],
    }


def render_line(dates: list, series_list: list[dict], title: str = '') -> dict:
    """平滑面积线图（趋势分析）。
    series_list: [{'name': str, 'data': list[float], 'color': str}]
    """
    series = []
    for i, s in enumerate(series_list):
        series.append({
            'name': s['name'],
            'type': 'line',
            'smooth': True,
            'symbol': 'circle',
            'symbolSize': 6,
            'itemStyle': {'color': s.get('color', COLORS[i % len(COLORS)])},
            'areaStyle': {
                'opacity': 0.15,
                'color': {
                    'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                    'colorStops': [
                        {'offset': 0, 'color': s.get('color', COLORS[i % len(COLORS)])},
                        {'offset': 1, 'color': 'rgba(0,0,0,0)'},
                    ],
                },
            },
            'data': s['data'],
            **ANIMATION_DEFAULTS,
        })

    return {
        'tooltip': {'trigger': 'axis', 'axisPointer': {'type': 'line'}, **TOOLTIP_STYLE},
        'legend': {
            'top': 0,
            'textStyle': {'color': TEXT_COLOR, 'fontSize': 12},
            'itemWidth': 14, 'itemHeight': 14,
        },
        'grid': {'left': 60, 'right': 30, 'top': 40, 'bottom': 30},
        'xAxis': {
            'type': 'category',
            'data': dates,
            'axisLabel': {'color': TEXT_SECONDARY, 'fontSize': 11, 'rotate': 20},
            'axisLine': {'lineStyle': {'color': AXIS_LINE_COLOR}},
        },
        'yAxis': {'type': 'value', **AXIS_STYLE},
        'series': series,
    }


def render_gauge(value: float, max_val: float, title: str = '', label: str = '') -> dict:
    """半圆仪表盘（KPI 指标）。"""
    pct = (value / max_val * 100) if max_val > 0 else 0
    if pct < 50:
        color = '#00c853'
    elif pct < 80:
        color = '#ffab00'
    else:
        color = '#ff5252'

    return {
        'tooltip': {
            'formatter': '{a}: {b}',
            **TOOLTIP_STYLE,
        },
        'series': [{
            'name': title or '指标',
            'type': 'gauge',
            'startAngle': 180,
            'endAngle': 0,
            'min': 0,
            'max': max_val,
            'splitNumber': 5,
            'axisLine': {
                'lineStyle': {
                    'width': 16,
                    'color': [
                        (0.5, '#00c853'),
                        (0.8, '#ffab00'),
                        (1, '#ff5252'),
                    ],
                },
            },
            'pointer': {
                'itemStyle': {'color': color},
                'width': 4,
            },
            'axisTick': {'distance': -16, 'length': 6, 'lineStyle': {'color': TEXT_SECONDARY, 'width': 1}},
            'splitLine': {'distance': -20, 'length': 14, 'lineStyle': {'color': TEXT_SECONDARY, 'width': 2}},
            'axisLabel': {'color': TEXT_SECONDARY, 'fontSize': 11, 'distance': -12},
            'detail': {
                'valueAnimation': True,
                'formatter': '{value}',
                'color': TEXT_COLOR,
                'fontSize': 28,
                'fontWeight': 'bold',
                'offsetCenter': [0, '30%'],
            },
            'title': {'offsetCenter': [0, '60%'], 'color': TEXT_SECONDARY, 'fontSize': 13},
            'data': [{'value': value, 'name': label or title}],
            **ANIMATION_DEFAULTS,
        }],
    }


def render_scatter(x_data: list, y_data: list, labels: list, title: str = '',
                   x_label: str = '', y_label: str = '') -> dict:
    """气泡散点图（相关性分析）。"""
    data = [
        {
            'value': [x_data[i], y_data[i]],
            'name': labels[i] if i < len(labels) else f'#{i}',
            'symbolSize': max(8, min(30, y_data[i] / max(y_data) * 30)) if max(y_data) > 0 else 12,
            'itemStyle': {
                'color': {
                    'type': 'radial', 'x': 0.5, 'y': 0.5, 'r': 0.5,
                    'colorStops': [
                        {'offset': 0, 'color': COLORS[i % len(COLORS)]},
                        {'offset': 1, 'color': COLORS[(i + 3) % len(COLORS)]},
                    ],
                },
            },
        }
        for i in range(len(x_data))
    ]

    return {
        'tooltip': {
            'trigger': 'item',
            'formatter': '{b}<br/>{c}',
            **TOOLTIP_STYLE,
        },
        'grid': {'left': 60, 'right': 30, 'top': 30, 'bottom': 40},
        'xAxis': {
            'name': x_label,
            'nameTextStyle': {'color': TEXT_SECONDARY},
            'type': 'value',
            **AXIS_STYLE,
        },
        'yAxis': {
            'name': y_label,
            'nameTextStyle': {'color': TEXT_SECONDARY},
            'type': 'value',
            **AXIS_STYLE,
        },
        'series': [{
            'type': 'scatter',
            'data': data,
            'emphasis': {
                'itemStyle': {
                    'shadowBlur': 10,
                    'shadowColor': 'rgba(0, 212, 255, 0.5)',
                },
            },
            **ANIMATION_DEFAULTS,
        }],
    }
