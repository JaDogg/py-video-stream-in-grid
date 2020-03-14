from __future__ import print_function

import logging
import mimetypes
import os
import re
import sys
from collections import namedtuple
from datetime import datetime

from flask import Flask
from flask import Response, render_template
from flask import request
from natsort import natsorted


try:
    _template_folder = os.path.join(sys._MEIPASS, "templates")
    app = Flask(__name__, template_folder=_template_folder)
    VIDEO_LOCATION = os.path.abspath(os.path.dirname(sys.executable))
except AttributeError:
    VIDEO_LOCATION = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    app = Flask(__name__)

ALLOWED = (".mp4", ".mkv")
VIDEO_ROUTE = "/video"
REGEX_RANGE = re.compile(r"bytes=(?P<start>\d+)-(?P<end>\d+)?")

Video = namedtuple("Video", ("name", "ext", "mime", "path"))


class Videos:
    def __init__(self, videos_path=VIDEO_LOCATION, allowed=ALLOWED):
        self._map = {}
        self._videos = []
        self._location = videos_path
        self._allowed = allowed
        self._map_videos()

    def _map_videos(self):
        i = 1
        videos = natsorted(list(self._possible()))
        for vid in videos:
            name, ext = os.path.splitext(vid)
            mime = mimetypes.guess_type(vid)[0]
            self._map[i] = Video(name, ext, mime, self._abs(vid))
            i += 1
        self._videos = self._sorted_videos()

    def _abs(self, path_):
        return os.path.abspath(os.path.join(self._location, path_))

    def _possible(self):
        for possible_video in os.listdir(self._location):
            if os.path.isdir(possible_video):
                continue

            name, ext = os.path.splitext(possible_video)
            if ext.lower() not in self._allowed:
                continue
            yield possible_video

    def _sorted_videos(self):
        return sorted(
            [[k, v.name, v.mime] for k, v in self._map.items()], key=lambda x: x[0]
        )

    @property
    def videos(self):
        return self._videos

    def __getitem__(self, item: int) -> Video:
        return self._map[item]


VIDEOS = Videos()

MB = 1 << 20
BUFF_SIZE = 10 * MB


@app.route("/")
def home():
    response = render_template(
        "index.html",
        time=str(datetime.now()),
        video_route=VIDEO_ROUTE,
        videos=VIDEOS.videos,
    )
    return response


def partial_response(path, start, end=None):
    file_size = os.path.getsize(path)

    # Determine (end, length)
    if end is None:
        end = start + BUFF_SIZE - 1
    end = min(end, file_size - 1)
    end = min(end, start + BUFF_SIZE - 1)
    length = end - start + 1

    # Read file
    with open(path, "rb") as fd:
        fd.seek(start)
        bytes_ = fd.read(length)
    assert len(bytes_) == length
    mime = mimetypes.guess_type(path)[0]
    response = Response(
        bytes_, 206, mimetype=mime, content_type=mime, direct_passthrough=True,
    )
    response.headers.add(
        "Content-Range", "bytes {0}-{1}/{2}".format(start, end, file_size,),
    )
    response.headers.add("Accept-Ranges", "bytes")
    return response


def get_range(request_):
    range_ = request_.headers.get("Range")
    matched = REGEX_RANGE.match(range_)
    if matched:
        start = matched.group("start")
        end = matched.group("end")
        start = int(start)
        if end is not None:
            end = int(end)
        return start, end

    return 0, None


@app.route(VIDEO_ROUTE + "/<vid>")
def video(vid):
    path = VIDEOS[int(vid)].path
    start, end = get_range(request)
    return partial_response(path, start, end)


if __name__ == "__main__":
    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    HOST = "0.0.0.0"
    PORT = 52165
    if len(sys.argv) == 2:
        PORT = int(sys.argv[1])
    from waitress import serve
    serve(app, host=HOST, port=PORT)