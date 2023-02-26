# Simple script to pull specified webtoons from webtoons.com
# TODO: Better error handling, batch downloading, filename templating

import requests
from bs4 import BeautifulSoup
import argparse
from PIL import Image
from io import BytesIO
import os
import re
import sys
import zipfile
from multiprocessing import Pool

# Default download dir is '~/webtoons-dl'
download_dir = os.path.expanduser('~/webtoons-dl')
comic_title = None
no_confirm = False
no_compile = False


def find_episode_urls(url, start=None, end=None):
    global download_dir
    global comic_title

    r = requests.get(url)
    if r.status_code != 200:
        r.raise_for_status()

    soup = BeautifulSoup(r.text, 'html.parser')

    _comic_title = soup.find('h1', class_='subj').text
    _comic_title = _comic_title.lower().replace(' ', '-')

    comic_title = _comic_title

    if comic_title is None:
        print('Error: Could not find comic title')
        return

    download_dir = os.path.join(download_dir, comic_title)

    pagination = soup.find('div', class_='paginate')
    page_links = pagination.find_all('a')

    data = []
    filter = []
    for page in range(len(page_links), 0, -1):
        print(f'Getting episode list for page {page}...', end='\r')

        url = page_links[page - 1]['href']
        if url == '#':
            url = r.url
        else:
            url = 'https://www.webtoons.com' + url
        episodes = get_episode_list(url)
        data.extend(episodes)

    if start is not None or end is not None:
        filter = [e for e in data if start <= int(e[0]) <= end]
    else:
        filter = data

    return [filter, data]


def get_episode_list(url):
    # Get list of episode urls from a given url (will be 'a' tags
    # within 'li' tags with id 'episode_1', etc.)
    r = requests.get(url)
    if r.status_code != 200:
        r.raise_for_status()

    soup = BeautifulSoup(r.text, 'html.parser')

    episodes = soup.find_all('li', id=lambda x: x and x.startswith('episode_'))

    data = []
    for episode in episodes[::-1]:
        e_id = episode['id'].split('_')[1]
        e_href = episode.find('a')['href']
        e_name = episode.find('a').find('span', class_='subj').text
        data.append((e_id, e_name, e_href))

    return data


def get_episode_images(url):
    global no_compile

    # Download all images for given episode URL
    print(f'Fetching images from {url}...')

    r = requests.get(url)
    if r.status_code != 200:
        r.raise_for_status()

    soup = BeautifulSoup(r.text, 'html.parser')
    images = soup.find_all('img', class_='_images')

    data = []
    for image in images[::-1]:
        src = image.get('data-url')

        r = requests.get(src, headers={'referer': 'https://www.webtoons.com'})
        if r.status_code != 200:
            r.raise_for_status()

        pil_image = Image.open(BytesIO(r.content)).convert('RGB')
        data.append(pil_image)

    return data if no_compile else stitch_images(data)


def batch_images(episodes, max_pool_size):
    pool = Pool(processes=min(len(episodes), max_pool_size))
    results = pool.map(get_episode_images, [e[2] for e in episodes])
    pool.close()
    pool.join()
    images = []
    for result in results:
        images.append(result)
    return images


def download_episodes(episodes):
    global download_dir
    global comic_title
    global no_confirm

    _episodes = episodes[1]
    _filter = episodes[0]

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)
    elif not os.path.isdir(download_dir):
        print('Error: Invalid download directory')
        return

    dl_msg = ''
    if len(_filter) != len(_episodes):
        dl_msg = f"""Ready to download {len(_filter)} episodes
                     (out of {len(_episodes)}) to \"{download_dir}\""""
    else:
        dl_msg = f'Ready to download {len(_filter)} episodes to {download_dir}'
    print(re.sub(r'\s+', ' ', dl_msg))
    if not no_confirm:
        print('Press enter to continue...')
        input()

    max_batch_size = min(8, int(os.cpu_count() / 2))

    try:
        for i in range(0, len(_filter), max_batch_size):
            batch = _filter[i:i + max_batch_size]
            images = batch_images(batch, max_batch_size)

            for j, image in enumerate(images):
                # If no_compile is True, 'image' will be a list of individual
                # panels. Otherwise, it will be a single stitched image
                if no_compile:
                    for k, panel in enumerate(image[::-1]):
                        clean_name = re.sub(r'\s+', ' ', batch[j][1].strip())
                        clean_name = re.sub(
                            r'[^a-zA-Z0-9\s\-\_\.\(\)\#]+', '', clean_name
                        )

                        episode_dir = os.path.join(
                            download_dir, f'{batch[j][0]}. {clean_name}'
                        )
                        if not os.path.exists(episode_dir):
                            os.makedirs(episode_dir)

                        filename = os.path.join(
                            episode_dir, f'{k + 1}.jpg'
                        )

                        if not confirm_overwrite(filename):
                            continue

                        panel.save(filename, 'JPEG')
                        print(f'Saved "{filename}"')
                else:
                    clean_name = re.sub(r'\s+', ' ', batch[j][1].strip())
                    clean_name = re.sub(
                        r'[^a-zA-Z0-9\s\-\_\.\(\)\#]+', '', clean_name
                    )

                    filename = os.path.join(
                        download_dir, f'{batch[j][0]}. {clean_name}.jpg'
                    )

                    if not confirm_overwrite(filename):
                        continue

                    image.save(filename, 'JPEG')
                    print(f'Saved "{filename}"')

    except Exception as e:
        print('Error: Error downloading images')
        print(e)
        return


