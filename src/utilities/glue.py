def glue(elements: list, glue=', '):
    result = ''
    length = len(elements)
    for i in range(0, length):
        result += elements[i]
        if i != length-1:
            result += glue
    return result