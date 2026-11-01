from test_api import group, expense


def test_personal_expense_is_neutral_but_partial_then_total_payment_reduces_debt(client):
    gid = group(client)
    bill = {**expense(gid), "amount_cents": 50000}
    assert client.post("/api/expenses", json=bill).status_code == 201
    personal = {
        **bill,
        "description": "Rimborso",
        "amount_cents": 20000,
        "paid_by_user_id": 2,
        "splits": [{"user_id": 2}],
    }
    row = client.post("/api/expenses", json=personal)
    assert row.status_code == 201

    def remaining():
        return client.get(f"/api/groups/{gid}/debts").json()

    assert remaining()[0]["amount_cents"] == 50000
    assert client.delete(f"/api/expenses/{row.json()['id']}").status_code == 200
    for amount, expected in [(20000, 30000), (30000, 0)]:
        payment = client.post(
            "/api/settlements",
            json={
                "group_id": gid,
                "paid_by_user_id": 2,
                "paid_to_user_id": 1,
                "amount_cents": amount,
                "settlement_date": "2026-10-06",
            },
        )
        assert payment.status_code == 201
        debts = remaining()
        assert (debts[0]["amount_cents"] if debts else 0) == expected
        total = client.get("/api/dashboard/summary").json()["balances"][0]
        assert total["balance_cents"] == expected
        assert total["to_receive_cents"] == expected
