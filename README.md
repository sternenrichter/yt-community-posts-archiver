# YouTube Community Posts Archiver
A small tool to download the content of a YouTube Channels Community Posts

The tool will fetch all posts it can find* and download their attached content (i.e. images/video-thumbnails). The printable content of a post is written to a `post.txt` file. `post.json` contains the raw json data of the post.

*_YouTube's API appears to limit the maximum number of posts that can be retrieved to the last 400. See [Supplying Post-IDs / -URL's](#supplying-post-ids---urls) below for a possible workaround._

The posts & content will be written in a structure like this:
```
- <output-dir>
    - [0001] <post_id>
        - post.json
        - post.txt
        - thumbnail.jpg
        - <attached_image_id>.png
    - [0002] (Members only) <post_id>
    - [0003] <post_id>
    - ...
```

The tool will try to store the posts in chronologically accending order, this is however not guaranteed. E.g. if an older post that could previously not be downloaded is available on a re-run, it would be written with the next available directory prefix.

## Usage

It should generally be safe to re-run the tool. Only content of posts that have not already been exported will be written.

**Example:**
```
main.py -o <output_dir> -u <youtube_channel_url>
```

**Arguments:**

|Argument|Required|Description|
|:-|:-|:-|
|`-u`/`--url`|No*|The URL of the YouTube channel to download community posts from|
|`-o`/`--output-dir`|Yes|Directory to write the exported content to|
|`-a`/`--archive-file`|No|The json file used to keep track of already downloaded posts|
|`-c`/`--cookie-file`|No|A optional cookie file used to download Members-only content|
|`-p`/`--post-ids-file`|No*|A optional file containing post-id's/-urls to download|

*At least one of `--url` or `--post-ids-file` is required

### Cookie File
In order to download posts which are only available to channel members, you need to supply a Netscape formatted cookies file to the tool.

Easy ways to generate such a file are e.g. the Firefox Add-on [cookies.txt](https://github.com/hrdl-github/cookies-txt) or [yt-dlp's](https://github.com/yt-dlp/yt-dlp) `--cookies-from-browser` argument.

### Supplying Post-IDs / -URL's
You can optionally supply the tool with a list of Post-IDs/-Urls to download.  
This can be useful as the YouTube's API (randomly?) limits the maximum amount of posts that can be loaded normally to 400. Therefore if there are more than 400 posts in the community tab of a channel older posts may not be able to be loaded.  
If you however already have a list of those older posts IDs / Urls you can download them via this.

The file should contain one post ID or Url per line. E.g.:
```
<post_id>
<post_id>
<post_id>
<post_id>
https://www.youtube.com/post/<post_id>
https://www.youtube.com/post/<post_id>
https://www.youtube.com/post/<post_id>
```
