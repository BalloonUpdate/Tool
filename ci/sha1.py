import sys
import hashlib

if len(sys.argv) != 2:
    print('no path inputed')
    sys.exit()

with open(sys.argv[1], 'rb') as f:
    sha1obj = hashlib.md5()
    sha1obj.update(f.read())
    print(sha1obj.hexdigest())