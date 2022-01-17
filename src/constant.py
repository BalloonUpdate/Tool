import sys
from src.utilities.env_util import getMetadata

version = getMetadata().get('version', 'dev')
commit = getMetadata().get('commit', 'not in git')
compile_time = getMetadata().get('compile_time', '<parser mode>')
inDev = not getattr(sys, 'frozen', False)
