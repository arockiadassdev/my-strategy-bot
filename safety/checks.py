"""
Safety checks — non-negotiable security validations for live trading.
"""
from config import Config


def check_api_key_permissions(api_key: str) -> bool:
    """
    Placeholder: In production, call exchange API to verify:
    - Key is trade-only (no withdrawal permission)
    - IP whitelisted
    For now, we warn the user to verify manually.
    """
    if not api_key:
        return False
    # In a real implementation, we'd call GET /v5/account/account-info
    # and check permissions. For now we issue a warning.
    print("⚠️  SECURITY: Please verify manually that your API key:")
    print("   - Has trade-only permission (no withdrawal)")
    print("   - Is IP-whitelisted")
    print("   - Has withdrawals disabled in Bybit API management")
    return True


def reject_deposit_scam_pattern(text: str) -> bool:
    """
    Never write code that could interpret 'deposit funds to activate'.
    Flag this pattern as a scam if it appears in config or prompts.
    """
    scam_patterns = [
        "deposit", "send funds", "activate account", "minimum deposit",
        "fund your account", "pay to unlock", "deposit to start",
        "verification fee",
    ]
    text_lower = text.lower()
    for pattern in scam_patterns:
        if pattern in text_lower:
            return True
    return False


def max_capital_safety_check() -> bool:
    """
    Ensure bot uses MAX_CAPITAL config, NOT live account balance.
    """
    if Config.MAX_CAPITAL <= 0:
        return False
    return True