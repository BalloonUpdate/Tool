import json
import sys

from src.utilities.file import File


def getMetadata():
    temp = File(getattr(sys, '_MEIPASS', ''))
    meta = temp('meta.json')
    if not meta.exists:
        return {}
    return json.loads(temp('meta.json').content)
