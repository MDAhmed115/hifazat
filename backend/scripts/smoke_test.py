"""Hifazat smoke test — run from backend folder:  python scripts\smoke_test.py"""
import httpx

BASE = "http://localhost:8000"          # backend must be running
API_KEY = "hifazat-demo-key-2026"       # must match backend/.env API_KEY

c = httpx.Client(base_url=BASE, timeout=30,
                 headers={"X-API-Key": API_KEY})
R = []

def check(name, ok, note=""):
    R.append(ok)
    print(("PASS " if ok else "FAIL "), name, ("| " + note if note else ""))

def token_for(phone, pw):
    r = c.post("/api/auth/login", json={"phone": phone, "password": pw})
    return r.json().get("token") if r.status_code == 200 else None

def auth(tok):
    return {"Authorization": f"Bearer {tok}"} if tok else {}

# 1. server alive
r = c.get("/health")
check("backend running", r.status_code == 200, "start uvicorn first if FAIL")

# 2. register 3 users (400, 403, 409 = already exists / seeded, that's fine)
ok = all(
    c.post("/api/auth/register", json={"name": n, "phone": p, "password": "test1234", "role": ro}).status_code in (200, 201, 400, 403, 409)
    for n, p, ro in [("Admin","0300-1111111","admin"), ("Citizen","0300-2222222","citizen"), ("Officer","0300-3333333","officer")]
)
check("register users", ok, "already exists or seeded is fine")

tok_a = token_for("0300-1111111", "test1234") or token_for("03000000000", "admin123")
tok_c = token_for("0300-2222222", "test1234") or token_for("03000000301", "citizen123")
tok_o = token_for("0300-3333333", "test1234") or token_for("03000000101", "officer123")
check("login works for all roles", bool(tok_a and tok_c and tok_o))

# 3. RBAC: citizen must be blocked from auditor-only data
r = c.get("/api/audit", headers=auth(tok_c))
check("RBAC enforced", r.status_code == 403, "404 = audit routes not built yet (skip for now)")

# 4. mock services (after P3)
r = c.get("/api/mock/schemes", headers=auth(tok_c))
check("mock schemes", r.status_code == 200, "404 = mocks not built yet (skip)")

# 5. AI engine (after P7, needs GROQ_API_KEY in backend/.env)
r = c.post("/api/analyze", headers=auth(tok_c), json={"message_text":
    "Congratulations! Aap ne Bait-ul-Maal Relief jeeta hai. Rs 250,000 prize claim karne "
    "ke liye Rs 250 processing fee Raast karein: 0300-7788990"})
if r.status_code == 404:
    check("AI analyze", False, "404 = analyze not built yet (skip)")
else:
    d = r.json() if r.status_code == 200 else {}
    lab, conf = d.get("label"), d.get("confidence")
    check("AI classifies scam SMS", r.status_code == 200 and lab == "scam",
          f"label={lab} confidence={conf}")

print(f"\n{sum(R)}/{len(R)} passed — " + ("ALL GOOD" if all(R) else "fix the FAIL lines, then re-run"))
