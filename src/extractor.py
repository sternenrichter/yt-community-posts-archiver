import requests
import json
import re
import time
import hashlib
import logging
from pydantic import BaseModel

logger = logging.getLogger(name=__name__)

class InitData(BaseModel):
    api_key: str = None
    request_body: dict = dict()


class PostExtractor:
    def __init__(self, cookies: dict) -> None:
        self.cookies = cookies

        cookie_header = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])

        self.headers = {
            "Cookie": cookie_header,
            "X-Goog-AuthUser": "0",
            "X-Origin": "https://www.youtube.com",
            "X-Youtube-Bootstrap-Logged-In": "true",
        }

        self.extracted_posts: set[str] = set()

    def get_continuation_token(self, continuation_container: dict) -> str | None:
        return (
            continuation_container.get("continuationItemRenderer", {})
            .get("continuationEndpoint", {})
            .get("continuationCommand", {})
            .get("token")
        )

    def _get_posts_init(self, endpoint: str, body: dict) -> list[dict] | None:
        if self.cookies.get("SAPISID"):
            self.headers[
                "Authorization"
            ] = f"SAPISIDHASH {self.calculate_sapisidhash()}"

        response = requests.post(
            url=endpoint,
            headers=self.headers,
            data=json.dumps(body),
            cookies=self.cookies,
        )

        response_content: dict = response.json()

        tabs: list[dict] = (
            response_content.get("contents", {})
            .get("twoColumnBrowseResultsRenderer", {})
            .get("tabs", [])
        )

        for tab in tabs:
            if self.is_community_tab(tab=tab):
                post_list: list[dict] = (
                    tab.get("tabRenderer", {})
                    .get("content", {})
                    .get("sectionListRenderer", {})
                    .get("contents", [dict()])[0]
                    .get("itemSectionRenderer", {})
                    .get("contents", [])
                )

                return post_list

    def _get_posts(self, endpoint: str, body: dict) -> list[dict]:
        if self.cookies.get("SAPISID"):
            self.headers[
                "Authorization"
            ] = f"SAPISIDHASH {self.calculate_sapisidhash()}"

        response = requests.post(
            url=endpoint,
            headers=self.headers,
            data=json.dumps(body),
            cookies=self.cookies,
        )

        response_content: dict = response.json()

        posts = (
            response_content.get("onResponseReceivedEndpoints", [dict()])[0]
            .get("appendContinuationItemsAction", {})
            .get("continuationItems", [])
        )

        return posts

    def get_posts(self, url: str) -> list[dict]:
        posts: list[dict] = list()

        init_data = self.extract_init_info(url=url)

        if init_data.api_key and init_data.request_body:
            endpoint = f"https://www.youtube.com/youtubei/v1/browse?key={init_data.api_key}&prettyPrint=false"

            init_posts = self._get_posts_init(
                endpoint=endpoint, body=init_data.request_body
            )

            if init_posts:
                posts += init_posts[:-1]

                token = self.get_continuation_token(
                    continuation_container=init_posts[-1]
                )

                while token:
                    init_data.request_body["continuation"] = token

                    batch_posts: list[dict] = self._get_posts(
                        endpoint=endpoint, body=init_data.request_body
                    )

                    token = ""

                    if batch_posts:
                        if batch_posts[-1].get("continuationItemRenderer"):
                            posts += batch_posts[:-1]

                            token = self.get_continuation_token(
                                continuation_container=batch_posts[-1]
                            )
                        else:
                            posts += batch_posts

            new_posts: list[dict] = list()
            for post in posts:
                post_id = (
                    post.get("backstagePostThreadRenderer", {})
                    .get("post", {})
                    .get("backstagePostRenderer", {})
                    .get("postId", "")
                )

                if post_id not in self.extracted_posts:
                    self.extracted_posts.add(post_id)
                    new_posts.append(post)

            return new_posts

    def extract_init_info(self, url: str) -> InitData:
        return_data = InitData()

        response = requests.get(url, cookies=self.cookies)

        if response.status_code == 200:
            html = response.text

            init_data_match = re.search(
                "(?<=var ytInitialData = ){.*?}(?=;<\/script>)", html
            )

            if init_data_match:
                init_data: dict = json.loads(init_data_match.group())

                tabs: list[dict] = (
                    init_data.get("contents", {})
                    .get("twoColumnBrowseResultsRenderer", {})
                    .get("tabs", [])
                )

                for tab in tabs:
                    if self.is_community_tab(tab=tab):
                        endpoint = (
                            tab.get("tabRenderer", {})
                            .get("endpoint", {})
                            .get("browseEndpoint", {})
                        )

                        return_data.request_body["browseId"] = endpoint.get(
                            "browseId", ""
                        )
                        return_data.request_body["params"] = endpoint.get("params", "")

            context_match = re.search("(?<=ytcfg\.set\()\{.*?\}(?=\);)", html)

            if context_match:
                context_dict: dict = json.loads(context_match.group())

                return_data.api_key = context_dict.get("INNERTUBE_API_KEY", "")

                return_data.request_body["context"] = context_dict.get(
                    "INNERTUBE_CONTEXT", {}
                )
                return_data.request_body["context"]["client"]["hl"] = "en"
                return_data.request_body["context"]["client"]["gl"] = "US"

        return return_data

    def get_individual_post(self, url: str) -> dict | None:
        if self.cookies.get("SAPISID"):
            self.headers[
                "Authorization"
            ] = f"SAPISIDHASH {self.calculate_sapisidhash()}"

        response = requests.get(url=url, headers=self.headers, cookies=self.cookies)

        if response.status_code == 200:
            html = response.text

            init_data_match = re.search(
                "(?<=var ytInitialData = ){.*?}(?=;<\/script>)", html
            )

            if init_data_match:
                init_data: dict = json.loads(init_data_match.group())

                tabs: list[dict] = (
                    init_data.get("contents", {})
                    .get("twoColumnBrowseResultsRenderer", {})
                    .get("tabs", [])
                )

                for tab in tabs:
                    if self.is_community_tab(tab=tab):
                        post = (
                            tab.get("tabRenderer", {})
                            .get("content", {})
                            .get("sectionListRenderer", {})
                            .get("contents", [dict()])[0]
                            .get("itemSectionRenderer", {})
                            .get("contents", [dict()])[0]
                        )

                        post_id = (
                            post.get("backstagePostThreadRenderer", {})
                            .get("post", {})
                            .get("backstagePostRenderer", {})
                            .get("postId", "")
                        )

                        if post_id and post_id not in self.extracted_posts:
                            self.extracted_posts.add(post_id)
                            return post
        else:
            logger.warning(f"error extracting '{url}' - response-code: {response.status_code}")

    def calculate_sapisidhash(self):
        origin = "https://www.youtube.com"
        timestamp = int(time.time())

        hashinput = f"{timestamp} {self.cookies.get('SAPISID','')} {origin}"

        sha1 = hashlib.sha1()

        sha1.update(hashinput.encode())

        SAPISIDHASH = f"{timestamp}_{sha1.hexdigest()}"

        return SAPISIDHASH

    def is_community_tab(self, tab: dict) -> bool:
        web_endpoint_url = tab.get("tabRenderer", {}).get("endpoint", {}).get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", "")

        return web_endpoint_url.endswith("/community")