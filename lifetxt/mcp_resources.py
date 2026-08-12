"""Protocol-neutral MCP resource listing and read validation."""


def resource_list(context):
    return [
        {
            "uri": "lifetxt://source/%d" % index,
            "name": path,
            "description": "life.txt input source",
            "mimeType": "text/plain",
        }
        for index, path in enumerate(context.paths)
    ]


def resource_read(context, uri, read_text):
    prefix = "lifetxt://source/"
    if not str(uri).startswith(prefix):
        raise ValueError("Unsupported resource URI: %s" % uri)
    try:
        index = int(str(uri)[len(prefix) :])
    except ValueError:
        raise ValueError("Invalid resource index in URI: %s" % uri)
    if index < 0 or index >= len(context.paths):
        raise ValueError("Resource index is out of range: %s" % uri)
    path = context.paths[index]
    return {
        "contents": [
            {
                "uri": uri,
                "mimeType": "text/plain",
                "text": read_text(path),
            }
        ]
    }
