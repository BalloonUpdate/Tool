import hashlib


def string_md5(text):
    sha1obj = hashlib.sha1()
    sha1obj.update(text)
    return sha1obj.hexdigest()
