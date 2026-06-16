import asyncio

from loguru import logger


class RuntimeStateManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
            cls._instance._lock = asyncio.Lock()
            cls._instance._current_stage = "idle"
            cls._instance._active_worker = "none"
        return cls._instance

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    @property
    def current_stage(self) -> str:
        return self._current_stage

    @current_stage.setter
    def current_stage(self, val: str):
        self._current_stage = val

    @property
    def active_worker(self) -> str:
        return self._active_worker

    @active_worker.setter
    def active_worker(self, val: str):
        self._active_worker = val

runtime_state = RuntimeStateManager()
