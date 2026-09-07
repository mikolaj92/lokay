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


def test_dispatch_uses_explicit_owner_without_probing_other_handlers(monkeypatch):
    from lokay import fala_organ
    from lokay.atom_bindings import Binding, BindingError

    probed = []

    def other(atom, inputs, up, ctx):
        probed.append(atom)
        return {"ok": True, "probed": True}

    def owner(atom, inputs, up, ctx):
        return {"ok": True, "atom": atom, "owned": True}

    monkeypatch.setattr(
        fala_organ,
        "ORGAN_BINDINGS",
        (Binding("inspect", owner), Binding("other", other)),
    )
    out = fala_organ._handle("inspect", {}, {})
    assert out == {"ok": True, "atom": "inspect", "owned": True}
    assert probed == []


def test_missing_binding_is_fail_closed_without_handler_scan(monkeypatch):
    from lokay import fala_organ
    from lokay.atom_bindings import Binding, BindingError

    def owner(atom, inputs, up, ctx):
        raise AssertionError("missing atom must not reach any handler")

    monkeypatch.setattr(fala_organ, "ORGAN_BINDINGS", (Binding("inspect", owner),))
    with pytest.raises(BindingError, match="missing"):
        fala_organ._handle("unknown", {}, {})


def test_conflicting_registry_fails_before_any_effect(monkeypatch):
    from lokay import fala_organ
    from lokay.atom_bindings import Binding, BindingError

    def first(atom, inputs, up, ctx):
        raise AssertionError("conflict must not execute")

    def second(atom, inputs, up, ctx):
        raise AssertionError("conflict must not execute")

    monkeypatch.setattr(
        fala_organ,
        "ORGAN_BINDINGS",
        (Binding("inspect", first), Binding("inspect", second)),
    )
    with pytest.raises(BindingError, match="conflict"):
        fala_organ._handle("inspect", {}, {})


def test_active_atoms_have_unique_owners():
    from lokay.fala_organ import ORGAN_BINDINGS
    from lokay.atom_bindings import BindingError, resolve
    from lokay.proc.atom_inventory import inventory
    from pathlib import Path

    report = inventory(Path("fala/lokay.fala-package.toml"), Path("src/lokay"))
    atoms = sorted(
        {
            node["atom"]
            for node in report["nodes"]
            if isinstance(node.get("atom"), str) and "${" not in node["atom"]
        }
    )
    assert atoms
    owners = {}
    for atom in atoms:
        binding = resolve(atom, ORGAN_BINDINGS)
        owners.setdefault(binding.handler, []).append(atom)
    assert all(owners.values())
    with pytest.raises(BindingError, match="missing"):
        resolve("this_atom_is_not_bound", ORGAN_BINDINGS)
