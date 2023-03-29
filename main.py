import re
import logging
import os
import argparse
from pathlib import Path

from src.extractor import PostExtractor
from src.content_exporter import ContentExporter


def export_posts(
    url: str,
    cookies: dict,
    output_path: str,
    archive_file: str,
    post_ids: list[str] = None,
):
    extractor = PostExtractor(cookies=cookies)

    exporter = ContentExporter(output_path=output_path, archive_file=archive_file)

    posts: list[dict] = list()
    if post_ids:
        logger.info(f"Extracting passed post id's")
        for post_id in post_ids:
            post_url = (
                f"https://www.youtube.com/post/{post_id}"
                if not post_id.startswith("https://")
                else post_id
            )
            post = extractor.get_individual_post(url=post_url)
            if post:
                posts.append(post)

    if url:
        logger.info(f"Extracting posts from '{url}'")
        extracted_posts = extractor.get_posts(url=url)
        extracted_posts.reverse()

        posts += extracted_posts

    exporter.export_posts(posts=posts)


def load_posts_file(file: str) -> list[str]:
    with open(file) as f:
        content = f.read()

    return content.splitlines()


def load_cookies(file: str) -> dict[str, str]:
    cookies: dict[str, str] = dict()
    with open(file) as f:
        content = f.read()

    lines = [line for line in content.splitlines() if line.startswith(".youtube.com")]

    for line in lines:
        parts = re.split("\s+", line)
        key = parts[5]
        value = ""
        if len(parts) >= 7:
            value = parts[6]
        cookies[key] = value

    return cookies


def parent_is_writable(path: str) -> bool:
    parent = Path(path).parent.absolute()

    return os.path.isdir(parent) and os.access(parent, os.W_OK)


def main():
    global logger
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s: %(message)s")
    logger = logging.getLogger(name=__name__)

    parser = argparse.ArgumentParser(
        prog="YouTube Community Posts Archiver",
        description="Exports YouTube Community Posts from a given URL or list of Post-IDs/URLs",
    )
    parser.add_argument(
        "-u",
        "--url",
        metavar="<youtube-channel-url>",
        dest="url",
        required=False,
        help="The youtube channel URL for which community posts should be downloaded",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        metavar="<output_dir>",
        dest="output_path",
        required=True,
        help="The directory to write the exported posts to",
    )
    parser.add_argument(
        "-a",
        "--archive-file",
        metavar="<archive_file>",
        dest="archive_file",
        required=False,
        help="The archive json file used to keep track of already exported posts (default: '<output-dir>/archive.json')",
    )
    parser.add_argument(
        "-c",
        "--cookie-file",
        metavar="<cookie_file>",
        dest="cookie_file",
        required=False,
        help="A optional cookies file used to export members-only content",
    )
    parser.add_argument(
        "-p",
        "--post-ids-file",
        metavar="<post-ids-file>",
        dest="posts_file",
        required=False,
        help="A optinal file containing post-id's or URLs to export",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 1.0")

    args = parser.parse_args()

    if not args.url and not args.posts_file:
        logger.error(f"At least one of '--url' or '--post-ids-file' is required")
        exit(1)

    url = args.url
    output_path = args.output_path
    archive_file = args.archive_file
    cookies_file = args.cookie_file
    posts_file = args.posts_file

    if not os.path.isdir(output_path):
        if parent_is_writable(output_path):
            os.mkdir(output_path)
        else:
            logger.error(
                f"Output dir '{output_path}' does not exist & couldn't be created"
            )
            exit(1)

    archive_file_default = os.path.join(output_path, "archive.json")
    if archive_file:
        if not os.path.isfile(archive_file):
            if not parent_is_writable(archive_file):
                logger.warning(
                    f"given archive file '{archive_file}' does not exists & could not be created. defaulting to '{archive_file_default}'"
                )
                archive_file = archive_file_default
    else:
        archive_file = archive_file_default

    if cookies_file and not os.path.isfile(cookies_file):
        logger.warning(f"given cookie file '{cookies_file}' does could not be found")
        cookies_file = ""

    if posts_file and not os.path.isfile(posts_file):
        logger.warning(f"given posts file '{posts_file}' could not be found")
        posts_file = ""

    if posts_file:
        post_ids = load_posts_file(file=posts_file)
    else:
        post_ids = None

    if cookies_file:
        cookies = load_cookies(file=cookies_file)
    else:
        cookies = {"CONSENT": "YES+"}

    export_posts(
        url=url,
        cookies=cookies,
        output_path=output_path,
        archive_file=archive_file,
        post_ids=post_ids,
    )


if __name__ == "__main__":
    main()
