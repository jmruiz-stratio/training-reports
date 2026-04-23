def derive_partner(username: str, email: str) -> str:
    if "stratio" in username.lower() or "stratio" in email.lower():
        return "stratio"
    parts = username.split("-")
    return parts[-1] if parts else username
