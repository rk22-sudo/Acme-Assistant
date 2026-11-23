from types import SimpleNamespace

import pytest

from app.agent import _leaf, build_args, to_declaration


def _tool(props, required):
    return SimpleNamespace(name="t", description="d", input_schema={"properties": props, "required": required})


def test_employee_id_is_hidden_from_the_model():
    d = to_declaration(_tool({"employee_id": {"type": "string"}, "leave_type": {"type": "string"}},
                             ["employee_id", "leave_type"]))
    assert "employee_id" not in d.parameters.properties
    assert d.parameters.required == ["leave_type"]


def test_tool_with_only_identity_has_no_parameters():
    assert to_declaration(_tool({"employee_id": {"type": "string"}}, ["employee_id"])).parameters is None


def test_unsupported_argument_type_fails_loudly():
    with pytest.raises(ValueError):
        to_declaration(_tool({"x": {"type": "array"}}, ["x"]))


def test_model_supplied_identity_is_overwritten():
    args = build_args("get_leave_balance", {"employee_id": "E002"}, {"get_leave_balance"}, "E001")
    assert args == {"employee_id": "E001"}


def test_identity_not_added_to_tools_that_do_not_take_it():
    assert build_args("send_slack_message", {"channel": "general", "text": "hi"}, set(), "E001") == {
        "channel": "general", "text": "hi"}

def test_leaf_unwraps_nested_exception_groups():
    inner = ValueError("boom")
    group = BaseExceptionGroup("outer", [ExceptionGroup("inner", [inner])])
    assert _leaf(group) is inner
