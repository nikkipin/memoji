# memoji

Export your Memoji stickers from macOS as PNG files.

macOS keeps the Memoji stickers that it has drawn in a cache folder, `~/Library/Application Support/Animoji/Stickers/`, as 420×420 PNG images. `memoji_export.py` copies the stickers of one Memoji out of that cache, names each file after its expression (for example `thumbs_up.png`), and resizes it to 512×512.

## Requirements

- A Mac with at least one Memoji
- Python 3.10 or later
- [Pillow](https://pypi.org/project/pillow/), the Python imaging library. `requirements.txt` installs it.

## Setup

```sh
git clone https://github.com/nikkipin/memoji.git
cd memoji
python3 -m pip install -r requirements.txt
```

## 1. Fill the sticker cache

macOS draws a Memoji's stickers only when a sticker picker shows them, and it caches only the stickers that it has drawn. A new or edited Memoji starts with an empty cache. The export then fails with `Error: No avatar found matching '<id>'`, or it exports only some of the stickers.

Two screens draw two different sets of stickers. Open both screens for each Memoji that you want to export:

1. **Stickers in Messages.** In Messages, click **+** next to the text box and choose **Stickers**. Select the Memoji and scroll to the end of its stickers.
2. **Poses in System Settings.** In System Settings, click your user picture and choose **Memoji**. Select the Memoji and look through its poses. This screen draws 12 stickers that the Messages picker does not draw: grizzled, hands_on_hips, happy, head_tilt, one_raised_eyebrow, pleasant_neutral, proud, pursed_lips, surprise, tongue_out, wink and yearbook.

To check that the cache is complete, run:

```sh
python3 memoji_export.py --list
```

The script prints the ID of each Memoji and the expressions that the cache holds for it. Compare the counts of your Memoji. On macOS 27.0, the largest count seen so far is 69 expressions.

## 2. Export

```sh
python3 memoji_export.py -o ./export --avatar <id>
```

`<id>` is a Memoji ID from `--list`, for example `1A2B3C4D`. The script writes one 512×512 PNG file for each expression into `./export`.

Pass `--avatar` when the cache holds more than one Memoji. The script names each file after its expression only. Without `--avatar`, the stickers of different Memoji overwrite each other.

### Options

| Option | What it does |
|---|---|
| `-l`, `--list` | Prints the ID and expressions of each Memoji, then stops. |
| `-o`, `--output DIR` | Writes the PNG files to `DIR`. An export needs this option. |
| `--avatar ID` | Exports only the Memoji whose ID contains `ID`. The first 8 characters from `--list` are enough. |
| `-s`, `--size N` | Resizes each sticker to N×N pixels. The default is 512. Use `--size 420` to keep the original size. |
| `--mouse` | Also exports the cache files whose names start with `mouse_`. |
| `--source DIR` | Reads stickers from `DIR` instead of the default cache folder. |

## Use the stickers in WhatsApp

These notes come from tests on a Pixel 9 (Android) in November 2026, with the Sticker Maker app. Sticker Maker imports a `.wastickers` sticker pack file into WhatsApp.

- **The stickers in a `.wastickers` file must be WebP.** `memoji_export.py` writes PNG files, so convert them to WebP first. With PNG stickers, Sticker Maker refuses the file with "you need to have at least 3 stickers in your pack before you can publish". The same stickers as WebP import without an error.
- **An imported pack holds at most 30 stickers.** When a `.wastickers` file holds more, Sticker Maker imports 30 of them and drops the rest: a file of 69 stickers imported as a pack of 30. WhatsApp's help page states this limit for uploaded packs: "a pack can have up to 30 stickers" ([How to create and share custom stickers and sticker packs](https://faq.whatsapp.com/1056840314992666/?cms_platform=android)).
- **A pack that you build inside WhatsApp holds at most 60 stickers.** Tap and hold a sticker, then tap **Add to sticker pack**.

To get more than 30 stickers into one pack:

1. Trim the folder to 60 stickers or fewer.
2. Split the stickers over two import files of 30 or fewer.
3. Import both files.
4. Add their stickers to one pack that you build inside WhatsApp.

## License

MIT. See [LICENSE](LICENSE).

Memoji is a trademark of Apple Inc. This project is not affiliated with or endorsed by Apple.
