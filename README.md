# webtoons-dl
Simple script to pull &amp; compile comics from Webtoons. Downloads all episodes of a comic, and compiles panels into single JPG images.

## Usage
`python3 webtoons-dl.py [comic url]`

### Flags
* `-h` or `--help` - Show help
* `--dir` - Specify output directory
* `--from` - Specify starting episode (inclusive)
* `--to` - Specify ending episode (inclusive)
* `--no-compile` - Don't compile panels into single images
* `--no-confirm` - Don't confirm before downloading or overwriting files
* `--zip` - Zip images after downloading

## Dependencies
* Python 3
* Requests
* Pillow
* BeautifulSoup4

## License
See [LICENSE](LICENSE) file.

## Disclaimer
This script is provided as-is, and while I don't believe it violates any ToS, IANAL. I take no responsibility for any consequences of using this script. Please respect the intellectual property rights of the webcomics' creators and only use this for personal use.
