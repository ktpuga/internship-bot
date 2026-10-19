import time

from bot.config import Config
from bot.feed import filter_listings, normalize_category
from bot.poller import plan_cycle
from bot.store import SeenStore

NOW = 1_800_000_000


def item(i, cat="Software", terms=("Summer 2027",), age_days=1, active=True, visible=True):
    return {
        "id": f"id{i}", "company_name": f"Co{i}", "title": "SWE Intern",
        "locations": ["Atlanta, GA"], "category": cat, "terms": list(terms),
        "url": f"https://x/{i}", "company_url": "", "active": active,
        "is_visible": visible, "date_posted": NOW - age_days * 86400,
        "sponsorship": "Other",
    }


def cfg(**kw):
    base = dict(categories=[], max_posts_per_cycle=25, max_age_days=14, seed_post_latest=0)
    base.update(kw)
    return Config(**base)


def test_category_aliases():
    assert normalize_category("Software Engineering") == "Software"
    assert normalize_category("Data Science, AI & Machine Learning") == "AI/ML/Data"
    assert normalize_category(None) == "Other"


def test_filter_rules():
    raw = [
        item(1), item(2, active=False), item(3, visible=False),
        item(4, terms=("Summer 2026",)), item(5, cat="Product"),
        item(6, age_days=30), item(7, cat="Software Engineering"),
    ]
    got = {x.id for x in filter_listings(raw, ["Summer 2027"], ["Software"], 14, NOW)}
    assert got == {"id1", "id7"}


def test_first_run_seeds_without_posting():
    store = SeenStore(":memory:")
    raw = [item(i) for i in range(50)]
    plan = plan_cycle(raw, store, cfg(), NOW)
    assert plan.to_post == [] and len(plan.mark_silently) == 50


def test_seed_post_latest():
    store = SeenStore(":memory:")
    raw = [item(i, age_days=i) for i in range(10)]
    plan = plan_cycle(raw, store, cfg(seed_post_latest=3), NOW)
    # newest are id0,id1,id2; posted oldest-first
    assert [x.id for x in plan.to_post] == ["id2", "id1", "id0"]
    assert len(plan.mark_silently) == 7


def test_new_items_detected_and_capped():
    store = SeenStore(":memory:")
    store.mark(["id0"])
    raw = [item(i, age_days=i % 10) for i in range(40)]
    plan = plan_cycle(raw, store, cfg(max_posts_per_cycle=25), NOW)
    assert len(plan.to_post) == 25 and plan.backlog == 14
    assert "id0" not in {x.id for x in plan.to_post}
    # chronological: oldest first
    ts = [x.date_posted for x in plan.to_post]
    assert ts == sorted(ts)


def test_unsent_items_retry_next_cycle():
    store = SeenStore(":memory:")
    store.mark(["seed"])
    raw = [item(1), item(2)]
    p1 = plan_cycle(raw, store, cfg(), NOW)
    store.mark([p1.to_post[0].id], posted=True)  # only first send succeeded
    p2 = plan_cycle(raw, store, cfg(), NOW)
    assert [x.id for x in p2.to_post] == [p1.to_post[1].id]
