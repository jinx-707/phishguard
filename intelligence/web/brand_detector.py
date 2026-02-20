KNOWN_BRANDS = [
    "google", "paypal", "microsoft",
    "apple", "amazon", "facebook"
]

def detect_brand_impersonation(url):
    domain = url.lower()
    matches = []

    for brand in KNOWN_BRANDS:
        if brand in domain:
            matches.append(brand)

    impersonation = False
    if matches:
        for brand in matches:
            if not domain.endswith(f"{brand}.com"):
                impersonation = True

    return {
        "url": url,
        "brands_detected": matches,
        "impersonation": impersonation
    }

if __name__ == "__main__":
    urls = [
        "https://accounts.google.com",
        "https://google-login-secure.com",
        "https://paypal.com"
    ]

    for u in urls:
        print(detect_brand_impersonation(u))