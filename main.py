from abc import ABC, abstractmethod
from math import ceil
from time import monotonic, sleep
from termcolor import colored
from itertools import cycle
import sys
from random import randint
import uuid


ANSI_CLEAR_CURRENT_LINE = "\33[2K"
ANSI_MOVE_CURSOR_UP = "\u001b[A"
ANSI_HIDE_CURSOR = "\x1b[?25l"
ANSI_SHOW_CURSOR = "\x1b[?25h"''

PROGRESS_ICONS = cycle("◐ ◓ ◑ ◒".split())


class ProgressItem(ABC):
    id: uuid.UUID

    def __init__(self):
        self.id = uuid.uuid4()

    @abstractmethod
    def current_progress(self) -> float:
        pass

    @abstractmethod
    def completed(self) -> bool:
        pass

    def not_completed(self):
        return not self.completed()

    @abstractmethod
    def start(self) -> bool:
        pass

    def current_progress_percentage(self):
        return self.current_progress() * 100

    def print_updates(self):
        progress_icon = next(PROGRESS_ICONS)
        if self.completed():
            sys.stdout.write(
                colored(f"    \u2714 Done!", "green", attrs=["bold"])
                + f" [{str(self.id)}]\n"
            )
        else:
            sys.stdout.write(
                f"    {progress_icon} {self.current_progress_percentage():04.2f} % [{str(self.id)}]\n"
            )


class MockDownload(ProgressItem):
    start_time: float
    is_finished: bool = False

    def __init__(self, size: float, bandwidth: float):
        super().__init__()
        self.size = size
        self.bandwidth = bandwidth
        self.duration = size / bandwidth

    def start(self):
        self.start_time = monotonic()

    def current_progress(self):
        if self.is_finished:
            return 1.0
        current = monotonic()
        progress = (current - self.start_time) / self.duration
        if progress >= 1.0:
            self.is_finished = True
        return min(progress, 1.0)

    def completed(self):
        return self.is_finished

    def __repr__(self):
        return f"{self.__class__.__qualname__}(size={self.size}MB, bandwidth={self.bandwidth}MBps)"


class ProgressBarManager:
    progress_items: tuple[ProgressItem, ...]

    def __init__(self, *progress_items):
        self.progress_items = tuple(progress_items)

    @staticmethod
    def delete_line():
        sys.stdout.write(ANSI_CLEAR_CURRENT_LINE)
        sys.stdout.write(ANSI_MOVE_CURSOR_UP)

    def print_header_progress_bar(self, completed):
        all_items = len(self.progress_items)
        completed = len(completed)
        uncompleted = all_items - completed

        n_chars = 30
        n_filled = max(0, ceil(uncompleted / all_items * n_chars))
        n_left = n_chars - n_filled

        sys.stdout.write(
            f'    {colored("Downloading", "green", attrs=["bold"])}  [{"="*(n_filled-1) + ">"}{" "*n_left}] [{uncompleted} / {all_items} downloaded]  \n'
        )

    def print(self):
        for progress_item in self.progress_items:
            progress_item.start()

        progress_items = self.progress_items
        last_time = monotonic()
        while progress_items:
            sys.stdout.write(ANSI_HIDE_CURSOR)
            self.print_header_progress_bar(progress_items)
            while monotonic() - last_time < 1.5:
                progress_items = tuple(
                    sorted(
                        progress_items, key=lambda p: p.current_progress(), reverse=True
                    )
                )
                for progress_item in progress_items:
                    progress_item.print_updates()
                sleep(0.2)
                for _ in range(len(progress_items)):
                    self.delete_line()
                sys.stdout.write(ANSI_CLEAR_CURRENT_LINE)
            last_time = monotonic()
            progress_items = tuple(
                filter(lambda p: p.not_completed(), self.progress_items)
            )
            self.delete_line()
        self.print_header_progress_bar(progress_items)
        self.delete_line()
        sys.stdout.write(ANSI_CLEAR_CURRENT_LINE)
        sys.stdout.write(f"{colored('Completed', 'green', attrs=['bold'])}")

        print(ANSI_SHOW_CURSOR)


if __name__ == "__main__":
    DOWNLOAD_SPEED = 200  # 10MB per sec
    NUMBER_OF_ITEMS = 30
    downloads = [
        MockDownload(randint(0, 100), DOWNLOAD_SPEED / NUMBER_OF_ITEMS)
        for _ in range(NUMBER_OF_ITEMS)
    ]
    progress_bar_manager = ProgressBarManager(*downloads)
    progress_bar_manager.print()
