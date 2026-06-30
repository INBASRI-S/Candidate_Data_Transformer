from abc import ABC, abstractmethod
from app.models.schemas import RawCandidate

class BaseParser(ABC):
    @abstractmethod
    def parse(self, source: str) -> RawCandidate:
        """
        Parses candidate information from the given source.
        'source' can be a filepath, a JSON string, or a username depending on the parser.
        Returns a RawCandidate Pydantic model.
        """
        pass
