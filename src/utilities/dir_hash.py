from src.utilities.file import File


def dir_hash(dir: File):
    structure = []
    for f in dir:
        if f.isFile:
            structure.append({
                'name': f.name,
                'length': f.length,
                'hash': f.sha1,
                'modified': f.modifiedTime
            })
        if f.isDirectory:
            structure.append({
                'name': f.name,
                'children': dir_hash(f)
            })
    return structure
