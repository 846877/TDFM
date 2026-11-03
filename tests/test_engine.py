from tdfm.engine.advisor import Advisor
from tdfm.engine.item import Item, Outcome
from tdfm.engine.journal import Attempt, Journal
from tdfm.engine.model import EXO_SC, Observed, blend, estimate
from tdfm.engine.runes import STATS, find_rune


def make_item():
    it = Item("Bottes de test", 200)
    it.add_line("vi", 300, 350, current=300)
    it.add_line("fo", 60, 80, current=60)
    it.add_line("po", 1, 1)
    return it


def test_rune_weights():
    assert find_rune("Ra Vi").weight == 10
    assert find_rune("Ga Pa").weight == 100
    assert find_rune("Pa Do Feu").weight == 15
    assert STATS["vi"].over_cap == 505
    assert STATS["pa"].over_cap == 1


def test_puits_from_neutral_success():
    # Perdre 1 PO (51) avec une rune Do Feu (5) donne +46 de puits.
    it = make_item()
    it.add_line("do_feu", 0, 10, current=5)
    delta = it.apply(find_rune("Do Feu"), Outcome.SN, losses={"po": 1})
    assert delta == 46
    assert it.lines["do_feu"].current == 6


def test_puits_absorbs_failure():
    it = make_item()
    it.puits = 46
    it.apply(find_rune("Ra Vi"), Outcome.EC)
    assert it.puits == 36
    assert it.lines["vi"].current == 300


def test_sc_keeps_puits():
    it = make_item()
    it.puits = 20
    it.apply(find_rune("Ra Vi"), Outcome.SC)
    assert it.puits == 20
    assert it.lines["vi"].current == 350


def test_exo_odds():
    it = make_item()
    o = estimate(it, find_rune("Ga Pa"))
    assert o.sc == EXO_SC and o.sn == 0


def test_odds_drop_near_max():
    it = make_item()
    low = estimate(it, find_rune("Fo"))
    it.lines["fo"].current = 79
    high = estimate(it, find_rune("Fo"))
    assert low.sc > high.sc
    for o in (low, high):
        assert abs(o.sc + o.sn + o.ec - 1) < 1e-9


def test_blend_moves_toward_observed():
    prior = estimate(make_item(), find_rune("Fo"))
    b = blend(prior, Observed(sc=100, sn=0, ec=0))
    assert b.sc > prior.sc


def test_suggestions_ignore_finished_lines():
    it = make_item()
    it.lines["fo"].current = 80
    names = {s.rune.stat.code for s in Advisor().suggestions(it)}
    assert names == {"vi"}


def test_exo_timing():
    adv = Advisor(prices={"Ga Pa": 100_000})
    it = make_item()
    a = adv.exo(it, "pa")
    assert not a.ready and a.puits_missing == 100
    it.puits = 120
    a = adv.exo(it, "pa")
    assert a.ready and round(a.expected_attempts) == 100
    assert a.expected_cost == 100 * 100_000


def test_exo_line_disappears_on_loss():
    it = make_item()
    it.puits = 100
    it.apply(find_rune("Ga Pa"), Outcome.SC)
    assert it.lines["pa"].current == 1
    it.apply(find_rune("Ra Vi"), Outcome.EC, losses={"pa": 1})
    assert "pa" not in it.lines


def test_journal_stats(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    for o in ["SC", "EC", "SC"]:
        j.add(Attempt("x", "Fo", "bas", o, 0, 0))
    s = j.stats()[("Fo", "bas")]
    assert (s.sc, s.sn, s.ec) == (2, 0, 1)


def test_item_roundtrip():
    from tdfm.engine.item import item_from_dict, item_to_dict
    it = make_item()
    it.puits = 12
    it.lines["fo"].target = 75
    back = item_from_dict(item_to_dict(it))
    assert item_to_dict(back) == item_to_dict(it)
