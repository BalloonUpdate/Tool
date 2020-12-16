from file import File


def generateStructure(dir: File):
    structure = []
    for f in dir:
        if f.isFile:
            structure.append({
                'name': f.name,
                'length': f.length,
                'hash': f.sha1
            })
        if f.isDirectory:
            structure.append({
                'name': f.name,
                'tree': generateStructure(f)
            })
    return structure
