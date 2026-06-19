from abc import ABC, abstractmethod


class IWorker(ABC):
    """
    Standard interface for background services in the worker boundary.
    """
    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass
