from enum import Enum
from dataclasses import dataclass
from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class SliderAction(Enum):
    PLAY = "play"
    PAUSE = "pause"
    PREV = "prev"
    NEXT = "next"
    INFO = "info"
    TO_FILTERS = "to_filters"
    EDIT = "edit_product"


@dataclass
class SliderCallbackData:
    action: SliderAction
    index: Optional[int] = None
    total: Optional[int] = None

    def to_callback_data(self) -> str:
        data = [self.action.value]
        if self.index is not None:
            data.append(str(self.index))
        if self.total is not None:
            data.append(str(self.total))
        return ":".join(data)

    @classmethod
    def from_callback_data(cls, callback_data: str) -> "SliderCallbackData":
        parts = callback_data.split(":")
        action = SliderAction(parts[0])
        index = int(parts[1]) if len(parts) > 1 else None
        total = int(parts[2]) if len(parts) > 2 else None
        return cls(action=action, index=index, total=total)


def create_slider_keyboard(
        paused: bool = False,
        expanded: bool = False,
        index: int = 0,
        total: int = 0,
        user_id: Optional[int] = None,
        admins: list[int] = None
) -> InlineKeyboardMarkup:
    """
    Create a slider keyboard with play/pause controls and navigation buttons.

    Args:
        paused: Whether the slider is currently paused
        expanded: Whether to show additional controls
        index: Current item index (0-based)
        total: Total number of items
        user_id: ID of the user viewing the keyboard
        admins: List of admin user IDs
    """
    # Control buttons (play/pause)
    control_buttons = [
        InlineKeyboardButton(
            text="||" if not paused else "ᐅ",
            callback_data=SliderCallbackData(
                action=SliderAction.PAUSE if not paused else SliderAction.PLAY,
                index=index,
                total=total
            ).to_callback_data()
        )
    ]

    # Navigation buttons
    nav_buttons = [
        InlineKeyboardButton(
            text=f"{index + 1}/{total}",
            callback_data=SliderCallbackData(
                action=SliderAction.INFO,
                index=index,
                total=total
            ).to_callback_data()
        ),
        InlineKeyboardButton(
            text="←",
            callback_data=SliderCallbackData(
                action=SliderAction.PREV,
                index=index,
                total=total
            ).to_callback_data()
        ),
        InlineKeyboardButton(
            text="→",
            callback_data=SliderCallbackData(
                action=SliderAction.NEXT,
                index=index,
                total=total
            ).to_callback_data()
        ),
        InlineKeyboardButton(
            text="🔍",
            callback_data=SliderCallbackData(
                action=SliderAction.TO_FILTERS,
                index=index,
                total=total
            ).to_callback_data()
        )
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[control_buttons])

    if expanded or paused:
        keyboard.inline_keyboard.append(nav_buttons)

        # Add edit button for admins
        if user_id in (admins or []):
            edit_button = [
                InlineKeyboardButton(
                    text="✏️ Редактировать",
                    callback_data=SliderCallbackData(
                        action=SliderAction.EDIT,
                        index=index,
                        total=total
                    ).to_callback_data()
                )
            ]
            keyboard.inline_keyboard.append(edit_button)

    return keyboard