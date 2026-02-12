from contexts.insights.application.ports.metrics import MetricsPort

from adapters.outbound.observability.metrics import inc_counter


class MetricsAdapter(MetricsPort):
    def inc_counter(self, name: str, value: int = 1) -> None:
        inc_counter(name, value)
