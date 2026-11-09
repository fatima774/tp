"""Tests de l'adaptateur HTTP : routes, codes de retour, format des réponses.

Les 6 premiers tests sont ceux de la version initiale, conservés tels quels :
ils prouvent que la refactorisation n'a pas cassé le comportement existant.
"""

# ---------------------------------------------------------------- tests hérités


def test_health_endpoint(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_artist_name_must_be_a_string(client):
    r = client.post("/artists", json={"name": 123, "genre": "Metal", "required_equipment": []})
    assert r.status_code == 422


def test_concert_end_must_be_after_start(client):
    r = client.post(
        "/concerts",
        json={
            "festival_id": 1,
            "artist_id": 1,
            "stage_id": 1,
            "start_time": "2027-06-18T15:00:00",
            "end_time": "2027-06-18T14:00:00",
        },
    )
    assert r.status_code in (400, 422)


def test_festival_end_must_be_after_start(client):
    r = client.post(
        "/festivals",
        json={
            "name": "Test Festival",
            "location": "Clisson",
            "start_date": "2027-06-20T10:00:00",
            "end_date": "2027-06-19T10:00:00",
        },
    )
    assert r.status_code == 400


def test_publish_unknown_festival_returns_404(client):
    assert client.post("/festivals/999/publish").status_code == 404


def test_stage_capacity_must_be_positive(client):
    r = client.post("/stages", json={"festival_id": 1, "name": "Mainstage", "capacity": 0, "available_equipment": []})
    assert r.status_code == 422


# ---------------------------------------------------------------- parcours complet


def test_full_flow_on_empty_database(client):
    f = client.post(
        "/festivals",
        json={
            "name": "Test Fest",
            "location": "Bordeaux",
            "start_date": "2027-07-01T10:00:00",
            "end_date": "2027-07-02T23:00:00",
        },
    )
    assert f.status_code == 201 and f.json()["status"] == "preparation"
    fid = f.json()["id"]
    a = client.post("/artists", json={"name": "Band", "genre": "Doom", "required_equipment": ["lights"]})
    assert a.status_code == 201
    s = client.post(
        "/stages", json={"festival_id": fid, "name": "Main", "capacity": 100, "available_equipment": ["lights"]}
    )
    assert s.status_code == 201
    c = client.post(
        "/concerts",
        json={
            "festival_id": fid,
            "artist_id": a.json()["id"],
            "stage_id": s.json()["id"],
            "start_time": "2027-07-01T20:00:00",
            "end_time": "2027-07-01T21:00:00",
        },
    )
    assert c.status_code == 201
    assert client.get(f"/concerts/{c.json()['id']}").json() == c.json()
    assert client.get(f"/festivals/{fid}").json()["name"] == "Test Fest"


# ---------------------------------------------------------------- codes d'erreur métier


def test_errors_carry_the_business_rule(seeded_client):
    r = seeded_client.post(
        "/concerts",
        json={
            "festival_id": 1,
            "artist_id": 4,
            "stage_id": 1,
            "start_time": "2027-06-18T18:30:00",
            "end_time": "2027-06-18T19:00:00",
        },
    )
    assert r.status_code == 409
    assert r.json()["rule"] == "R2"


def test_r5_missing_equipment_returns_400(seeded_client):
    # Iron Vow (large_rigging) sur la Warzone (special_lighting seulement)
    r = seeded_client.post(
        "/concerts",
        json={
            "festival_id": 1,
            "artist_id": 1,
            "stage_id": 2,
            "start_time": "2027-06-20T12:00:00",
            "end_time": "2027-06-20T13:00:00",
        },
    )
    assert r.status_code == 400 and r.json()["rule"] == "R5"


def test_r4_stage_of_unknown_festival_returns_400(client):
    r = client.post("/stages", json={"festival_id": 42, "name": "Ghost", "capacity": 10})
    assert r.status_code == 400 and r.json()["rule"] == "R4"


def test_unknown_concert_returns_404(client):
    assert client.get("/concerts/999").status_code == 404
    assert (
        client.patch(
            "/concerts/999/reschedule", json={"start_time": "2027-06-18T18:00:00", "end_time": "2027-06-18T19:00:00"}
        ).status_code
        == 404
    )


def test_duplicate_artist_returns_409_not_500(seeded_client):
    r = seeded_client.post("/artists", json={"name": "Iron Vow", "genre": "Heavy"})
    assert r.status_code == 409


def test_timezone_aware_dates_return_400_not_500(seeded_client):
    r = seeded_client.post(
        "/concerts",
        json={
            "festival_id": 1,
            "artist_id": 9,
            "stage_id": 3,
            "start_time": "2027-06-20T10:00:00+02:00",
            "end_time": "2027-06-20T11:00:00+02:00",
        },
    )
    assert r.status_code == 400


def test_r10_blank_incident_description_returns_400(seeded_client):
    r = seeded_client.post("/incidents", json={"concert_id": 1, "description": "   "})
    assert r.status_code == 400 and r.json()["rule"] == "R10"


def test_r10_incident_on_unknown_concert_returns_400(seeded_client):
    r = seeded_client.post("/incidents", json={"concert_id": 999, "description": "Ampli en panne"})
    assert r.status_code == 400 and r.json()["rule"] == "R10"


def test_incident_report_and_list(seeded_client):
    r = seeded_client.post(
        "/incidents", json={"concert_id": 1, "description": "Ampli en panne", "occurred_at": "2027-06-18T18:20:00"}
    )
    assert r.status_code == 201
    listed = seeded_client.get("/incidents", params={"concert_id": 1}).json()
    assert [i["description"] for i in listed] == ["Ampli en panne"]


def test_cancel_twice_returns_409(seeded_client):
    assert seeded_client.post("/concerts/1/cancel").status_code == 200
    assert seeded_client.post("/concerts/1/cancel").status_code == 409


def test_schedule_is_chronological_and_excludes_cancelled(seeded_client):
    seeded_client.post("/concerts/4/cancel")
    planning = seeded_client.get("/concerts/schedule/1").json()
    starts = [c["start_time"] for c in planning]
    assert starts == sorted(starts)
    assert 4 not in [c["id"] for c in planning]
    assert len(planning) == 13
