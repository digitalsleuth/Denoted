import os
import struct
import sys

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import QGuiApplication, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer

HERE = os.path.dirname(os.path.abspath(__file__))
SVG_PATH = os.path.join(HERE, "denoted.svg")
PNG_PATH = os.path.join(HERE, "denoted.png")
ICO_PATH = os.path.join(HERE, "denoted.ico")
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
PNG_SIZE = 256


def render(renderer, size):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(p)
    p.end()
    return img


def png_bytes(img):
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(data)


def main():
    app = QGuiApplication(sys.argv)
    renderer = QSvgRenderer(SVG_PATH)
    render(renderer, PNG_SIZE).save(PNG_PATH)
    images = [png_bytes(render(renderer, s)) for s in ICO_SIZES]
    offset = 6 + 16 * len(images)
    out = bytearray(struct.pack("<HHH", 0, 1, len(images)))
    for size, data in zip(ICO_SIZES, images):
        out += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    for data in images:
        out += data
    with open(ICO_PATH, "wb") as f:
        f.write(out)
    print(f"{PNG_PATH}\n{ICO_PATH} ({len(out)} bytes, sizes {ICO_SIZES})")
    del app


if __name__ == "__main__":
    main()
