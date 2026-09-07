"""Ownership resolution is metadata-only, never handler probing."""
import pytest

from lokay.atom_bindings import Binding, BindingError, resolve


def test_exact_binding_resolves_without_calling_executor():
    def forbidden(*args):
        raise AssertionError("resolution must not execute handlers")

    binding = Binding("inspect", forbidden)
    assert resolve("inspect", [binding]).handler is forbidden


def test_unknown_binding_fails_closed():
    with pytest.raises(BindingError, match="missing"):
        resolve("unknown", [])


def test_duplicate_binding_fails_even_for_same_handler():
    binding = Binding("inspect", object())
    with pytest.raises(BindingError, match="conflict"):
        resolve("inspect", [binding, binding])


def test_numbered_family_requires_positive_numeric_suffix():
    binding = Binding("slot_", object(), numbered=True)
    assert resolve("slot_12", [binding]) is binding
    for atom in ("slot_", "slot_bad", "slot_0", "slot_-1", "slot_1_extra", "slot_01"):
        with pytest.raises(BindingError, match="missing"):
            resolve(atom, [binding])


def test_exact_family_overlap_is_conflict_not_precedence():
    with pytest.raises(BindingError, match="conflict"):
        resolve("slot_1", [Binding("slot_1", object()), Binding("slot_", object(), numbered=True)])
