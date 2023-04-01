import json
import os
import logging
import urllib.parse
import requests
from string import Template
from pydantic import BaseModel
from threading import Lock


class PollOption(BaseModel):
    votes: str = "0"
    percentage: str = "0%"

class PostShare(BaseModel):
    share_author: str = "N/A"
    share_text: str = ""
    share_time: str = ""
    share_post_id: str = ""


class PostContent(BaseModel):
    video_thumbnail_url: str = None
    video_url: str = None
    video_title: str = None
    video_published_time: str = None
    video_members_only: bool = False
    members_only: bool = False
    author: str = ""
    post_text: str = ""
    post_published_time: str = ""
    post_id: str = ""
    like_count: str = "0"
    attached_images: list[str] = list()
    poll: dict[str, PollOption] = dict()
    share: PostShare = None


logger = logging.getLogger(name=__name__)

post_template = Template(
    """$author - $time$members_only

$content

$attached_content

$likes Likes
"""
)

share_post_template = Template(
    """$author - $time

$content

---
Original Post:

$originalpost
"""
)


class ContentExporter:
    def __init__(self, output_path: str, archive_file: str) -> None:
        self.output_path = output_path
        self.archive_file = archive_file
        self.file_lock = Lock()

        self.state: dict[str, str] = self.load_archive_file()

    def load_archive_file(self) -> dict[str, str]:
        self.file_lock.acquire()
        try:
            if os.path.isfile(self.archive_file):
                with open(self.archive_file) as f:
                    state = json.load(f)
            else:
                state = dict()
        except Exception as error:
            logger.error(f"Archive file could not be loaded: '{error}'")
            exit(1)
        finally:
            self.file_lock.release()

        return state

    def write_archive_file(self) -> None:
        self.file_lock.acquire()
        try:
            with open(self.archive_file, "w") as f:
                json.dump(self.state, f, indent=4)
        except Exception as error:
            logger.error(f"{error}")
        finally:
            self.file_lock.release()

    def download_image(self, url: str, file_path: str, filename: str):
        if url:
            response = requests.get(url, stream=True)

            if response.status_code == 200:
                file = os.path.join(file_path, filename)

                with open(file, "wb") as f:
                    for chunk in response:
                        f.write(chunk)
            else:
                logger.warning(f"Image could not be downloaded from: {url}")

    def download_images(self, urls: set[str], file_path: str):
        for url in urls:
            if url:
                parsed_url = urllib.parse.urlparse(url)

                filename = f"{parsed_url.path.strip('/')}.png"

                self.download_image(url=url, file_path=file_path, filename=filename)

    def _get_image_urls(self, container: dict) -> list[str]:
        urls = [
            image.get("url", "")
            for image in container.get("backstageImageRenderer", {})
            .get("image", {})
            .get("thumbnails", [dict()])
        ]

        return urls
    
    def _get_post_text(self, text_runs: list[dict]) -> str:
        post_text_parts: list[str] = list()

        for text_run in text_runs:
            text = text_run.get("text", "")
            navigation_link = (
                text_run.get("navigationEndpoint", {})
                .get("commandMetadata", {})
                .get("webCommandMetadata", {})
                .get("url", "")
            )

            if navigation_link.startswith("/"):
                navigation_link = f"https://youtube.com{navigation_link}"

            if navigation_link and not text == navigation_link:
                text = f"{text} ({navigation_link})"

            post_text_parts.append(text)

        return "".join(post_text_parts)
    
    def _extract_post_share_detais(self, post: dict) -> PostShare:
        post_share = PostShare()

        post_share.share_post_id = post.get("postId", "id_not_found")
        post_share.share_author = post.get("displayName", {}).get("runs", [dict()])[0].get("text", "N/A")
        post_share.share_text = self._get_post_text(text_runs=post.get("content", {}).get("runs", []))
        post_share.share_time = post.get("publishedTimeText", {}).get("runs", [dict()])[0].get("text", "")

        return post_share


    def _extract_post_details(self, post: dict) -> PostContent:
        post_content = PostContent()

        # General Post content
        post_content.post_id = post.get("postId", "no_id_found")
        post_content.author = (
            post.get("authorText", {}).get("runs", [dict()])[0].get("text", "")
        )
        post_content.post_published_time = (
            post.get("publishedTimeText", {}).get("runs", [dict()])[0].get("text", "")
        )
        post_content.members_only = "sponsorsOnlyBadge" in post.keys()
        post_content.like_count = post.get("voteCount", {}).get("simpleText")

        # Post Text
        text_runs: list[dict] = post.get("contentText", {}).get("runs", [])

        post_content.post_text = self._get_post_text(text_runs=text_runs)

        # Post Images
        image_urls = []

        image_urls += self._get_image_urls(
            container=post.get("backstageAttachment", {})
        )

        multi_images: list[dict] = (
            post.get("backstageAttachment", {})
            .get("postMultiImageRenderer", {})
            .get("images", [])
        )

        for image in multi_images:
            image_urls += self._get_image_urls(container=image)

        post_content.attached_images = image_urls

        # Polls
        poll_choices: list[dict] = (
            post.get("backstageAttachment", {})
            .get("pollRenderer", {})
            .get("choices", [])
        )

        for choice in poll_choices:
            choice_text = (
                choice.get("text", {}).get("runs", [dict()])[0].get("text", "Null")
            )

            percentage_voted = choice.get("votePercentage", {}).get("simpleText")
            percentage_not_voted = choice.get("votePercentageIfSelected", {}).get(
                "simpleText"
            )

            percentage = percentage_voted if percentage_voted else percentage_not_voted

            post_content.poll[choice_text] = PollOption(
                votes=choice.get("numVotes", ""),
                percentage=percentage if percentage else "",
            )

        # Video data
        video_dict = post.get("backstageAttachment", {}).get("videoRenderer", {})

        post_content.video_title = (
            video_dict.get("title", {}).get("runs", [dict()])[0].get("text", "")
        )
        post_content.video_thumbnail_url = (
            video_dict.get("thumbnail", {})
            .get("thumbnails", [dict()])[-1]
            .get("url", "")
            .split("?")[0]
        )
        post_content.video_published_time = video_dict.get("publishedTimeText", {}).get(
            "simpleText", ""
        )

        video_link = (
            video_dict.get("navigationEndpoint", {})
            .get("commandMetadata", {})
            .get("webCommandMetadata", {})
            .get("url", "")
        )

        if video_link.startswith("/"):
            video_link = f"https://www.youtube.com{video_link}"

        post_content.video_url = video_link

        video_badges: list[dict] = video_dict.get("badges", [])

        for badge in video_badges:
            badge_label = badge.get("metadataBadgeRenderer", {}).get("label", "")
            if badge_label == "Members only":
                post_content.video_members_only = True
                break

        return post_content

    def deduplicate_images(self, images: list[str]) -> set[str]:
        deduplicated_images: set[str] = set()

        for image in images:
            if image:
                url = f"{image.split('=s')[0]}=s0"
                deduplicated_images.add(url)

        return deduplicated_images

    def export_posts(self, posts: list[dict]):
        previous_index_offset = (
            max([int(key) for key in self.state.keys()]) if self.state else 0
        )

        index = 0

        for post_dict in posts:
            index += 1
            logger.info(f"Exporting post {index}/{len(posts)}")

            post_common_root = post_dict.get("backstagePostThreadRenderer", {}).get("post", {})

            share = None

            if "sharedPostRenderer" in post_common_root.keys():
                post = post_common_root.get("sharedPostRenderer", {}).get("originalPost", {}).get("backstagePostRenderer", {})

                share = self._extract_post_share_detais(post=post_common_root.get("sharedPostRenderer", {}))
            else:
                post = (
                    post_dict.get("backstagePostThreadRenderer", {})
                    .get("post", {})
                    .get("backstagePostRenderer", {})
                )

            post_content = self._extract_post_details(post=post)
            
            if share:
                post_content.share = share

            if post_content.post_id not in self.state.values():
                post_num = str(index + previous_index_offset).zfill(4)

                members_only_tag = (
                    " (Members only)" if post_content.members_only else ""
                )
                members_only_tag_post = (
                    " - Members only" if post_content.members_only else ""
                )

                post_path_id = post_content.post_id
                if post_content.share and post_content.share.share_post_id:
                    post_path_id = post_content.share.share_post_id

                post_path = os.path.join(
                    self.output_path,
                    f"[{post_num}]{members_only_tag} {post_path_id}",
                )

                if not os.path.isdir(post_path):
                    os.mkdir(post_path)

                images = self.deduplicate_images(images=post_content.attached_images)

                self.download_images(urls=images, file_path=post_path)
                self.download_image(
                    url=post_content.video_thumbnail_url,
                    file_path=post_path,
                    filename="video_thumbnail.jpg",
                )

                linked_video = ""
                if post_content.video_url:
                    member_only_video = (
                        " (Members only)" if post_content.video_members_only else ""
                    )

                    linked_video = f"Linked Video:\n{post_content.video_title}{member_only_video}\n{post_content.video_published_time}\n{post_content.video_url}"

                image_links = ""
                if images:
                    links = "\n".join(images)
                    image_links = f"Images:\n{links}"

                poll = ""
                if post_content.poll:
                    option_lines = list()
                    for option, results in post_content.poll.items():
                        votes = f" - {results.votes}" if results.votes else ""
                        percentage = (
                            f" - {results.percentage}" if results.percentage else ""
                        )

                        option_lines.append(f"[{option}]{votes}{percentage}")

                    options = "\n".join(option_lines)
                    poll = f"Poll:\n{options}"

                attached_content = "\n\n".join(
                    [item for item in [linked_video, image_links, poll] if item]
                )

                post_output = post_template.substitute(
                    author=post_content.author,
                    time=post_content.post_published_time,
                    members_only=members_only_tag_post,
                    content=post_content.post_text,
                    attached_content=attached_content,
                    likes=post_content.like_count,
                )

                if post_content.share:
                    post_output = share_post_template.substitute(
                        author=post_content.share.share_author,
                        time=post_content.share.share_time,
                        content=post_content.share.share_text,
                        originalpost=post_output
                    )
                
                post_output = post_output.encode("utf-8")

                with open(os.path.join(post_path, "post.txt"), "wb") as f:
                    f.write(post_output)

                with open(os.path.join(post_path, "post.json"), "w") as f:
                    json.dump(post, f, indent=4)

                self.state[post_num] = post_content.post_id
                self.write_archive_file()

            else:
                logger.info(
                    f"Skipping post '{post_content.post_id}' - already exported"
                )
