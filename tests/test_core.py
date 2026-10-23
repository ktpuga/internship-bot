from bot.config import Config, Source
from bot.feed import filter_listings, normalize_category
from bot.poller import fingerprint_key, plan_cycle, store_id
from bot.store import SeenStore

NOW = 1_800_000_000


def item(
    i, cat="Software", terms=("Summer 2027",), age_days=1, active=True, visible=True
):
    return {
        "id": f"id{i}",
        "company_name": f"Co{i}",
        "title": "SWE Intern",
        "locations": ["Atlanta, GA"],
        "category": cat,
        "terms": list(terms),
        "url": f"https://x/{i}",
        "company_url": "",
        "active": active,
        "is_visible": visible,
        "date_posted": NOW - age_days * 86400,
        "sponsorship": "Other",
    }


def src(**kw):
    base = dict(
        name="internship", feed_url="https://x", channel_id=1, terms=["Summer 2027"]
    )
    base.update(kw)
    return Source(**base)


def cfg(**kw):
    base = dict(
        categories=[], max_posts_per_cycle=25, max_age_days=14, seed_post_latest=0
    )
    base.update(kw)
    return Config(**base)


def prime(store, ids, c=None, source=None):
    """ids should be raw listing ids; we prefix them for the store."""
    source = source or src()
    c = c or cfg()
    store.mark(store_id(source, i) for i in ids)
    store.set_meta(fingerprint_key(source), c.filter_fingerprint(source))


def test_category_aliases():
    assert normalize_category("Software Engineering") == "Software"
    assert normalize_category("Data Science, AI & Machine Learning") == "AI/ML/Data"
    assert normalize_category(None) == "Other"


def test_filter_rules():
    raw = [
        item(1),
        item(2, active=False),
        item(3, visible=False),
        item(4, terms=("Summer 2026",)),
        item(5, cat="Product"),
        item(6, age_days=30),
        item(7, cat="Software Engineering"),
    ]
    got = {x.id for x in filter_listings(raw, ["Summer 2027"], ["Software"], 14, NOW)}
    assert got == {"id1", "id7"}


def test_first_run_seeds_without_posting():
    store = SeenStore(":memory:")
    raw = [item(i) for i in range(50)]
    plan = plan_cycle(raw, store, cfg(), src(), NOW)
    assert plan.to_post == [] and len(plan.mark_silently) == 50


def test_seed_post_latest():
    store = SeenStore(":memory:")
    raw = [item(i, age_days=i) for i in range(10)]
    plan = plan_cycle(raw, store, cfg(seed_post_latest=3), src(), NOW)
    # newest are id0,id1,id2; posted oldest-first
    assert [x.id for x in plan.to_post] == ["id2", "id1", "id0"]
    assert len(plan.mark_silently) == 7


def test_new_items_detected_and_capped():
    store = SeenStore(":memory:")
    prime(store, ["id0"])
    raw = [item(i, age_days=i % 10) for i in range(40)]
    plan = plan_cycle(raw, store, cfg(max_posts_per_cycle=25), src(), NOW)
    assert len(plan.to_post) == 25 and plan.backlog == 14
    assert "id0" not in {x.id for x in plan.to_post}
    # chronological: oldest first
    ts = [x.date_posted for x in plan.to_post]
    assert ts == sorted(ts)


def test_unsent_items_retry_next_cycle():
    store = SeenStore(":memory:")
    prime(store, ["seed"])
    raw = [item(1), item(2)]
    p1 = plan_cycle(raw, store, cfg(), src(), NOW)
    store.mark(
        [store_id(src(), p1.to_post[0].id)], posted=True
    )  # only first send succeeded
    p2 = plan_cycle(raw, store, cfg(), src(), NOW)
    assert [x.id for x in p2.to_post] == [p1.to_post[1].id]


# --- v0.2: keywords, US-only, filter-change reseed ---
from bot.location import is_us


def test_is_us():
    for s in [
        "Atlanta, GA",
        "NYC",
        "SF",
        "Remote in USA",
        "Georgia",
        "United States",
        "Washington, DC",
    ]:
        assert is_us(s), s
    for s in [
        "London, UK",
        "Toronto, ON, Canada",
        "Remote in UK",
        "Singapore",
        "Dublin, Ireland",
    ]:
        assert not is_us(s), s


def test_keyword_match_relabels_and_respects_word_boundaries():
    raw = [
        {**item(1, cat="AI/ML/Data"), "title": "Finance Analytics Intern"},
        {
            **item(2, cat="AI/ML/Data"),
            "title": "Taxonomy Research Intern",
        },  # 'tax' must not match
        {**item(3, cat="Product"), "title": "Product Manager Intern"},
        item(4, cat="Software"),
    ]
    got = {
        x.id: x.category
        for x in filter_listings(
            raw, ["Summer 2027"], ["Software"], 14, NOW, keywords=["finance", "tax"]
        )
    }
    assert got == {"id1": "Finance/Business", "id4": "Software"}


