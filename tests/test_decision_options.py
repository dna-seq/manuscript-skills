"""A decision's options (0.61.0): the alternatives a stage lists on a `decision: true` finding, or the adjudication on
its decision, carried by collect into the inventory and the To-do items, refused by stage_check and the inventory
when they are not two to six different alternatives on a decision, and named one by one in the Word review and the
Google Doc comments, so the authors answer by naming one (the Decisions pane in Claude Code makes each a button)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from test_dashboard_todo import collect, inventory, runner, synthetic_run, viz  # noqa: F401  (collect loads stage_check)

import stage_check  # noqa: E402  (beside collect, on the path test_dashboard_todo set)

OPTIONS = ["Keep the paragraph with the bridge (ST-C1)",
           "Cut it to one sentence beside the downloads, the rest to the supplement",
           "Leave the MCP server out until it has users"]


def test_collect_carries_a_stage_s_options_into_the_inventory_and_the_to_do_items(tmp_path: Path) -> None:
    run = synthetic_run(tmp_path)
    stage = run / "manuscript-integrity-check/findings.json"
    doc = json.loads(stage.read_text(encoding="utf-8"))
    doc["findings"][0] |= {"decision": True, "options": OPTIONS, "action": "Choose one; the first keeps the link."}
    stage.write_text(json.dumps(doc), encoding="utf-8")
    out = run / "manuscript-dashboard/findings.json"
    result = runner.invoke(collect.app, [str(run), "--output", str(out)])
    assert result.exit_code == 0, result.output
    data = viz.Inventory.model_validate_json(out.read_text(encoding="utf-8"))
    assert data.findings[0].options == OPTIONS
    item = next(i for i in viz.todo_items(data) if i["kind"] == "decision")
    assert (item["id"], item["options"]) == ("IC-1", OPTIONS)
    # every other item has none
    assert all(i["options"] == [] for i in viz.todo_items(data) if i["kind"] != "decision")


def test_an_adjudicated_decision_s_own_options_come_before_a_linked_finding_s(tmp_path: Path) -> None:
    raw = inventory(tmp_path)
    by_id = {f["id"]: f for f in raw["findings"]}
    by_id["F1"] |= {"decision": True, "options": ["Narrow it", "Rerun it"]}
    by_id["F5"] |= {"options": OPTIONS}
    items = {i["id"]: i for i in viz.todo_items(viz.Inventory.model_validate(raw))}
    # D1 links F1 and has none of its own: F1's; F5, a stage's own decision: its own
    assert items["D1"]["options"] == ["Narrow it", "Rerun it"] and items["F5"]["options"] == OPTIONS
    raw["decisions"][0]["options"] = ["Narrow the claim to one machine", "Rerun the benchmark on three"]
    items = {i["id"]: i for i in viz.todo_items(viz.Inventory.model_validate(raw))}
    assert items["D1"]["options"] == ["Narrow the claim to one machine", "Rerun the benchmark on three"]


@pytest.mark.parametrize("options, decision, refused", [
    (["Only one"], True, "lists 1 options"),
    ([f"Option {n}" for n in range(7)], True, "lists 7 options"),
    (["Keep it", "keep  it"], True, "the same option twice"),
    (["Keep it", "Cut it"], False, "is no decision"),
])
def test_the_inventory_refuses_options_that_are_not_a_choice(tmp_path: Path, options: list[str], decision: bool,
                                                            refused: str) -> None:
    raw = inventory(tmp_path)
    raw["findings"][0] |= {"decision": decision, "options": options}
    with pytest.raises(ValidationError, match=refused):
        viz.Inventory.model_validate(raw)
    raw = inventory(tmp_path)
    raw["decisions"][0]["options"] = options
    if decision:
        with pytest.raises(ValidationError, match=refused):
            viz.Inventory.model_validate(raw)


def test_stage_check_names_each_finding_whose_options_are_no_choice() -> None:
    def record(fid: str, **more) -> dict:
        return {"id": fid, "summary": "s", "decision": True, **more}

    doc = {"findings": [record("ST-1", options=OPTIONS),  # fine
                        record("ST-2"),  # no options: fine, the action is its way forward
                        record("ST-3", options=["Only one"]),
                        record("ST-4", options="Keep it, or cut it"),
                        record("ST-5", options=["Keep it", ""]),
                        record("ST-6", options=["Keep it", "Cut it"], decision=False),
                        record("ST-7", options=["Keep it", "Keep  it"])]}
    said = stage_check.option_problems(doc)
    assert [line.split(":")[0] for line in said] == [f"finding ST-{n}" for n in (3, 4, 5, 6, 7)]
    assert "give 2 to 6 alternatives" in said[0] and "belong to a decision" in said[3] and "twice" in said[4]


def test_the_reviews_name_each_option_in_one_sentence() -> None:
    assert viz.options_text(["Keep it.", "Cut it;"]) == "Options: (1) Keep it; (2) Cut it."
    assert viz.options_text([]) == ""


def test_the_page_lists_a_decision_s_options_numbered() -> None:
    page = (Path(__file__).resolve().parents[1] / "skills/manuscript-dashboard/assets/dashboard.html").read_text(encoding="utf-8")
    assert "function optionList(options)" in page
    # in the To-do tab, the problem's detail and its comment beside the passage
    assert page.count("optionList(") == 4


def test_the_google_doc_comment_on_a_decision_names_its_options(tmp_path: Path) -> None:
    from test_export_gdoc import gdoc

    raw = inventory(tmp_path)
    next(f for f in raw["findings"] if f["id"] == "F5")["options"] = OPTIONS
    data = viz.Inventory.model_validate(raw)
    items = {i["id"]: i for i in viz.todo_items(data)}
    said = gdoc.comment_text(items["F5"], data)
    assert said.startswith("A decision only you can make: Problem F5.")
    assert "Options: (1) Keep the paragraph with the bridge (ST-C1); (2) Cut it to one sentence beside the downloads, " \
           "the rest to the supplement; (3) Leave the MCP server out until it has users." in said and said.endswith("(F5)")
    # a decision without options says none
    assert "Options:" not in gdoc.comment_text(items["D1"], data)
