from stop_loss.ingestion.providers.macro import FREDProvider
from stop_loss.ingestion.providers.market import YahooFinanceProvider
from stop_loss.ingestion.providers.news import GDELTProvider
from stop_loss.ingestion.providers.weather import OpenMeteoProvider

__all__ = [
    "FREDProvider",
    "GDELTProvider",
    "OpenMeteoProvider",
    "YahooFinanceProvider",
]
