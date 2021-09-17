import sys
from src.utilities.env_util import getMetadata

version = getMetadata()['version']
commit = getMetadata()['commit']
compile_time = getMetadata()['compile_time']
inDev = not getattr(sys, 'frozen', False)
