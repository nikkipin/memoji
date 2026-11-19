#!/usr/bin/env python3
"""Create a Telegram sticker set from a folder of 512 px PNG or WEBP images, using the Bot API.

Setup, once:
  1. In Telegram, message @BotFather, send /newbot, and follow the prompts.
  2. Save the bot token in ~/.config/telegram-sticker-bot/token (readable only by you).
  3. Open your new bot in Telegram and press Start, so this script can find your user id.

Usage:
  python3 make_telegram_sticker_pack.py ./export --set-name-prefix memoji_3f9a1c07be --dry-run
  python3 make_telegram_sticker_pack.py ./export --set-name-prefix memoji_3f9a1c07be

A set made by a bot must have a link name that ends in "_by_<bot username>", so the link is
t.me/addstickers/<prefix>_by_<bot username>. The prefix is --set-name-prefix, or the folder name.
The title shown in Telegram is --title, or the folder name.
If the set already exists, the script adds only the files after the set's current sticker count,
in file-name order, so a run that stopped part way can be run again.
"""

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from PIL import Image

API_ROOT = "https://api.telegram.org"
DEFAULT_TOKEN_PATH = Path.home() / ".config" / "telegram-sticker-bot" / "token"
STICKER_SIDE_PX = 512
MAX_STICKERS_PER_CREATE = 50
MAX_STICKERS_PER_SET = 120
MAX_RATE_LIMIT_WAITS = 5
REQUEST_TIMEOUT_SECONDS = 120
FALLBACK_EMOJI = "🙂"
SUFFIX_TO_MIME_TYPE = {".png": "image/png", ".webp": "image/webp"}

STEM_TO_EMOJI = {
    "annoyed": "😒",
    "beKind": "🫶",
    "big_happy": "😃",
    "callMe": "🤙",
    "chefs_kiss": "🤌",
    "crossed_fingers": "🤞",
    "crying_face": "😢",
    "dizzy_birds": "😵‍💫",
    "exploding_head": "🤯",
    "face_blowing_a_kiss": "😘",
    "face_screaming_in_fear": "😱",
    "face_with_hand_over_mouth": "🤭",
    "face_with_party_horn": "🥳",
    "face_with_rolling_eyes": "🙄",
    "face_with_starry_eyes": "🤩",
    "face_with_steam_from_nose": "😤",
    "face_with_symbols_over_mouth": "🤬",
    "face_with_tears_of_joy": "😂",
    "finger_heart": "🫰",
    "fist_bump": "🤜",
    "folded_hands": "🙏",
    "front_pucker": "😗",
    "grace_face": "☺️",
    "grinning_face_with_sweat": "😅",
    "grizzled": "😒",
    "halo": "😇",
    "hands_on_hips": "💪",
    "happy": "😊",
    "happy_person_raising_one_hand": "🙋",
    "head_in_clouds": "😶‍🌫️",
    "head_tilt": "😏",
    "hugging_face": "🤗",
    "hushed_face": "😯",
    "one_raised_eyebrow": "🤨",
    "peekaboo": "🫣",
    "person_face_palm": "🤦",
    "person_gesturing_no": "🙅",
    "person_gossiping": "👀",
    "person_meditating": "🧘",
    "person_nervous": "😬",
    "person_shrugging": "🤷",
    "person_tipping_hand": "💁",
    "person_waving": "👋",
    "person_with_lightbulb": "💡",
    "person_with_tissue": "🤧",
    "pleasant_neutral": "🙂",
    "pouting_face": "😡",
    "proud": "😌",
    "pursed_lips": "😗",
    "shushing_face": "🤫",
    "sleeping_face": "😴",
    "slightly_frowning_face": "🙁",
    "smiling_face_with_heart-shaped_eyes": "😍",
    "smiling_face_with_open_mouth_and_smiling_eyes": "😄",
    "smiling_face_with_smiling_eyes_and_three_hearts": "🥰",
    "smirk": "😏",
    "surprise": "😮",
    "talk_to_the_hand": "✋",
    "technologist": "🧑‍💻",
    "thinking_face": "🤔",
    "thumbs_down": "👎",
    "thumbs_up": "👍",
    "tongue_out": "😛",
    "victory_hand": "✌️",
    "wink": "😉",
    "winking_face": "😉",
    "winking_face_with_stuck_out_tongue": "😜",
    "yawn": "🥱",
    "yearbook": "📸",
}


