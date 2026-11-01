import json
import pytest
from app.importers.splitwise_csv import parse_csv
from app.importers.splitwise_json import parse_json
from test_api import group

CSV = b"Date,Description,Category,Cost,Currency,Alex,Laura\n2025-01-01,Cena,Food,30.00,EUR,15.00,-15.00\n2025-01-02,Payment,Payment,5.00,EUR,-5.00,5.00\n"


def test_csv_legacy_and_payment():
    data = parse_csv(CSV, "Casa")
    assert not data["errors"]
    assert data["people"] == ["Alex", "Laura"]
    assert data["records"][0]["kind"] == "LEGACY"
    assert data["records"][0]["deltas"] == {"Alex": 1500, "Laura": -1500}
    assert data["records"][1]["kind"] == "SETTLEMENT"


def test_json_native_and_multi_payer():
    expense = {
        "id": 99,
        "description": "Dinner",
        "cost": "30.00",
        "currency_code": "EUR",
        "date": "2025-01-01T00:00:00Z",
        "group_id": 1,
        "users": [
            {"user": {"id": 1, "first_name": "Alex"}, "paid_share": "30", "owed_share": "15"},
            {"user": {"id": 2, "first_name": "Laura"}, "paid_share": "0", "owed_share": "15"},
        ],
    }
    data = parse_json(
        json.dumps({"groups": [{"id": 1, "name": "Casa"}], "expenses": [expense]}).encode()
    )
    assert not data["errors"]
    assert data["records"][0]["kind"] == "EXPENSE"
    expense["users"][0]["paid_share"] = "20"
    expense["users"][1]["paid_share"] = "10"
    data = parse_json(json.dumps({"expenses": [expense]}).encode())
    assert data["records"][0]["kind"] == "LEGACY"


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"unexpected,header\nx,y",
        b"Date,Description,Cost,Currency,A,B\n2025-01-01,x,10,EUR,2,-1",
    ],
)
def test_bad_csv(content):
    d = parse_csv(content, "Casa")
    assert d["errors"]


def test_import_mapping_commit_duplicate_rollback(client):
    c = client
    gid = group(c)
    r = c.post(
        "/api/imports/splitwise/analyze", files={"file": ("../../Casa.csv", CSV, "text/csv")}
    )
    assert r.status_code == 200, r.text
    batch = r.json()
    bid = batch["id"]
    r = c.post(
        f"/api/imports/splitwise/{bid}/mapping",
        json={"users": {"Alex": 1, "Laura": 2}, "groups": {batch["groups"][0]: gid}},
    )
    assert r.status_code == 200, r.text
    r = c.get(f"/api/imports/splitwise/{bid}/preview")
    assert not r.json()["errors"], r.text
    r = c.post(f"/api/imports/splitwise/{bid}/commit")
    assert r.status_code == 200, r.text
    assert r.json()["records_imported"] == 2
    balances = c.get(f"/api/groups/{gid}/balances").json()
    assert next(x for x in balances if x["user_id"] == 1)["balance_cents"] == 1000
    r = c.post("/api/imports/splitwise/analyze", files={"file": ("other.csv", CSV, "text/csv")})
    assert r.status_code == 409
    assert c.delete(f"/api/imports/{bid}").status_code == 422
    assert c.delete(f"/api/imports/{bid}?confirm=true").status_code == 200
    assert all(x["balance_cents"] == 0 for x in c.get(f"/api/groups/{gid}/balances").json())
    assert c.get("/api/users/1").status_code == 200


def test_import_new_user_group_and_foreign_currency(client):
    c = client
    content = b"Date,Description,Cost,Currency,Alex,New\n01/02/2025,Trip,10.00,USD,5,-5\n"
    b = c.post("/api/imports/splitwise/analyze", files={"file": ("Trip.csv", content)}).json()
    bid = b["id"]
    r = c.post(
        f"/api/imports/splitwise/{bid}/mapping",
        json={
            "users": {
                "Alex": 1,
                "New": {"username": "newuser", "display_name": "New", "password": "newpassword123"},
            },
            "groups": {b["groups"][0]: {"name": "Trip"}},
        },
    )
    assert r.status_code == 200, r.text
    assert not c.get(f"/api/imports/splitwise/{bid}/preview").json()["errors"]
    assert c.post(f"/api/imports/splitwise/{bid}/commit").status_code == 200
    assert any(g["name"] == "Trip" for g in c.get("/api/groups").json())


