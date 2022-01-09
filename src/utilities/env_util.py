import json
import sys

from src.utilities.file import File


def getMetadata():
    temp = File(getattr(sys, '_MEIPASS', ''))
    return json.loads(temp('meta.json').content)
