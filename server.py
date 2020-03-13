from __future__ import print_function

import logging
import mimetypes
import os
import re
import sys
from collections import namedtuple
from datetime import datetime

from natsort import natsorted

from flask import Flask
from flask import Response, render_template
from flask import request

LOG = logging.getLogger(__name__)

if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    app = Flask(__name__, template_folder=template_folder)
else:
    app = Flask(__name__)

ALLOWED = {".mp4", ".mkv"}
VIDEO_LOCATION = r"D:\Downloads"
VIDEO_ROUTE = "/video"

Video = namedtuple("Video", ("name", "ext", "mime", "path"))


class Videos:
    def __init__(self):
        self._map = {}
        i = 1

        videos = natsorted(list(self._possible()))

        for vid in videos:
            name, ext = os.path.splitext(vid)
            mime = mimetypes.guess_type(vid)[0]
            self._map[i] = Video(name, ext, mime, self._abs(vid))
            i += 1

        self._videos = self._videos()

    def _abs(self, path_):
        return os.path.abspath(os.path.join(VIDEO_LOCATION, path_))

    def _possible(self):
        for possible_video in os.listdir(VIDEO_LOCATION):
            if os.path.isdir(possible_video):
                continue

            name, ext = os.path.splitext(possible_video)
            if ext.lower() not in ALLOWED:
                continue
            yield possible_video

    def _videos(self):
        return sorted([[k, v.name, v.mime] for k, v in self._map.items()], key=lambda x: x[0])

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
    LOG.info("Rendering home page")
    response = render_template(
        "index.html", time=str(datetime.now()),
        video_route=VIDEO_ROUTE,
        videos=VIDEOS.videos
    )
    return response


def partial_response(path, start, end=None):
    LOG.info("Requested: %s, %s", start, end)
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
        bytes = fd.read(length)
    assert len(bytes) == length
    mime = mimetypes.guess_type(path)[0]
    LOG.info("File mime: %s", mime)
    response = Response(
        bytes, 206, mimetype=mime, content_type=mime, direct_passthrough=True,
    )
    response.headers.add(
        "Content-Range", "bytes {0}-{1}/{2}".format(start, end, file_size, ),
    )
    response.headers.add("Accept-Ranges", "bytes")
    LOG.info("Response: %s", response)
    LOG.info("Response: %s", response.headers)
    return response


def get_range(request_):
    range_ = request_.headers.get("Range")
    LOG.info("Requested: %s", range_)
    m = re.match("bytes=(?P<start>\d+)-(?P<end>\d+)?", range_)
    if m:
        start = m.group("start")
        end = m.group("end")
        start = int(start)
        if end is not None:
            end = int(end)
        return start, end
    else:
        return 0, None


@app.route(VIDEO_ROUTE + "/<vid>")
def video(vid):
    path = VIDEOS[int(vid)].path
    start, end = get_range(request)
    return partial_response(path, start, end)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    HOST = "0.0.0.0"
    # http_server = HTTPServer(WSGIContainer(app))
    # http_server.bind(8080)
    # http_server.start(1)
    # IOLoop.instance().start()

    # Standalone
    app.run(host=HOST, port=8080, debug=False, threaded=False)
