from pact.agents.compliance_agent import check_compliance
from pact.models.schemas import Offer, PolicyConstraints, VendorId


def _offer(price=10000.0):
    return Offer(vendor_id=VendorId.AWS, round_number=1, price_usd=price, claimed_discount_rate=0.0)


def test_passes_when_no_certifications_required():
    policy = PolicyConstraints(budget_ceiling_usd=20000)
    result = check_compliance(_offer(), policy, vendor_certifications=[])
    assert result.passed is True


def test_passes_when_vendor_holds_all_required_certifications():
    policy = PolicyConstraints(budget_ceiling_usd=20000, required_certifications=["SOC2"])
    result = check_compliance(_offer(), policy, vendor_certifications=["SOC2", "ISO27001"])
    assert result.passed is True


def test_rejects_when_vendor_missing_a_required_certification():
    policy = PolicyConstraints(budget_ceiling_usd=20000, required_certifications=["FedRAMP-High"])
    result = check_compliance(_offer(), policy, vendor_certifications=["SOC2", "ISO27001"])
    assert result.passed is False
    assert result.constraint_name == "required_certifications"
    assert "FedRAMP-High" in result.detail


def test_certification_check_only_runs_after_budget_and_blocklist_pass():
    """Budget/blocklist failures should be reported as such, not masked by
    a certification failure that would also be true."""
    policy = PolicyConstraints(budget_ceiling_usd=5000, required_certifications=["FedRAMP-High"])
    result = check_compliance(_offer(price=10000.0), policy, vendor_certifications=[])
    assert result.constraint_name == "budget_ceiling"
