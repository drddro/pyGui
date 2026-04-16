from abc import ABC, abstractmethod



class OnExit(ABC):
    @abstractmethod
    def on_exit(self) -> None:
        pass