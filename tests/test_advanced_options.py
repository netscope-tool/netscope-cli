from types import SimpleNamespace

from questionary import Choice

from netscope.cli import advanced_options


def test_advanced_option_select_defaults_match_choice_values(monkeypatch):
    select_overrides = {"DNS record type?": "more"}
    confirm_overrides = {"Use custom DNS server?": True}

    def fake_select(message, *, choices, default=None, **kwargs):
        values = [choice.value if isinstance(choice, Choice) else choice for choice in choices]
        assert default in values, f"{message!r} default {default!r} is absent from {values!r}"
        selected = select_overrides.get(message, default)
        assert selected in values, f"test selection {selected!r} is absent from {values!r}"
        return SimpleNamespace(ask=lambda: selected)

    def fake_confirm(message, *, default=False, **kwargs):
        return SimpleNamespace(ask=lambda: confirm_overrides.get(message, default))

    def fake_text(message, *, default="", **kwargs):
        return SimpleNamespace(ask=lambda: default)

    monkeypatch.setattr(advanced_options.questionary, "select", fake_select)
    monkeypatch.setattr(advanced_options.questionary, "confirm", fake_confirm)
    monkeypatch.setattr(advanced_options.questionary, "text", fake_text)

    assert advanced_options.prompt_mode_selection() is True

    ping = advanced_options.prompt_ping_options(simple_mode=False)
    assert ping.count == 10
    assert ping.packet_size is None
    assert ping.interval is None
    assert ping.timeout is None

    simple_dns = advanced_options.prompt_dns_options(simple_mode=True)
    assert simple_dns.record_type == "NS"

    select_overrides.pop("DNS record type?")
    expert_dns = advanced_options.prompt_dns_options(simple_mode=False)
    assert expert_dns.record_type == "A"
    assert expert_dns.dns_server == "8.8.8.8"
    assert expert_dns.timeout == 5

    simple_ports = advanced_options.prompt_port_scan_options(simple_mode=True)
    assert simple_ports.timeout == 2.0

    expert_ports = advanced_options.prompt_port_scan_options(simple_mode=False)
    assert expert_ports.timeout == 2.0
    assert expert_ports.max_workers == 64
