import sys
from src.utilities.env_util import getMetadata

version = getMetadata().get('version', 'dev-version')
commit = getMetadata().get('commit', 'NotInGit')
compile_time = getMetadata().get('compile_time', '<dev-mode>')
inDev = not getattr(sys, 'frozen', False)