def test_us_only_drops_foreign_and_trims_locations():
    raw = [
        {**item(1), "locations": ["London, UK"]},
        {**item(2), "locations": ["Toronto, ON, Canada", "NYC"]},
    ]
    got = filter_listings(raw, ["Summer 2027"], [], 14, NOW, us_only=True)
    assert [(x.id, x.locations) for x in got] == [("id2", ["NYC"])]


def test_filter_change_seeds_silently_then_posts_normally():
    store = SeenStore(":memory:")
    raw = [item(1, cat="Software"), item(2, cat="Quant"), item(3, cat="Quant")]
    c1 = cfg(categories=["Software"])
    p = plan_cycle(raw, store, c1, src(), NOW)  # first run
    store.mark(p.mark_silently)
    store.set_meta(fingerprint_key(src()), p.fingerprint)
    c2 = cfg(categories=["Software", "Quant"])  # widen filters
    p = plan_cycle(raw, store, c2, src(), NOW)
    assert p.to_post == [] and sorted(p.mark_silently) == [
        "internship:id2",
        "internship:id3",
    ]
    store.mark(p.mark_silently)
    store.set_meta(fingerprint_key(src()), p.fingerprint)
    raw.append(item(9, cat="Quant"))  # genuinely new posting
    p = plan_cycle(raw, store, c2, src(), NOW)
    assert [x.id for x in p.to_post] == ["id9"]


def test_fingerprint_ignores_order_and_case():
    assert cfg(categories=["Software", "Quant"]).filter_fingerprint(src()) == cfg(
        categories=["quant", "software"]
    ).filter_fingerprint(src())


# --- per-source first run + legacy migration ---
from bot.poller import migrate_legacy_ids


def test_second_source_first_run_honors_seed_post_latest():
    store = SeenStore(":memory:")
    prime(store, ["a", "b"])  # internship already running
    ng = src(name="newgrad", terms=[])
    raw = [item(i, terms=(), age_days=i) for i in range(5)]
    p = plan_cycle(raw, store, cfg(seed_post_latest=2), ng, NOW)
    assert [x.id for x in p.to_post] == ["id1", "id0"]
    assert len(p.mark_silently) == 3 and all(i.startswith("newgrad:") for i in p.mark_silently)


def test_legacy_ids_migrated_so_upgrade_does_not_seed_post():
    store = SeenStore(":memory:")
    raw = [item(1), item(2)]
    store.mark(["id1", "id2"])  # DB written by the single-source version
    store.set_meta("filter_fingerprint", "old")
    c = cfg(seed_post_latest=3, sources=[src()])
    assert migrate_legacy_ids(store, c) == 2
    assert migrate_legacy_ids(store, c) == 0  # idempotent
    assert store.get_meta("filter_fingerprint") is None
    assert store.unseen(["internship:id1", "internship:id2", "id1"]) == {"id1"}
    p = plan_cycle(raw, store, c, src(), NOW)
    assert p.to_post == []  # not treated as a first run -> no seed posts


# --- Engineering keyword group ---
from bot.config import DEFAULT_ENGINEERING_KEYWORDS


def test_engineering_group_checked_before_finance_and_keeps_real_categories():
    raw = [
        {**item(1, cat="AI/ML/Data"), "title": "Manufacturing Data & Analytics Co-op"},  # both lists could match
        {**item(2, cat="AI/ML/Data"), "title": "Finance Analytics Intern"},
        {**item(3, cat="Hardware"), "title": "Systems Engineer Intern"},  # already wanted -> stays Hardware
        {**item(4, cat="AI/ML/Data"), "title": "Search Quality ML Intern"},  # bare 'quality' must not match
        {**item(5, cat="Product"), "title": "Robotics Engineer Intern"},
    ]
    got = {x.id: x.category for x in filter_listings(
        raw, ["Summer 2027"], ["Hardware"], 14, NOW,
        keywords=["finance", "analytics"],
        keyword_groups=[("Engineering", DEFAULT_ENGINEERING_KEYWORDS.split(","))])}
    assert got == {"id1": "Engineering", "id2": "Finance/Business", "id3": "Hardware", "id5": "Engineering"}


def test_engineering_keywords_change_fingerprint():
    assert cfg(engineering_keywords=["robotics"]).filter_fingerprint(src()) != \
           cfg(engineering_keywords=[]).filter_fingerprint(src())

