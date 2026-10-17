import re
from urllib.parse import urlsplit, urlunsplit


DETAIL_IMAGE_PATH = re.compile(r'^/uploads/products/[0-9a-f]{32}-detail\.jpg$')


def thumbnail_url(image_url):
    """Use the generated thumbnail for new uploads; preserve legacy/external URLs."""
    if not image_url:
        return image_url

    parsed = urlsplit(image_url)
    if not DETAIL_IMAGE_PATH.fullmatch(parsed.path):
        return image_url

    return urlunsplit(parsed._replace(path=parsed.path.replace('-detail.jpg', '-thumb.jpg')))
