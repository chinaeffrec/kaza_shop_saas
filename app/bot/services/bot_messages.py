from typing import Dict, List

_sent: Dict[int, List[int]] = {}

def track(user_id: int, message_id: int):
    if user_id not in _sent:
        _sent[user_id] = []
    if message_id not in _sent[user_id]:
        _sent[user_id].append(message_id)

async def clear_and_reset(user_id: int, bot) -> None:
    mids = _sent.pop(user_id, [])
    for mid in sorted(mids, reverse=True):
        try:
            await bot.delete_message(user_id, mid)
        except Exception:
            pass