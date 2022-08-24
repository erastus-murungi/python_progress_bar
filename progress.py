import sys
import uuid
from abc import ABC, abstractmethod
from itertools import cycle
from math import ceil
from random import randint
from time import monotonic, sleep
from typing import TextIO, Iterable

from termcolor import colored

ANSI_ERASE_CURRENT_LINE = "\x1b[2K"
ANSI_MOVE_CURSOR_UP_ONE_LINE = "\x1b[1A"
ANSI_HIDE_CURSOR = "\x1b[?25l"
ANSI_SHOW_CURSOR = "\x1b[?25h"

PROGRESS_SPINNER_SEQUENCE = cycle("◐ ◓ ◑ ◒".split())


COMPLETED_JOBS_REFRESH_TIME = 1.5
FRAMES_PER_CYCLE = 1.0 / 30.0

MAX_NUMBER_CHARACTERS_HEADER_PROGRESS_BAR = 30

INDENT = "    "


def get_green_bold_colored(text: str) -> str:
    return colored(f"{text}", "green", attrs=["bold"])


class DeterminateProgressItem(ABC):
    id: uuid.UUID

    def __init__(self):
        self.id = uuid.uuid4()

    @abstractmethod
    def get_normalized_progress(self) -> float:
        """
        Returns the progress of this time with 1 being complete

        :return: The progress from 0 to 1
        """

    @abstractmethod
    def is_completed(self) -> bool:
        pass

    @abstractmethod
    def start_progress(self) -> bool:
        pass

    def is_not_completed(self):
        return not self.is_completed()

    def get_percentage_progress(self) -> float:
        return self.get_normalized_progress() * 100

    def get_progress_item_title(self) -> str:
        """
        Return a title to display

        """
        return str(self.id)

    def pretty_print_progress(self, text_io: TextIO = sys.stdout) -> None:
        progress_item_title = self.get_progress_item_title()
        progress_spinner_code_point = next(PROGRESS_SPINNER_SEQUENCE)
        if self.is_completed():
            # we define done_str because f-strings do not allow `\`
            done_str = "\u2714 Done!"
            text_io.write(
                f"{INDENT}{get_green_bold_colored(done_str)} [{progress_item_title}]\n"
            )
        else:
            text_io.write(
                f"{INDENT}{progress_spinner_code_point} {self.get_percentage_progress():04.2f} % [{progress_item_title}]\n"
            )


class MockDownload(DeterminateProgressItem):
    start_time: float

    def __init__(self, download_size: float, bandwidth: float):
        super().__init__()
        self.size = download_size
        self.bandwidth = bandwidth
        self.expected_download_duration: float = download_size / bandwidth
        self.is_finished: bool = False

    def start_progress(self) -> None:
        self.start_time = monotonic()

    def get_normalized_progress(self):
        if self.is_finished:
            return 1.0
        normalized_progress = (
            monotonic() - self.start_time
        ) / self.expected_download_duration
        if normalized_progress >= 1.0:
            self.is_finished = True
        return min(normalized_progress, 1.0)

    def is_completed(self):
        return (
            self.is_finished
            or (monotonic() - self.start_time) > self.expected_download_duration
        )

    def __repr__(self):
        return f"{self.__class__.__qualname__}(size={self.size}MB, bandwidth={self.bandwidth}MBps)"


class ProgressBarManager:
    progress_items: tuple[DeterminateProgressItem, ...]

    def __init__(self, progress_items: Iterable[DeterminateProgressItem]):
        self.progress_items = tuple(progress_items)

    @staticmethod
    def delete_ascii_terminal_line(text_io: TextIO = sys.stdout):
        text_io.write(ANSI_ERASE_CURRENT_LINE)
        text_io.write(ANSI_MOVE_CURSOR_UP_ONE_LINE)

    def pretty_print_progress_bar_header(self, text_io: TextIO):
        n_jobs_total = len(self.progress_items)
        n_jobs_completed = len(
            tuple(filter(lambda p: p.is_completed(), self.progress_items))
        )

        n_filled = ceil(
            n_jobs_completed / n_jobs_total * MAX_NUMBER_CHARACTERS_HEADER_PROGRESS_BAR
        )
        n_left = MAX_NUMBER_CHARACTERS_HEADER_PROGRESS_BAR - n_filled

        text_io.write(
            f'{INDENT}{get_green_bold_colored("Downloading")}  '
            f'[{"=" * (n_filled - 1) + ">"}{" " * n_left}] [{n_jobs_completed} / {n_jobs_total} downloaded]  \n'
        )

    def initialize_all_progress_items(self):
        for progress_item in self.progress_items:
            progress_item.start_progress()

    def pretty_print_all_progress_items(
        self,
        progress_items: tuple[DeterminateProgressItem, ...],
        text_io: TextIO = sys.stdout,
    ):
        progress_items = tuple(
            sorted(
                progress_items,
                key=lambda p: p.get_normalized_progress(),
                reverse=True,
            )
        )
        for progress_item in progress_items:
            progress_item.pretty_print_progress()
        sleep(FRAMES_PER_CYCLE)
        for _ in range(len(progress_items)):
            self.delete_ascii_terminal_line()
        text_io.write(ANSI_ERASE_CURRENT_LINE)

    def get_incomplete_progress_items_state(
        self,
    ) -> tuple[tuple[DeterminateProgressItem, ...], float]:
        return (
            tuple(filter(lambda p: p.is_not_completed(), self.progress_items)),
            monotonic(),
        )

    def run(self, text_io: TextIO = sys.stdout):
        self.initialize_all_progress_items()

        (
            incomplete_progress_items,
            incomplete_progress_items_update_time,
        ) = self.get_incomplete_progress_items_state()
        while incomplete_progress_items:
            text_io.write(ANSI_HIDE_CURSOR)
            self.pretty_print_progress_bar_header(text_io)
            while (
                monotonic() - incomplete_progress_items_update_time
                < COMPLETED_JOBS_REFRESH_TIME
            ):
                self.pretty_print_all_progress_items(incomplete_progress_items, text_io)

            (
                incomplete_progress_items,
                incomplete_progress_items_update_time,
            ) = self.get_incomplete_progress_items_state()
            self.delete_ascii_terminal_line()
        self.pretty_print_progress_bar_header(text_io)
        self.delete_ascii_terminal_line()
        text_io.write(ANSI_ERASE_CURRENT_LINE)
        text_io.write(get_green_bold_colored(f"{INDENT}Completed"))
        text_io.write(ANSI_SHOW_CURSOR)


if __name__ == "__main__":
    DOWNLOAD_SPEED = 100  # 10MB per sec
    NUMBER_OF_ITEMS = 10
    downloads = [
        MockDownload(randint(1, 100), DOWNLOAD_SPEED / NUMBER_OF_ITEMS)
        for _ in range(NUMBER_OF_ITEMS)
    ]
    progress_bar_manager = ProgressBarManager(downloads)
    progress_bar_manager.run()
