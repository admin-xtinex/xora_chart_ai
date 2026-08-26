"""
chart_pattern module — Phase 1 skeleton only.

In Phase 2 this package will implement the Analyzer protocol from xora_trade_ai:

    class Analyzer(Protocol):
        key: str
        version: str
        def analyze(self, snapshot, config) -> FeatureResult: ...

For now it only exposes the static pattern catalog so the contract surface is ready.
"""

from xora_chart.catalog import get_pattern, list_patterns

__all__ = ["get_pattern", "list_patterns"]

# Placeholder for the future MODULE object expected by trade_ai discovery.
# MODULE = ChartPatternAnalyzer()   # Phase 2