def test_ignore_nonzero_and_dryrun_no_writes(client):
    c = client
    gid = group(c)
    b = c.post("/api/imports/splitwise/analyze", files={"file": ("Casa.csv", CSV)}).json()
    bid = b["id"]
    r = c.post(
        f"/api/imports/splitwise/{bid}/mapping",
        json={"users": {"Alex": 1, "Laura": None}, "groups": {b["groups"][0]: gid}},
    )
    assert r.status_code == 200
    assert c.get(f"/api/imports/splitwise/{bid}/preview").json()["errors"]
    assert c.post(f"/api/imports/splitwise/{bid}/commit").status_code == 422
    assert all(x["balance_cents"] == 0 for x in c.get(f"/api/groups/{gid}/balances").json())


def test_duplicate_external_record_and_manual_preserved(client):
    c = client
    gid = group(c)

    def blob(note):
        return json.dumps(
            {
                "expenses": [
                    {
                        "id": 909,
                        "description": "Coffee",
                        "cost": "10",
                        "date": "2025-01-01",
                        "currency_code": "EUR",
                        "users": [
                            {
                                "user": {"id": 1, "first_name": "Alex"},
                                "paid_share": "10",
                                "owed_share": "5",
                            },
                            {
                                "user": {"id": 2, "first_name": "Laura"},
                                "paid_share": "0",
                                "owed_share": "5",
                            },
                        ],
                    }
                ],
                "note": note,
            }
        ).encode()

    batches = []
    for note in ["first", "second"]:
        b = c.post(
            "/api/imports/splitwise/analyze", files={"file": ("export.json", blob(note))}
        ).json()
        bid = b["id"]
        batches.append(bid)
        users = {p: 1 if p.startswith("Alex") else 2 for p in b["people"]}
        assert (
            c.post(
                f"/api/imports/splitwise/{bid}/mapping",
                json={"users": users, "groups": {b["groups"][0]: gid}},
            ).status_code
            == 200
        )
        p = c.get(f"/api/imports/splitwise/{bid}/preview").json()
        assert p["duplicates"] == (1 if note == "second" else 0)
        assert c.post(f"/api/imports/splitwise/{bid}/commit").status_code == 200
    from test_api import expense

    eid = c.post("/api/expenses", json=expense(gid)).json()["id"]
    assert c.delete(f"/api/imports/{batches[0]}?confirm=true").status_code == 200
    assert c.get(f"/api/expenses/{eid}").status_code == 200
    assert len(c.get("/api/expenses").json()) == 1


def test_import_atomic_failure(client, monkeypatch):
    from app.services import import_service

    c = client
    gid = group(c)
    b = c.post("/api/imports/splitwise/analyze", files={"file": ("Casa.csv", CSV)}).json()
    bid = b["id"]
    c.post(
        f"/api/imports/splitwise/{bid}/mapping",
        json={"users": {"Alex": 1, "Laura": 2}, "groups": {b["groups"][0]: gid}},
    )
    c.get(f"/api/imports/splitwise/{bid}/preview")
    original = import_service.record_keys
    calls = 0

    def crash(batch):
        nonlocal calls
        calls += 1
        for i, pair in enumerate(original(batch)):
            if calls == 2 and i == 1:
                raise ValueError("Simulated transaction failure")
            yield pair

    monkeypatch.setattr(import_service, "record_keys", crash)
    assert c.post(f"/api/imports/splitwise/{bid}/commit").status_code == 422
    assert c.get("/api/legacy").json() == []
    assert all(x["balance_cents"] == 0 for x in c.get(f"/api/groups/{gid}/balances").json())
    assert c.get(f"/api/imports/{bid}").json()["status"] == "MAPPED"


