import json
import sys
import time
import urllib.error
import urllib.request


BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"


def request(path, method="GET", body=None, token=None, expected_status=200):
    url = f"{BASE_URL}{path}"
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            payload = response.read().decode("utf-8")
            parsed = json.loads(payload) if payload else {}
            if response.status != expected_status:
                raise RuntimeError(f"{method} {path} esperado {expected_status}, recebeu {response.status}: {parsed}")
            return parsed
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        parsed = json.loads(payload) if payload else {}
        if exc.code != expected_status:
            raise RuntimeError(f"{method} {path} esperado {expected_status}, recebeu {exc.code}: {parsed}") from exc
        return parsed


def main():
    stamp = str(int(time.time()))
    signup_a = request(
        "/api/signup",
        "POST",
        {
            "company_name": "Smoke Empresa A",
            "owner_name": "Master A",
            "owner_email": f"smokea{stamp}@test.local",
            "owner_password": "1234",
        },
    )
    signup_b = request(
        "/api/signup",
        "POST",
        {
            "company_name": "Smoke Empresa B",
            "owner_name": "Master B",
            "owner_email": f"smokeb{stamp}@test.local",
            "owner_password": "1234",
        },
    )

    token_a = signup_a["token"]
    token_b = signup_b["token"]

    prod_a = request(
        "/api/products",
        "POST",
        {"name": "Produto Smoke A", "sku": f"SM-A-{stamp}", "cost_price": 10, "desired_margin_percent": 30, "status": "active"},
        token=token_a,
    )
    request(
        "/api/products",
        "POST",
        {"name": "Produto Smoke B", "sku": f"SM-B-{stamp}", "cost_price": 20, "desired_margin_percent": 30, "status": "active"},
        token=token_b,
    )

    products_a = request("/api/products", token=token_a)
    products_b = request("/api/products", token=token_b)
    names_a = {row.get("name") for row in products_a}
    names_b = {row.get("name") for row in products_b}
    if "Produto Smoke A" not in names_a or "Produto Smoke B" in names_a:
        raise RuntimeError("Falha de isolamento: empresa A com dados incorretos.")
    if "Produto Smoke B" not in names_b or "Produto Smoke A" in names_b:
        raise RuntimeError("Falha de isolamento: empresa B com dados incorretos.")

    request(f"/api/products/{prod_a['product_id']}", method="DELETE", token=token_b, expected_status=404)

    print("OK: smoke multiempresa validado (isolamento e bloqueio cruzado).")


if __name__ == "__main__":
    main()