class TelegramError(Exception):
    """A Bot API call failed. The message never contains the bot token."""

    def __init__(self, method: str, description: str):
        super().__init__(f"{method}: {description}")
        self.description = description


@dataclass(frozen=True)
class Sticker:
    path: Path
    emoji: str

    def to_input_sticker(self, attach_name: str) -> dict[str, Any]:
        return {"sticker": f"attach://{attach_name}", "format": "static", "emoji_list": [self.emoji]}

    def to_upload(self) -> tuple[str, bytes, str]:
        return (self.path.name, self.path.read_bytes(), SUFFIX_TO_MIME_TYPE[self.path.suffix.lower()])


@dataclass(frozen=True)
class Owner:
    user_id: int
    display_name: str


class TelegramBot:
    def __init__(self, token: str):
        self._token = token
        self._http = requests.Session()

    def call(
        self,
        method: str,
        data: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> Any:
        for _ in range(MAX_RATE_LIMIT_WAITS + 1):
            reply = self._post(method, data, files)
            if reply.get("ok"):
                return reply["result"]
            retry_after = reply.get("parameters", {}).get("retry_after")
            if retry_after is None:
                raise TelegramError(method, f"{reply.get('error_code')} {reply.get('description')}")
            print(f"  Telegram asked for a {retry_after} s pause before {method}; waiting.")
            time.sleep(retry_after)
        raise TelegramError(method, f"still rate limited after {MAX_RATE_LIMIT_WAITS} pauses")

    def _post(
        self,
        method: str,
        data: dict[str, Any] | None,
        files: dict[str, tuple[str, bytes, str]] | None,
    ) -> dict[str, Any]:
        # The URL holds the token, and requests puts the URL into its exception text,
        # so each failure raises a new error "from None" instead of chaining the original.
        url = f"{API_ROOT}/bot{self._token}/{method}"
        try:
            response = self._http.post(url, data=data, files=files, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            raise TelegramError(method, f"network error ({type(exc).__name__})") from None
        try:
            return response.json()
        except ValueError:
            raise TelegramError(method, f"HTTP {response.status_code} with a reply that is not JSON") from None


def main() -> None:
    args = parse_args()
    folder: Path = args.folder.expanduser().resolve()
    title: str = args.title or folder.name
    set_name_prefix: str = args.set_name_prefix or folder.name.lower()

    stickers = collect_stickers(folder)
    bot = TelegramBot(read_token(args.token_file))
    set_name = f"{set_name_prefix}_by_{bot.call('getMe')['username']}"
    owner = Owner(args.user_id, "given with --user-id") if args.user_id else find_owner(bot)
    existing_count = count_stickers_in_set(bot, set_name)

    print_plan(owner, set_name, title, stickers, existing_count)
    if args.dry_run:
        print("Dry run: nothing uploaded.")
        return
    upload_stickers(bot, owner, set_name, title, stickers, existing_count)
    print(f"Done: '{title}' has {count_stickers_in_set(bot, set_name)} stickers.")
    print(f"Add it in Telegram: https://t.me/addstickers/{set_name}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Telegram sticker set from a folder of images.")
    parser.add_argument("folder", type=Path, help="folder of .png or .webp images, one side exactly 512 px")
    parser.add_argument("--title", help="set title shown in Telegram (default: the folder name)")
    parser.add_argument("--set-name-prefix", help="start of the t.me/addstickers/ link name (default: the folder name)")
    parser.add_argument("--user-id", type=int, help="your Telegram user id, if the script cannot find it")
    parser.add_argument("--token-file", type=Path, default=DEFAULT_TOKEN_PATH, help="file that holds the bot token")
    parser.add_argument("--dry-run", action="store_true", help="check everything and print the plan; upload nothing")
    return parser.parse_args()


def collect_stickers(folder: Path) -> list[Sticker]:
    paths = sorted(
        (path for path in folder.iterdir() if path.suffix.lower() in SUFFIX_TO_MIME_TYPE),
        key=lambda path: path.name.lower(),
    )
    if not paths:
        raise SystemExit(f"No .png or .webp files in {folder}")
    if len(paths) > MAX_STICKERS_PER_SET:
        raise SystemExit(f"{len(paths)} images, but a sticker set holds at most {MAX_STICKERS_PER_SET}")
    wrong_size_names = [path.name for path in paths if not is_valid_sticker_size(path)]
    if wrong_size_names:
        raise SystemExit(
            f"Telegram needs one side exactly {STICKER_SIDE_PX} px and the other at most {STICKER_SIDE_PX} px. "
            f"These files do not fit: {', '.join(wrong_size_names)}"
        )
    return [Sticker(path, STEM_TO_EMOJI.get(path.stem, FALLBACK_EMOJI)) for path in paths]


def is_valid_sticker_size(path: Path) -> bool:
    with Image.open(path) as image:
        return max(image.size) == STICKER_SIDE_PX


def read_token(token_path: Path) -> str:
    if not token_path.is_file():
        raise SystemExit(f"No bot token file at {token_path}. See the setup steps at the top of this script.")
    token = token_path.read_text().strip()
    if not token:
        raise SystemExit(f"The bot token file {token_path} is empty.")
    return token


def find_owner(bot: TelegramBot) -> Owner:
    """Use the sender of the newest private message to the bot as the set's owner."""
    updates = bot.call("getUpdates")
    senders = [
        update["message"]["from"]
        for update in updates
        if update.get("message", {}).get("chat", {}).get("type") == "private"
    ]
    if not senders:
        raise SystemExit("Found no private message to the bot. Open the bot in Telegram, press Start, and run again.")
    sender = senders[-1]
    display_name = " ".join(part for part in (sender.get("first_name"), sender.get("last_name")) if part)
    if sender.get("username"):
        display_name += f" (@{sender['username']})"
    return Owner(sender["id"], display_name)


def count_stickers_in_set(bot: TelegramBot, set_name: str) -> int | None:
    """Return the number of stickers in the set, or None when no set has this name."""
    try:
        sticker_set = bot.call("getStickerSet", {"name": set_name})
    except TelegramError as exc:
        if "STICKERSET_INVALID" in exc.description:
            return None
        raise
    return len(sticker_set["stickers"])


def print_plan(owner: Owner, set_name: str, title: str, stickers: list[Sticker], existing_count: int | None) -> None:
    print(f"Owner: {owner.display_name}, user id {owner.user_id}")
    print(f"Title: {title}")
    print(f"Link:  https://t.me/addstickers/{set_name}")
    if existing_count is None:
        first_batch_size = min(len(stickers), MAX_STICKERS_PER_CREATE)
        remaining_count = len(stickers) - first_batch_size
        print(f"Plan:  create the set with {first_batch_size} stickers, then add {remaining_count} more")
    else:
        print(f"Plan:  the set has {existing_count} stickers; add files {existing_count + 1} to {len(stickers)}")
    for position, sticker in enumerate(stickers, start=1):
        print(f"  {position:3}. {sticker.emoji}  {sticker.path.name}")
    unmapped_names = [sticker.path.name for sticker in stickers if sticker.path.stem not in STEM_TO_EMOJI]
    if unmapped_names:
        print(f"No emoji chosen for {', '.join(unmapped_names)}; using {FALLBACK_EMOJI}")


def upload_stickers(
    bot: TelegramBot,
    owner: Owner,
    set_name: str,
    title: str,
    stickers: list[Sticker],
    existing_count: int | None,
) -> None:
    uploaded_count = existing_count
    if uploaded_count is None:
        first_batch = stickers[:MAX_STICKERS_PER_CREATE]
        create_sticker_set(bot, owner, set_name, title, first_batch)
        uploaded_count = len(first_batch)
    for position, sticker in enumerate(stickers[uploaded_count:], start=uploaded_count + 1):
        print(f"  Adding {position}/{len(stickers)}: {sticker.path.name}")
        bot.call(
            "addStickerToSet",
            {"user_id": owner.user_id, "name": set_name, "sticker": json.dumps(sticker.to_input_sticker("upload"))},
            files={"upload": sticker.to_upload()},
        )


def create_sticker_set(bot: TelegramBot, owner: Owner, set_name: str, title: str, stickers: list[Sticker]) -> None:
    attach_name_to_sticker = {f"upload{index}": sticker for index, sticker in enumerate(stickers)}
    input_stickers = [sticker.to_input_sticker(name) for name, sticker in attach_name_to_sticker.items()]
    print(f"  Creating '{title}' with the first {len(stickers)} stickers")
    bot.call(
        "createNewStickerSet",
        {"user_id": owner.user_id, "name": set_name, "title": title, "stickers": json.dumps(input_stickers)},
        files={name: sticker.to_upload() for name, sticker in attach_name_to_sticker.items()},
    )


if __name__ == "__main__":
    main()
