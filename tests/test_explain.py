from fplcore.explain.template import TemplateExplainer


def test_template_mentions_transfer() -> None:
    text = TemplateExplainer().explain(
        {
            "horizon": 3,
            "transfers": [
                {
                    "out_name": "Saka",
                    "in_name": "Palmer",
                    "metric_deltas": {"fixture": 0.31, "form": 0.12},
                }
            ],
            "hits": 0,
            "gain_vs_roll": 6.4,
            "captain": {"web_name": "Haaland", "proj": 8.1},
            "vice": {"web_name": "Palmer"},
            "reason_codes": ["FIXTURE_SWING"],
        }
    )
    assert "Saka" in text and "Palmer" in text
    assert "Haaland" in text
