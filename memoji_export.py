#!/usr/bin/env python3
"""
Memoji Export Tool

Exports high-resolution Memoji sticker images from macOS cache.
macOS stores pre-rendered 420x420 PNG stickers in:
    ~/Library/Application Support/Animoji/Stickers/

This script copies them to a specified output directory with clean filenames
and upscales them to 512x512 (change this with --size).
"""

import argparse
import re
import sys
from pathlib import Path

from PIL import Image


def get_sticker_source_dir() -> Path:
    """Get the macOS Animoji stickers directory."""
    return Path.home() / "Library" / "Application Support" / "Animoji" / "Stickers"


def parse_sticker_filename(filename: str) -> dict | None:
    """
    Parse a sticker filename to extract components.

    Filename format: {UUID}_{ID}_{hash}_{expression}.png
    Example: 1A2B3C4D-5E6F-4A7B-8C9D-0E1F2A3B4C5D_AK346201000_b29f6cca6a6348f9f7e4b477da053d86_thumbs_up.png

    Also handles mouse pointer variants: mouse_{ID}_{expression}.png
    """
    if filename.startswith("mouse_"):
        # Mouse pointer format: mouse_{ID}_{expression}.png
        match = re.match(r"mouse_([^_]+)_(.+)\.png$", filename)
        if match:
            return {
                "type": "mouse",
                "avatar_id": match.group(1),
                "expression": match.group(2),
                "original": filename
            }
    else:
        # Standard sticker format: {UUID}_{ID}_{hash}_{expression}.png
        match = re.match(
            r"([A-F0-9-]+)_([^_]+)_([a-f0-9]+)_(.+)\.png$",
            filename,
            re.IGNORECASE
        )
        if match:
            return {
                "type": "sticker",
                "uuid": match.group(1),
                "avatar_id": match.group(2),
                "hash": match.group(3),
                "expression": match.group(4),
                "original": filename
            }
    return None


def get_stickers(source_dir: Path) -> list[dict]:
    """Get all stickers from the source directory."""
    stickers = []
    if not source_dir.exists():
        return stickers

    for file in source_dir.iterdir():
        if file.suffix.lower() == ".png":
            parsed = parse_sticker_filename(file.name)
            if parsed:
                parsed["path"] = file
                stickers.append(parsed)

    return stickers


def get_avatars(stickers: list[dict]) -> dict[str, list[dict]]:
    """Group stickers by avatar UUID."""
    avatars = {}
    for sticker in stickers:
        if sticker["type"] == "sticker":
            uuid = sticker["uuid"]
            if uuid not in avatars:
                avatars[uuid] = []
            avatars[uuid].append(sticker)
    return avatars


def list_stickers(stickers: list[dict]) -> None:
    """Print a summary of available stickers."""
    avatars = get_avatars(stickers)
    mouse_stickers = [s for s in stickers if s["type"] == "mouse"]

    print(f"\nFound {len(stickers)} total stickers")
    print(f"  - {len(avatars)} Memoji avatar(s)")
    print(f"  - {len(mouse_stickers)} mouse pointer variants")

    for i, (uuid, avatar_stickers) in enumerate(avatars.items(), 1):
        print(f"\nAvatar {i}: {uuid[:8]}...")
        print(f"  Expressions ({len(avatar_stickers)}):")
        expressions = sorted([s["expression"] for s in avatar_stickers])
        # Print in columns
        cols = 3
        for j in range(0, len(expressions), cols):
            row = expressions[j:j+cols]
            print("    " + "  ".join(f"{e:<35}" for e in row))

    if mouse_stickers:
        print(f"\nMouse pointer expressions ({len(mouse_stickers)}):")
        expressions = sorted([s["expression"] for s in mouse_stickers])
        for j in range(0, len(expressions), 3):
            row = expressions[j:j+3]
            print("    " + "  ".join(f"{e:<20}" for e in row))


def export_stickers(
    stickers: list[dict],
    output_dir: Path,
    size: int,
    include_mouse: bool = False,
    avatar_uuid: str | None = None
) -> int:
    """Write the selected stickers to output_dir as size x size PNGs named by expression; return the count."""
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = 0

    # Filter stickers
    to_export = []
    for sticker in stickers:
        if sticker["type"] == "mouse" and not include_mouse:
            continue
        if avatar_uuid and sticker.get("uuid") != avatar_uuid:
            continue
        to_export.append(sticker)

    for sticker in to_export:
        expression = sticker["expression"]

        # Create output filename
        if sticker["type"] == "mouse":
            output_name = f"mouse_{expression}.png"
        else:
            output_name = f"{expression}.png"

        output_path = output_dir / output_name
        source_path = sticker["path"]

        with Image.open(source_path) as img:
            if img.size != (size, size):
                img = img.resize((size, size), Image.Resampling.LANCZOS)
            img.save(output_path, "PNG")

        exported += 1
        print(f"  Exported: {output_name}")

    return exported


def main():
    parser = argparse.ArgumentParser(
        description="Export Memoji stickers from macOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --list                     List available stickers
  %(prog)s -o ./my_memojis            Export to ./my_memojis at 512x512
  %(prog)s -o ./memojis --size 420    Export at the original 420x420
  %(prog)s -o ./memojis --mouse       Include mouse pointer variants
        """
    )

    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available stickers and exit"
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output directory for exported stickers"
    )
    parser.add_argument(
        "-s", "--size",
        type=int,
        default=512,
        help="Target size in pixels (default: 512). Use 420 to keep the original 420x420."
    )
    parser.add_argument(
        "--mouse",
        action="store_true",
        help="Include mouse pointer variants"
    )
    parser.add_argument(
        "--avatar",
        type=str,
        help="Export only this avatar UUID (partial match supported)"
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Override sticker source directory"
    )

    args = parser.parse_args()

    # Get source directory
    source_dir = args.source if args.source else get_sticker_source_dir()

    if not source_dir.exists():
        print(f"Error: Sticker source directory not found: {source_dir}")
        print("Make sure you have created a Memoji on this Mac.")
        sys.exit(1)

    # Get stickers
    stickers = get_stickers(source_dir)

    if not stickers:
        print(f"No stickers found in: {source_dir}")
        sys.exit(1)

    # Handle --list
    if args.list:
        list_stickers(stickers)
        sys.exit(0)

    # Handle export
    if not args.output:
        parser.print_help()
        print("\nError: --output is required for export")
        sys.exit(1)

    # Find matching avatar
    avatars = get_avatars(stickers)
    avatar_uuid = None
    if not args.avatar and len(avatars) > 1:
        print(f"Error: Found {len(avatars)} avatars, and their stickers share file names.")
        print("Pass --avatar with one of these IDs:")
        for uuid in avatars:
            print(f"  {uuid}")
        sys.exit(1)
    if args.avatar:
        matches = [u for u in avatars.keys() if args.avatar.upper() in u.upper()]
        if len(matches) == 0:
            print(f"Error: No avatar found matching '{args.avatar}'")
            sys.exit(1)
        elif len(matches) > 1:
            print(f"Error: Multiple avatars match '{args.avatar}':")
            for m in matches:
                print(f"  {m}")
            sys.exit(1)
        avatar_uuid = matches[0]

    # Export
    print(f"Exporting stickers to: {args.output}")
    print(f"Size: {args.size}x{args.size}")

    count = export_stickers(
        stickers,
        args.output,
        size=args.size,
        include_mouse=args.mouse,
        avatar_uuid=avatar_uuid
    )

    print(f"\nExported {count} stickers to {args.output}")


if __name__ == "__main__":
    main()
