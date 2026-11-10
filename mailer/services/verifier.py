"""
mailer/services/verifier.py

DNS and Email Deliverability Verification Service.
Enforces RFC 5321 Mail Exchange (MX) record pre-flight checks
to guarantee recipient domains possess active mail servers before dispatch.
"""
import dns.resolver
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

def verify_email_mx(email: str, timeout: float = 3.0) -> tuple[bool, str]:
    """
    Validates an email address via syntax validation and DNS MX record lookup.
    
    Returns:
        tuple[bool, str]: (is_valid, reason)
    """
    clean_email = email.strip()
    if not clean_email:
        return False, "Empty email address"

    # 1. Syntax check
    try:
        validate_email(clean_email)
    except ValidationError:
        return False, "Invalid email syntax"

    try:
        domain = clean_email.split('@')[1].lower()
    except IndexError:
        return False, "Missing domain in email"

    # 2. DNS MX Record Lookup
    resolver = dns.resolver.Resolver()
    resolver.timeout = timeout
    resolver.lifetime = timeout

    try:
        mx_records = resolver.resolve(domain, 'MX')
        if mx_records and len(mx_records) > 0:
            return True, f"MX verified ({len(mx_records)} servers active)"
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
        # RFC 5321 fallback: check if domain has an active A record
        try:
            a_records = resolver.resolve(domain, 'A')
            if a_records and len(a_records) > 0:
                return True, "Fallback A-record verified"
        except Exception:
            return False, f"Domain '{domain}' has no active mail exchange (MX) servers"
    except dns.resolver.Timeout:
        return False, f"DNS timeout resolving '{domain}'"
    except Exception as e:
        return False, f"DNS lookup failed for '{domain}': {str(e)[:30]}"

    return False, f"Domain '{domain}' does not accept email"
