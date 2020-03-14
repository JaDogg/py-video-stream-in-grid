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

ALLOWED = (".mp4", ".webm")
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
        videos = natsorted(list(self._possible()), key=lambda x: x[1])
        for path_name, full_path in videos:
            _, ext = os.path.splitext(full_path)
            mime = mimetypes.guess_type(full_path)[0]
            self._map[i] = Video(path_name, ext, mime, full_path)
            i += 1
        self._videos = self._sorted_videos()

    def _possible(self):
        for path_name, full_path in self._list_dir():
            _, ext = os.path.splitext(full_path)
            if ext.lower() not in self._allowed:
                continue
            yield path_name, full_path

    def _list_dir(self):
        for root, _, files in os.walk(self._location):
            for f in files:
                full_path = os.path.join(root, f)
                if full_path.startswith(self._location):
                    yield full_path[len(self._location) + 1 :], full_path
                else:
                    yield full_path, full_path

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
    HOST = "0.0.0.0"
    PORT = 52165
    if len(sys.argv) == 2:
        PORT = int(sys.argv[1])
    from waitress import serve

    serve(app, host=HOST, port=PORT)
