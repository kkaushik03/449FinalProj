import pytest
import sys, os
from fastapi.testclient import TestClient

# make sure main.py is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from main import app, metadata, engine

@pytest.fixture(autouse=True)
def reset_db():
    # recreate the database schema before each test
    metadata.drop_all(engine)
    metadata.create_all(engine)
    yield
    metadata.drop_all(engine)

client = TestClient(app)

def test_create_plan():
    print("Test 1: Testing create plan")
    payload = {"name": "Basic", "description": "Basic plan", "permission_ids": [], "limits": []}
    res = client.post("/plans", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    print("Passed")

def test_duplicate_plan_fails():
    print("Test 2: Testing duplicate plan fails")
    payload = {"name": "Basic", "description": "Basic plan", "permission_ids": [], "limits": []}
    client.post("/plans", json=payload)
    res = client.post("/plans", json=payload)
    assert res.status_code == 400
    assert res.json()["detail"] == "Plan name must be unique"
    print("Passed")

def test_update_plan():
    print("Test 3: Testing update plan")
    # create plan
    pid = client.post("/plans", json={"name":"Pro","description":"Pro plan","permission_ids":[],"limits":[]} ).json()["id"]
    # update name
    res = client.put(f"/plans/{pid}", json={"name":"ProPlus"})
    assert res.status_code == 200
    assert res.json()["status"] == "updated"
    # verify change
    sub = client.post("/subscriptions", json={"user_id":1,"plan_id":pid})
    view = client.get("/subscriptions/1").json()
    assert view["plan"]["name"] == "ProPlus"
    print("Passed")

def test_delete_plan():
    print("Test 4: Testing delete plan")
    pid = client.post("/plans", json={"name":"Temp","description":"Temp plan","permission_ids":[],"limits":[]} ).json()["id"]
    res = client.delete(f"/plans/{pid}")
    assert res.status_code == 200 and res.json()["status"] == "deleted"
    # now plan is gone
    res2 = client.put(f"/plans/{pid}", json={"name":"X"})
    assert res2.status_code == 404
    print("Passed")

def test_create_permission():
    print("Test 5: Testing create permission")
    payload = {"name":"perm1","endpoint":"endpoint1","description":"desc"}
    res = client.post("/permissions", json=payload)
    assert res.status_code == 200 and "id" in res.json()
    print("Passed")

def test_duplicate_permission_fails():
    print("Test 6: Testing duplicate permission fails")
    payload = {"name":"perm1","endpoint":"endpoint1","description":"desc"}
    client.post("/permissions", json=payload)
    res = client.post("/permissions", json=payload)
    assert res.status_code == 400
    assert "unique" in res.json()["detail"]
    print("Passed")

def test_update_permission():
    print("Test 7: Testing update permission")
    pid = client.post("/permissions", json={"name":"p2","endpoint":"e2","description":""}).json()["id"]
    res = client.put(f"/permissions/{pid}", json={"endpoint":"e2-new"})
    assert res.status_code == 200 and res.json()["status"] == "updated"
    print("Passed")

def test_delete_permission():
    print("Test 8: Testing delete permission")
    pid = client.post("/permissions", json={"name":"p3","endpoint":"e3","description":""}).json()["id"]
    res = client.delete(f"/permissions/{pid}")
    assert res.status_code == 200 and res.json()["status"] == "deleted"
    print("Passed")

def test_subscribe_and_duplicate_fails():
    print("Test 9: Testing subscribe and duplicate fails")
    # need a plan first
    plan_id = client.post("/plans", json={"name":"SubPlan","description":"","permission_ids":[],"limits":[]} ).json()["id"]
    res1 = client.post("/subscriptions", json={"user_id":42,"plan_id":plan_id})
    assert res1.status_code == 200 and res1.json()["status"] == "subscribed"
    res2 = client.post("/subscriptions", json={"user_id":42,"plan_id":plan_id})
    assert res2.status_code == 400 and "exists" in res2.json()["detail"]
    print("Passed")

def test_modify_subscription():
    print("Test 10: Testing modify subscription")
    plan1 = client.post("/plans", json={"name":"One","description":"","permission_ids":[],"limits":[]}).json()["id"]
    plan2 = client.post("/plans", json={"name":"Two","description":"","permission_ids":[],"limits":[]}).json()["id"]
    client.post("/subscriptions", json={"user_id":7,"plan_id":plan1})
    res = client.put("/subscriptions/7", json={"user_id":7,"plan_id":plan2})
    assert res.status_code == 200 and res.json()["status"] == "updated"
    print("Passed")

def test_view_subscription_details():
    print("Test 11: Testing view subscription details")
    # create permission and plan with that permission
    perm = client.post("/permissions", json={"name":"p4","endpoint":"e4","description":""}).json()["id"]
    plan = client.post("/plans", json={"name":"PlanA","description":"","permission_ids":[perm],"limits":[3]}).json()["id"]
    client.post("/subscriptions", json={"user_id":9,"plan_id":plan})
    res = client.get("/subscriptions/9")
    body = res.json()
    assert res.status_code == 200
    assert body["plan"]["id"] == plan
    assert body["permissions"][0]["endpoint"] == "e4"
    print("Passed")

def test_view_usage_empty_and_limit_status():
    print("Test 12: Testing view usage empty and limit status")
    perm = client.post("/permissions", json={"name":"p5","endpoint":"e5","description":""}).json()["id"]
    plan = client.post("/plans", json={"name":"PlanB","description":"","permission_ids":[perm],"limits":[1]}).json()["id"]
    client.post("/subscriptions", json={"user_id":11,"plan_id":plan})
    # usage should be empty
    usage = client.get("/subscriptions/11/usage").json()
    assert usage["usage"] == []
    # limits should show used=0
    lim = client.get("/usage/11/limit").json()
    assert lim["limits"][0]["used"] == 0
    print("Passed")

def test_access_control_and_usage_tracking():
    print("Test 13: Testing access control and usage tracking")
    # set up
    perm = client.post("/permissions", json={"name":"p6","endpoint":"svc1","description":""}).json()["id"]
    plan = client.post("/plans", json={"name":"PlanC","description":"","permission_ids":[perm],"limits":[2]}).json()["id"]
    client.post("/subscriptions", json={"user_id":21,"plan_id":plan})
    # first access
    ok = client.get("/access/21/svc1").json()
    assert ok["access"] is True
    # record usage
    rec = client.post("/usage/21", json={"endpoint":"svc1"})
    assert rec.status_code == 200
    # second usage ok
    client.post("/usage/21", json={"endpoint":"svc1"})
    # third usage hits limit
    res = client.post("/usage/21", json={"endpoint":"svc1"})
    assert res.status_code == 403 and "limit" in res.json()["detail"]
    print("Passed")

def test_service_route_integration():
    print("Test 14: Testing /services/{name} integration")
    # add a service permission matching service2
    perm = client.post("/permissions", json={"name":"p7","endpoint":"service2","description":""}).json()["id"]
    plan = client.post("/plans", json={"name":"PlanD","description":"","permission_ids":[perm],"limits":[1]}).json()["id"]
    client.post("/subscriptions", json={"user_id":31,"plan_id":plan})
    # valid call
    res1 = client.get("/services/service2", params={"user_id":31})
    assert res1.status_code == 200 and res1.json()["status"] == "OK"
    # next call exceeds limit
    res2 = client.get("/services/service2", params={"user_id":31})
    assert res2.status_code == 403
    # invalid service name
    res3 = client.get("/services/unknown", params={"user_id":31})
    assert res3.status_code == 404
    print("Passed")