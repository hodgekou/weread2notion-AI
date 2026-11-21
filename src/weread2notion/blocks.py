TEXT_LIMIT = 2000


def split_text(content, limit=TEXT_LIMIT):
    """Split text into pieces Notion accepts as one rich-text item each.

    Notion rejects rich-text content longer than 2000 characters. Characters
    outside the Basic Multilingual Plane (most emoji, rare CJK) are counted as
    two, so they are measured the same way here.
    """
    parts, current, size = [], [], 0
    for char in "" if content is None else str(content):
        width = 2 if ord(char) > 0xFFFF else 1
        if size + width > limit:
            parts.append("".join(current))
            current, size = [], 0
        current.append(char)
        size += width
    if current:
        parts.append("".join(current))
    return parts or [""]


def get_heading(level, content):
    if level == 1:
        heading = "heading_1"
    elif level == 2:
        heading = "heading_2"
    else:
        heading = "heading_3"
    return {
        "type": heading,
        heading: {
            "rich_text": [
                {
                    "type": "text",
                    "text": {
                        "content": content,
                    },
                }
            ],
            "color": "default",
            "is_toggleable": False,
        },
    }


def get_table_of_contents():
    """获取目录"""
    return {"type": "table_of_contents", "table_of_contents": {"color": "default"}}


def get_title(content):
    return {"title": [{"type": "text", "text": {"content": content}}]}


def get_rich_text(content):
    return {"rich_text": [{"type": "text", "text": {"content": content}}]}


def get_url(url):
    return {"url": url}


def get_file(url):
    return {"files": [{"type": "external", "name": "Cover", "external": {"url": url}}]}


def get_multi_select(names):
    return {"multi_select": [{"name": name} for name in names]}


def get_date(start):
    return {
        "date": {
            "start": start,
            "time_zone": "Asia/Shanghai",
        }
    }


def get_icon(url):
    return {"type": "external", "external": {"url": url}}


def get_select(name):
    return {"select": {"name": name}}


def get_status(name):
    return {"status": {"name": name}}


def get_number(number):
    return {"number": number}


def get_quote(content):
    return {
        "type": "quote",
        "quote": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": content},
                }
            ],
            "color": "default",
        },
    }


def get_callout(content, icon=None, children=None):
    callout = {
        # Long highlights and thoughts are split, never truncated.
        "rich_text": [
            {
                "type": "text",
                "text": {"content": part},
                "annotations": {"color": "blue"},
            }
            for part in split_text(content)
        ],
    }
    if icon:
        callout["icon"] = {"type": "emoji", "emoji": icon}
    if children:
        callout["children"] = children
    return {
        "type": "callout",
        "callout": callout,
    }
