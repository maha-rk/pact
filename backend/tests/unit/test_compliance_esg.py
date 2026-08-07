from pact.agents.compliance_agent import check_compliance
from pact.models.schemas import Offer, PolicyConstraints, VendorId


def _offer(price=10000.0):
    return Offer(vendor_id=VendorId.AWS, round_number=1, price_usd=price, claimed_discount_rate=0.0)


def test_passes_when_no_esg_threshold_set():
    policy = PolicyConstraints(budget_ceiling_usd=20000)
    result = check_compliance(_offer(), policy, vendor_renewable_energy_pct=None)
    assert result.passed is True


def test_passes_when_vendor_meets_the_renewable_energy_threshold():
    policy = PolicyConstraints(budget_ceiling_usd=20000, min_renewable_energy_pct=80.0)
    result = check_compliance(_offer(), policy, vendor_renewable_energy_pct=100.0)
    assert result.passed is True


def test_rejects_when_vendor_is_below_the_renewable_energy_threshold():
    policy = PolicyConstraints(budget_ceiling_usd=20000, min_renewable_energy_pct=90.0)
    result = check_compliance(_offer(), policy, vendor_renewable_energy_pct=60.0)
    assert result.passed is False
    assert result.constraint_name == "esg_renewable_energy"
    assert "60.0%" in result.detail
    assert "90.0%" in result.detail


def test_rejects_when_vendor_has_not_declared_a_renewable_energy_figure():
    policy = PolicyConstraints(budget_ceiling_usd=20000, min_renewable_energy_pct=50.0)
    result = check_compliance(_offer(), policy, vendor_renewable_energy_pct=None)
    assert result.passed is False
    assert result.constraint_name == "esg_renewable_energy"
    assert "undisclosed" in result.detail


def test_esg_check_only_runs_after_budget_blocklist_and_certification_pass():
    """A budget failure should be reported as such, not masked by an ESG
    failure that would also be true."""
    policy = PolicyConstraints(budget_ceiling_usd=5000, min_renewable_energy_pct=90.0)
    result = check_compliance(_offer(price=10000.0), policy, vendor_renewable_energy_pct=0.0)
    assert result.constraint_name == "budget_ceiling"