def test_csv_semicolon_comma_negative_cp1252():
    d = parse_csv(
        "Data;Descrizione;Costo;Valuta;André;Laura\n02/01/2025;Rimborso;-12,50;EUR;-6,25;6,25\n".encode(
            "cp1252"
        ),
        "Casa",
    )
    assert not d["errors"]
    assert d["records"][0]["amount_cents"] == -1250
    assert d["records"][0]["date"] == "2025-01-02"


def test_external_id_dedup_across_formats():
    from app.services.import_service import fingerprint

    record = {"external_id": "901"}
    assert fingerprint(record, "CSV", 1) == fingerprint(record, "JSON", 1)


def test_json_distinct_same_named_groups():
    def expense(gid, eid):
        return {
            "id": eid,
            "group_id": gid,
            "description": "Cena",
            "cost": "10",
            "currency_code": "EUR",
            "date": "2025-01-01",
            "users": [
                {"user": {"id": 1, "first_name": "A"}, "paid_share": "10", "owed_share": "5"},
                {"user": {"id": 2, "first_name": "B"}, "paid_share": "0", "owed_share": "5"},
            ],
        }

    data = parse_json(
        json.dumps(
            {
                "groups": [{"id": 1, "name": "Casa"}, {"id": 2, "name": "Casa"}],
                "expenses": [expense(1, 90), expense(2, 91)],
            }
        ).encode()
    )
    assert len(data["groups"]) == 2


def test_import_metadata_private_to_authorized_uploader(client):
    c = client
    gid = group(c)
    b = c.post("/api/imports/splitwise/analyze", files={"file": ("Casa.csv", CSV)}).json()
    bid = b["id"]
    c.post(
        f"/api/imports/splitwise/{bid}/mapping",
        json={"users": {"Alex": 1, "Laura": 2}, "groups": {b["groups"][0]: gid}},
    )
    assert c.patch("/api/users/3", json={"is_admin": True}).status_code == 200
    r = c.post("/api/auth/login", json={"username": "outsider", "password": "password12345"})
    c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    assert c.get("/api/imports").json() == []
    assert c.get(f"/api/imports/{bid}").status_code == 403
    assert c.get(f"/api/imports/splitwise/{bid}/preview").status_code == 403


def test_csv_normalized_dedup_ignores_filename_when_mapped_to_same_group(client):
    c = client
    gid = group(c)
    for index, (filename, content) in enumerate(
        [("Original.csv", CSV), ("Renamed.csv", CSV + b"\n")]
    ):
        b = c.post("/api/imports/splitwise/analyze", files={"file": (filename, content)}).json()
        bid = b["id"]
        c.post(
            f"/api/imports/splitwise/{bid}/mapping",
            json={"users": {"Alex": 1, "Laura": 2}, "groups": {b["groups"][0]: gid}},
        )
        p = c.get(f"/api/imports/splitwise/{bid}/preview").json()
        assert p["duplicates"] == (2 if index else 0)
        assert c.post(f"/api/imports/splitwise/{bid}/commit").status_code == 200


def test_italian_export_plural_category_and_dated_balance_footer():
    content = b"Data,Descrizione,Categorie,Costo,Valuta,A,B\n\n2026-01-01,Spesa,Alimentari,36.20,EUR,-18.10,18.10\n2026-01-02,Pagamento,Pagamento,5.00,EUR,5.00,-5.00\n\n2026-10-01,Bilancio totale, , ,EUR,-13.10,13.10\n"
    data = parse_csv(content, "Casa")
    assert data["errors"] == []
    assert data["people"] == ["A", "B"]
    assert len(data["records"]) == 2
    assert data["records"][1]["kind"] == "SETTLEMENT"
    assert sum(r["deltas"]["A"] for r in data["records"]) == -1310
    assert len(data["warnings"]) == 1


def test_csv_expense_named_balance_is_not_dropped():
    content = b"Date,Description,Category,Cost,Currency,A,B\n2026-01-01,Bilancio totale,General,10.00,EUR,-5.00,5.00\n"
    data = parse_csv(content, "Casa")
    assert not data["errors"]
    assert len(data["records"]) == 1
