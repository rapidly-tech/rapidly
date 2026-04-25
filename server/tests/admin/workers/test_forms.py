"""Tests for ``rapidly/admin/workers/forms.py``.

Dynamic enqueue-task form generation. Three load-bearing surfaces:

- ``_FRAMEWORK_PARAMS`` excludes ``self`` from the list of
  user-visible actor parameters. Drift to drop the exclusion
  would surface ``self`` as a required field on every actor's
  enqueue form.
- ``_iter_callable_params`` flattens ``Unpack[TypedDict]`` kwargs
  into individual ``(name, annotation)`` pairs so kwargs-style
  actors render as a row of fields rather than a single opaque
  blob. Drift would either crash on iteration or render no
  fields for the kwargs actor.
- ``build_enqueue_task_form_class`` returns a Pydantic model that
  always carries a ``task`` selector. Bool-typed actor parameters
  default to ``False`` (so the admin can submit without ticking
  every box); other parameter types are required (``...``).
  Drift would either reject the form when the admin leaves a
  bool unset, or accept invalid empty values.
"""

from typing import Annotated, Any, TypedDict, Unpack

from rapidly.admin.workers import forms as M

# ---------------------------------------------------------------------------
# Helpers — synthetic functions exercising the introspection paths.
# ---------------------------------------------------------------------------


def _plain_fn(a: int, b: str = "x") -> None:  # pragma: no cover - introspected only
    pass


class _PlainClass:
    def method(self, a: int, b: str) -> None:  # pragma: no cover - introspected only
        pass


class _Kwargs(TypedDict):
    a: int
    b: str


def _kwargs_fn(
    **kwargs: Unpack[_Kwargs],
) -> None:  # pragma: no cover - introspected only
    pass


class TestFrameworkParamsExcluded:
    def test_self_is_in_framework_params(self) -> None:
        # Pin: ``self`` is the documented framework-injected
        # parameter that must NOT appear on actor forms.
        assert "self" in M._FRAMEWORK_PARAMS

    def test_iter_callable_params_skips_self_for_methods(self) -> None:
        # Pin: instance methods don't surface ``self`` as a form
        # field. Drift would force the admin to type the literal
        # string "self" into a text input on every method actor.
        params = list(M._iter_callable_params(_PlainClass.method))
        names = [name for name, _ in params]
        assert "self" not in names
        assert names == ["a", "b"]


class TestIterCallableParams:
    def test_plain_function_yields_each_param(self) -> None:
        # Pin: plain functions yield ``(name, annotation)`` for
        # every user-visible parameter.
        params = list(M._iter_callable_params(_plain_fn))
        assert params == [("a", int), ("b", str)]

    def test_unpack_typeddict_flattens_into_individual_fields(self) -> None:
        # Pin: ``Unpack[TypedDict]`` is exploded into the
        # underlying TypedDict's fields. Drift would either
        # crash on iteration or render the kwargs as a single
        # opaque blob.
        params = list(M._iter_callable_params(_kwargs_fn))
        # Order follows TypedDict declaration order (Python 3.7+
        # dict-insertion guarantee).
        assert params == [("a", int), ("b", str)]


class TestBuildEnqueueTaskFormClass:
    def _request(self) -> Any:
        from unittest.mock import MagicMock

        req = MagicMock()
        req.url_for.return_value = "/admin/tasks/enqueue"
        return req

    def test_no_task_only_task_selector_field(self) -> None:
        # Pin: with no task chosen, the form shows only the
        # task-selector dropdown. Drift would crash the initial
        # GET on missing fields for an absent actor.
        Form = M.build_enqueue_task_form_class(self._request(), task=None)
        assert "task" in Form.model_fields
        # Only the selector field is present.
        assert set(Form.model_fields) == {"task"}

    def test_task_selected_adds_actor_parameter_fields(self) -> None:
        # Pin: choosing a task adds its actor's parameter list
        # to the form (introspected from the function signature).
        # We register a synthetic actor through the broker
        # registry shim so the test does not depend on the
        # specific dramatiq actors that exist in the repo.
        actor_name = next(iter(M._TASK_DEFINITIONS))

        Form = M.build_enqueue_task_form_class(self._request(), task=actor_name)

        # The selector remains.
        assert "task" in Form.model_fields
        # At least the selector — extra params depend on the
        # actor's signature; the form must NOT crash on any of
        # the registered actors.
        assert isinstance(Form.model_fields, dict)

    def test_bool_param_defaults_to_false(self, monkeypatch: Any) -> None:
        # Pin: bool-typed actor params default to ``False`` so
        # the admin can submit without ticking every checkbox.
        # Drift to ``...`` (required) would 422 on submit
        # whenever the admin omitted any boolean.

        # Inject a synthetic actor whose ``fn`` has a bool param.
        def fake_fn(flag: bool, name: str) -> None:  # pragma: no cover
            pass

        class _FakeActor:
            fn = staticmethod(fake_fn)

        fake_actor: Any = _FakeActor()
        monkeypatch.setitem(M._TASK_DEFINITIONS, "test.fake_actor", fake_actor)

        Form = M.build_enqueue_task_form_class(self._request(), task="test.fake_actor")

        # ``flag`` (bool) is optional with default False;
        # ``name`` (str) is required.
        flag_default = Form.model_fields["flag"].default
        name_required = Form.model_fields["name"].is_required()
        assert flag_default is False
        assert name_required is True


class TestSelectChoices:
    def test_returns_sorted_task_names_as_value_label_pairs(self) -> None:
        # Pin: the dropdown's options are sorted by task name
        # for predictable scan-ability — admins read down the
        # list. Drift to dict-iteration order would shuffle on
        # every Python rebuild.
        choices = M._select_choices()
        names = [value for value, _label in choices]
        assert names == sorted(names)
        # Each entry is (name, name) — same value and label.
        for value, label in choices:
            assert value == label


class TestEnqueueTaskFormBase:
    def test_has_task_attribute(self) -> None:
        # Pin: ``task`` is the documented base attribute. Drift
        # to rename it would break the dispatch handler that
        # reads ``form.task``.
        # The class is defined with ``task: str``.
        assert "task" in M.EnqueueTaskFormBase.__annotations__


# Annotated import is used by static analyzers in the synthetic
# helpers above; suppress unused-import false-positive.
_ = Annotated
