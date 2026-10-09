"""Offline Layer III silence frames assembled without encoders or dependencies."""


def mp3_frames(version=1, count=200, padding=False):
    # MPEG-1: 128 kbps / 44100 Hz; MPEG-2: 64 kbps / 22050 Hz;
    # MPEG-2.5: 64 kbps / 11025 Hz. Zero side information and zero main data.
    header, length = {1: (0xFFFB9064, 417), 2: (0xFFF38064, 208),
                      2.5: (0xFFE38064, 417)}[version]
    if padding:
        header |= 1 << 9
        length += 1
    return (header.to_bytes(4, "big") + bytes(length - 4)) * count


def id3v2_tag():
    payload = bytes(150)
    return b"ID3\x04\x00\x00\x00\x00\x01\x16" + payload


ID3V1 = b"TAG" + bytes(125)
