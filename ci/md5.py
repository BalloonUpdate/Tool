import sys
import hashlib

if len(sys.argv) != 2:
    print('no path inputed')
    sys.exit()

with open(sys.argv[1], 'rb') as f:
    md5obj = hashlib.sha1()
    md5obj.update(f.read())
    print(md5obj.hexdigest())