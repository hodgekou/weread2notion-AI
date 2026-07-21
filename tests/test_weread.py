from weread2notion.weread import WeReadClient


class Response:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


class Session:
    def __init__(self, pages):
        self.headers = {}
        self.pages = iter(pages)
        self.payloads = []

    def post(self, url, json, timeout):
        self.payloads.append(json)
        return Response(next(self.pages))


def test_notebook_pagination_is_flat_and_uses_last_sort():
    session = Session(
        [
            {"books": [{"sort": 20}], "hasMore": 1, "totalNoteCount": 3},
            {"books": [{"sort": 10}], "hasMore": 0, "totalNoteCount": 3},
        ]
    )
    client = WeReadClient("key", session=session)
    rows, totals = client.notebooks()
    assert len(rows) == 2
    assert totals["notes"] == 3
    assert session.payloads[1]["lastSort"] == 20
    assert "params" not in session.payloads[1]


def test_reading_days_falls_back_to_monthly_day_buckets():
    session = Session(
        [
            {"totalReadTime": 120},
            {"readTimes": {"1767196800": 120}, "totalReadTime": 120},
            {"readTimes": {"1767283200": 120}},
        ]
    )
    client = WeReadClient("key", session=session)
    days, _ = client.reading_days(2026)
    assert days == [{"timestamp": 1767283200, "duration": 120}]
    assert session.payloads[2]["mode"] == "monthly"
