from typing import Any

from stop_loss.domain.enums import DataType
from stop_loss.domain.models import NormalizedRecord
from stop_loss.ingestion.base import DataProvider


class GDELTProvider(DataProvider):
    """News intelligence provider leveraging GDELT (Global Database of Events, Language, and Tone).

    Responsible for ingesting geopolitical, commodity disruption, and severe weather news
    coverage in real-time. Implementation scheduled for Checkpoint 1.
    """

    @property
    def name(self) -> str:
        return "gdelt"

    @property
    def data_type(self) -> DataType:
        return DataType.NEWS

    def fetch(self, **kwargs: Any) -> Any:
        """Fetch raw GDELT news events and articles.

        To be implemented in Checkpoint 1.
        """
        raise NotImplementedError("GDELTProvider.fetch() will be implemented in Checkpoint 1.")

    def normalize(self, raw_data: Any) -> list[NormalizedRecord]:
        """Normalize GDELT articles into NormalizedRecord instances.

        To be implemented in Checkpoint 1.
        """
        raise NotImplementedError("GDELTProvider.normalize() will be implemented in Checkpoint 1.")
