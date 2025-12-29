import json
from typing import Optional

from fastapi import FastAPI, Request, Form, Query, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_302_FOUND
from database import SessionLocal, User
from auth import hash_password, verify_password
import requests

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="change-this-secret-key")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})

@app.post("/login", include_in_schema=False)
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    db = next(get_db())
    user = db.query(User).filter(User.email == email).first()
    if user and verify_password(password, user.password_hash):
        request.session["user"] = user.email
        return RedirectResponse("/search", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid email or password"})

@app.get("/logout", include_in_schema=False)
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=HTTP_302_FOUND)

@app.get("/create-user", response_class=HTMLResponse, include_in_schema=False)
def create_user_form():
    return """
    <form action="/create-user" method="post">
      <input type="email" name="email" placeholder="Email" required>
      <input type="password" name="password" placeholder="Password" required>
      <button type="submit">Create User</button>
    </form>
    """

@app.post("/create-user", include_in_schema=False)
def create_user(email: str = Form(...), password: str = Form(...)):
    db = next(get_db())
    hashed_password = hash_password(password)
    new_user = User(email=email, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    return {"msg": "User created successfully"}

@app.get("/search", response_class=HTMLResponse, include_in_schema=False)
def search_page(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login", status_code=HTTP_302_FOUND)
    return templates.TemplateResponse("search.html", {"request": request})



EGOV_URL = "https://cs.egov.uz/apiPartner/Table/Get"
ACCESS_TOKEN = "6951537446107f73f8e05636"

VALID_COLUMNS = {
    "BANK_ID", "BANK_TYPE", "REGION_ID", "HEADER_ID", "UNION_ID",
    "TCC_ID", "CCC_ID", "BANK_NAME", "BANK_ADRES", "BANK_STATU",
    "DATE_OPEN", "DATE_CLOSE", "ACTIVE", "DATE_ACT", "DATE_DEACT",
    "DISTR", "KOL_OBM", "INN"
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://cs.egov.uz/",
    "Origin": "https://cs.egov.uz"
}


class BankFilter(BaseModel):
    BANK_ID: Optional[str] = None
    BANK_TYPE: Optional[str] = None
    REGION_ID: Optional[str] = None
    HEADER_ID: Optional[str] = None
    UNION_ID: Optional[str] = None
    TCC_ID: Optional[str] = None
    CCC_ID: Optional[str] = None
    BANK_NAME: Optional[str] = None
    BANK_ADRES: Optional[str] = None
    BANK_STATU: Optional[str] = None
    DATE_OPEN: Optional[str] = None
    DATE_CLOSE: Optional[str] = None
    ACTIVE: Optional[str] = None
    DATE_ACT: Optional[str] = None
    DATE_DEACT: Optional[str] = None
    DISTR: Optional[str] = None
    KOL_OBM: Optional[str] = None
    INN: Optional[str] = None


@app.get("/api/search", include_in_schema=False)
def search_bank(request: Request, offset: int = 0, limit: int = 10, id: Optional[str] = None):
    if not request.session.get("user"):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)

    try:
        response = requests.get(EGOV_URL, params={
            "accessToken": ACCESS_TOKEN,
            "name": "400-4-001",
            "limit": limit,
            "offset": offset,
            "lang": 1
        }, headers=HEADERS, timeout=15)
        response.raise_for_status()
        api_data = response.json()
    except Exception as e:
        return JSONResponse({"detail": "Failed to fetch egov data", "error": str(e)}, status_code=500)

    rows = api_data.get("result", {}).get("data", [])
    total_count = api_data.get("result", {}).get("count", 0)

    # Apply filters directly from query parameters
    filters = {k: v for k, v in request.query_params.items() if k in VALID_COLUMNS and v.strip()}
    if filters:
        rows = [
            row for row in rows
            if all(str(row.get(col, "")).lower() == str(val).lower() for col, val in filters.items())
        ]

    return JSONResponse({"count": total_count, "data": rows})


@app.get("/look_for", tags=['Search'])
def swagger_search(request: Request, access_token: str = Query(...), offset: int = 0, limit: int = 100,
                filters: BankFilter = Depends()):
    if access_token != ACCESS_TOKEN:
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)

    params = {
        "accessToken": ACCESS_TOKEN,
        "name": "400-4-001",
        "limit": limit,
        "offset": offset,
        "lang": 1
    }

    try:
        response = requests.get(EGOV_URL, params=params, headers=HEADERS, timeout=15)
        response.raise_for_status()
        api_data = response.json()
    except Exception as e:
        return JSONResponse({"detail": "Failed to fetch egov data", "error": str(e)}, status_code=500)

    rows = api_data.get("result", {}).get("data", [])
    total_count = api_data.get("result", {}).get("count", 0)

    # Apply filters
    filters = {k: v.strip() for k, v in request.query_params.items() if k in VALID_COLUMNS and v.strip()}
    if filters:
        filtered = []
        for row in rows:
            if all(filters[col].lower() in str(row.get(col, "")).lower() for col in filters):
                filtered.append(row)
        rows = filtered

    return JSONResponse({"count": total_count, "data": rows})
