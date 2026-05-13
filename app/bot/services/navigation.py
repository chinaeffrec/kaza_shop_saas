from collections import defaultdict
from typing import Optional

from app.bot.states.screen import Screen


class NavigationStack:
    def __init__(self):
        self._stack: dict[int, list[Screen]] = defaultdict(list)

    def push(self, user_id: int, state: Screen) -> None:
        self._stack[user_id].append(state)

    def pop(self, user_id: int) -> Optional[Screen]:
        if self._stack[user_id]:
            return self._stack[user_id].pop()
        return None

    def peek(self, user_id: int) -> Optional[Screen]:
        if self._stack[user_id]:
            return self._stack[user_id][-1]
        return None

    def reset(self, user_id: int) -> None:
        self._stack[user_id].clear()

    def size(self, user_id: int) -> int:
        return len(self._stack[user_id])


# singleton
navigation = NavigationStack()