def confirm_overwrite(filename):
    global no_confirm

    if os.path.exists(filename) and not no_confirm:
        print(f'\nFile "{filename}" already exists')
        print('Overwrite? (Y/n)', end=' ')
        overwrite = input()
        if overwrite != '' and overwrite.lower() != 'y':
            print('Skipping...')
            return False
        else:
            print('\033[F\033[K\033[F\033[K', end='\r')

    return True


def stitch_images(images):
    width = max([image.width for image in images])
    height = sum([image.height for image in images])

    stitched_image = Image.new('RGB', (width, height))

    y_offset = 0
    for pil_image in images[::-1]:
        stitched_image.paste(pil_image, (0, y_offset))
        y_offset += pil_image.height

    return stitched_image


def zip_images():
    global download_dir

    files = os.listdir(download_dir)

    zip_path = os.path.join(download_dir, 'images.zip')
    zip_file = zipfile.ZipFile(zip_path, 'w')

    for file in files:
        zip_file.write(os.path.join(download_dir, file), file)
        os.remove(os.path.join(download_dir, file))

    zip_file.close()
    print(f'Zipped images to {zip_path}')


def main():
    global download_dir
    global no_confirm
    global no_compile

    parser = argparse.ArgumentParser()
    parser.add_argument('--url', help='URL of webtoon to download')
    parser.add_argument('url', nargs='?', help='URL of webtoon to download')
    parser.add_argument('--dir', help='Directory to save images to')
    parser.add_argument(
        '--zip',
        help='Zip images into single file when done',
        action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        '--no-confirm',
        help='Skip confirmation prompts',
        action=argparse.BooleanOptionalAction
    )
    parser.add_argument(
        '--from',
        dest='_from',
        help='Episode to start downloading from (inclusive)'
    )
    parser.add_argument(
        '--to', help='Episode to stop downloading at (inclusive)'
    )
    parser.add_argument(
        '--no-compile',
        help='Do not compile images into a single image',
        action=argparse.BooleanOptionalAction
    )
    args = parser.parse_args()

    url = args.url
    dir = args.dir
    no_confirm = None if args.no_confirm is None else True
    no_compile = None if args.no_compile is None else True

    _from = None if args._from is None else int(args._from)
    to = None if args.to is None else int(args.to)

    if dir is None:
        print(f'No directory provided, defaulting to "{download_dir}"...')
    else:
        download_dir = dir

    valid_url = re.compile(r"""https?:\/\/(?:www\.)?webtoons\.com\/
                               [a-zA-Z]{2}\/.*?\/.*?\/list\?
                               (?:title_no|.*?&title_no)=\d+.*""", re.X)

    if not re.match(valid_url, url):
        print('Error: Invalid URL provided - URL should be of the form:')
        print(
            'https://www.webtoons.com/en/genre/comic-title/list?title_no=0000'
        )
        return

    try:
        episodes = find_episode_urls(url, start=_from, end=to)
    except Exception as e:
        print(f'Error: Uncaught error: {e}')
        return

    try:
        result = download_episodes(episodes)
    except Exception as e:
        print(f'Error: Uncaught error: {e}')
        return

    if result and args.zip:
        print('Zipping images...')
        zip_images()

    print('\nDone!')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\r', end='')
        print('Exiting...')
        sys.exit(0)
