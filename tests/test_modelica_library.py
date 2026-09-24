"""
Adversarial pytest coverage for the vendored Modelica Standard Library subset.

Unlike tests/test_namespaces.py (a standalone smoke-test script), this file is
pytest-based and exercises: exhaustive per-namespace type instantiation,
Complex being deliberately unvendored (Complex-typed values raise
ClassNotFoundError), declaration-binding function calls being unresolvable
with pymoca 0.11.2, static reference resolution across the vendored .mo
files, vendored-file content pinning, and cross-namespace unit-string
consistency.

Requires pymoca, casadi and pytest as CI-only test dependencies (never runtime
dependencies of this package).

Usage (from a checkout, testing the working tree):
  pip install -e . "pymoca>=0.11,<0.12" "casadi>=3.6,<3.8" pytest
  pytest tests/test_modelica_library.py -v
"""
import hashlib
import os
import tempfile
from importlib.metadata import entry_points
from pathlib import Path

import importlib.resources
import pytest

pymoca = pytest.importorskip("pymoca")
pymoca_api = pytest.importorskip("pymoca.backends.casadi.api")
import pymoca.ast
import pymoca.parser


# ---------------------------------------------------------------------------
# Library / tree loading helpers
# ---------------------------------------------------------------------------

VENDORED_FILES = ("Icons.mo", "Units.mo", "SIunits.mo", "Constants.mo")


def library_folders():
    folders = []
    for ep in entry_points(group="rtctools.libraries.modelica"):
        if ep.name == "library_folder":
            folders.append(str(importlib.resources.files(ep.module).joinpath(ep.attr)))
    return folders


LIB_FOLDERS = library_folders()


def test_exactly_one_library_folder_registered():
    # Guards against a broken/missing install silently producing confusing
    # "class not found" errors instead of a clear "library not installed"
    # message.
    assert len(LIB_FOLDERS) == 1


def _modelica_dir():
    return os.path.join(LIB_FOLDERS[0], "Modelica")


def _read_vendored(fname):
    path = os.path.join(_modelica_dir(), fname)
    with open(path, encoding="utf-8") as f:
        return f.read()


def _parse_file(fname):
    return pymoca.parser.parse(_read_vendored(fname), bypass_cache=True)


def _merged_tree():
    """Parse+merge all four vendored files the way pymoca's own loader does
    (pymoca.backends.casadi.api._compile_model: sequential tree.extend())."""
    tree = None
    for fname in VENDORED_FILES:
        parsed = pymoca.parser.parse(_read_vendored(fname), bypass_cache=True)
        if tree is None:
            tree = parsed
        else:
            tree.extend(parsed)
    return tree


def transfer(model_name, mo_src):
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / f"{model_name}.mo").write_text(mo_src, encoding="utf-8")
        pymoca_api.transfer_model(
            d, model_name, {"cache": False, "library_folders": LIB_FOLDERS}
        )


# ---------------------------------------------------------------------------
# Namespace enumeration
# ---------------------------------------------------------------------------

def _walk_type_classes(pkg_class):
    """All `type`-restricted classes directly under pkg_class.classes (the
    vendored namespaces declare their SI/NonSI types at a single nesting
    level, not scattered across deeper sub-packages)."""
    return {name: cls for name, cls in pkg_class.classes.items() if cls.type == "type"}


def _units_si():
    tree = _parse_file("Units.mo")
    return _walk_type_classes(tree.classes["Modelica"].classes["Units"].classes["SI"])


def _units_nonsi():
    tree = _parse_file("Units.mo")
    return _walk_type_classes(tree.classes["Modelica"].classes["Units"].classes["NonSI"])


def _siunits():
    tree = _parse_file("SIunits.mo")
    return _walk_type_classes(tree.classes["Modelica"].classes["SIunits"])


def _siunits_conversions_nonsiunits():
    tree = _parse_file("SIunits.mo")
    conv = tree.classes["Modelica"].classes["SIunits"].classes["Conversions"]
    return _walk_type_classes(conv.classes["NonSIunits"])


# ---------------------------------------------------------------------------
# 1. Exhaustive instantiation per namespace
# ---------------------------------------------------------------------------

NAMESPACE_CASES = [
    pytest.param("Modelica.Units.SI", _units_si, 450, 506, id="Units.SI"),
    pytest.param("Modelica.Units.NonSI", _units_nonsi, 15, 18, id="Units.NonSI"),
    pytest.param("Modelica.SIunits", _siunits, 450, 505, id="SIunits"),
    pytest.param(
        "Modelica.SIunits.Conversions.NonSIunits",
        _siunits_conversions_nonsiunits,
        15,
        20,
        id="SIunits.Conversions.NonSIunits",
    ),
]


@pytest.mark.parametrize("qualified_prefix,type_getter,floor,expected_actual", NAMESPACE_CASES)
def test_namespace_types_instantiate(qualified_prefix, type_getter, floor, expected_actual):
    types = type_getter()
    assert len(types) >= floor, (
        f"{qualified_prefix}: found {len(types)} type-restricted classes, "
        f"expected at least {floor} (~{expected_actual} at time of writing)"
    )

    model_name = "TestBatch_" + qualified_prefix.replace(".", "_")
    names = sorted(types)
    decls = "\n".join(f"  {qualified_prefix}.{n} var{i};" for i, n in enumerate(names))
    src = f"model {model_name}\n{decls}\nend {model_name};\n"

    try:
        transfer(model_name, src)
    except Exception as batch_exc:
        # Batched parse failed: fall back to one-at-a-time so the failure
        # names the specific offending type, rather than leaving a single
        # opaque batch-level error.
        culprits = []
        for i, n in enumerate(names):
            single_name = f"{model_name}_single_{i}"
            single_src = f"model {single_name}\n  {qualified_prefix}.{n} var0;\nend {single_name};\n"
            try:
                transfer(single_name, single_src)
            except Exception as single_exc:
                culprits.append((n, repr(single_exc)))

        pytest.fail(
            f"{qualified_prefix}: batched instantiation failed ({batch_exc!r}); "
            f"per-type retry found {len(culprits)} broken type(s): {culprits}"
        )


# ---------------------------------------------------------------------------
# 2. Complex is deliberately unvendored
# ---------------------------------------------------------------------------

@pytest.mark.xfail(raises=pymoca.ast.ClassNotFoundError)  # strict via pyproject.toml xfail_strict
def test_complex_types_xfail():
    transfer(
        "TestComplexXfail",
        "model TestComplexXfail\n  Complex x = Complex(1.0, 2.0);\nend TestComplexXfail;\n",
    )


# ---------------------------------------------------------------------------
# 3. Declaration-binding-form function calls, pymoca 0.11.2
# ---------------------------------------------------------------------------

def test_declaration_binding_function_call_fails():
    # pymoca 0.11.2 raises a bare Exception (not a specific subclass) whose
    # message names the first dotted segment of the unresolved qualified
    # call, not the leaf function name (e.g. "Modelica", not "to_deg") --
    # anchored to reduce the chance of matching an unrelated failure.
    with pytest.raises(Exception, match=r"^Unknown function Modelica$"):
        transfer(
            "TestDeclBind",
            "model TestDeclBind\n"
            "  Real x = Modelica.Units.Conversions.to_deg(1.0);\n"
            "end TestDeclBind;\n",
        )


# ---------------------------------------------------------------------------
# 4. Equation-form Conversions calls resolve
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fn_name", ["to_deg", "to_degC"])
def test_conversions_equation_form_resolve(fn_name):
    model_name = f"TestEqForm_{fn_name}"
    src = (
        f"model {model_name}\n"
        f"  Real x;\n"
        f"equation\n"
        f"  x = Modelica.Units.Conversions.{fn_name}(1.0);\n"
        f"end {model_name};\n"
    )
    transfer(model_name, src)  # must not raise


# ---------------------------------------------------------------------------
# 5. No dangling Modelica.*/Complex references in the vendored files
# ---------------------------------------------------------------------------

_SKIP_WALK_KEYS = {"parent", "root", "annotation", "comment"}


def _collect_modelica_refs(node, refs, seen_ids):
    """Recursively collect every ComponentRef whose first segment is
    `Modelica`, plus bare `Complex` refs, from a parsed pymoca AST node.

    ComponentRef is treated as a leaf (its str() gives the full dotted
    name) -- do not descend into `.child`, or fragments like `Icons.Package`
    get collected instead of the full `Modelica.Icons.Package`.
    `parent`/`root` are back-references (would recurse forever); `annotation`
    and `comment` hold HTML documentation strings, not code references.
    """
    if id(node) in seen_ids:
        return
    if isinstance(node, pymoca.ast.ComponentRef):
        seen_ids.add(id(node))
        s = str(node)
        if s.split(".")[0] == "Modelica" or s == "Complex":
            refs.add(s)
        return
    if isinstance(node, (list, tuple)):
        for item in node:
            _collect_modelica_refs(item, refs, seen_ids)
        return
    if isinstance(node, dict):
        for v in node.values():
            _collect_modelica_refs(v, refs, seen_ids)
        return
    if hasattr(node, "__dict__"):
        seen_ids.add(id(node))
        for k, v in vars(node).items():
            if k in _SKIP_WALK_KEYS:
                continue
            _collect_modelica_refs(v, refs, seen_ids)


def _resolves(ref, tree):
    """Whether a dotted Modelica.* reference (or bare Complex) resolves to a
    class or a constant symbol in the combined parsed tree.

    Precondition: ref is "Complex" or a dot-separated path starting with
    "Modelica" (guaranteed by _collect_modelica_refs, the only real caller).
    Any other ref, including "", is a caller bug and raises rather than
    silently returning False."""
    if ref == "Complex":
        return False
    parts = ref.split(".")
    if parts[0] != "Modelica":
        raise ValueError(f"_resolves expects a Modelica.*/Complex ref, got {ref!r}")
    node = tree.classes.get("Modelica")
    if node is None:
        return False
    for i, p in enumerate(parts[1:], start=1):
        if hasattr(node, "classes") and p in node.classes:
            node = node.classes[p]
            continue
        if hasattr(node, "symbols") and p in node.symbols:
            # Constant symbol: terminal, but only resolves if this was the
            # last segment -- trailing segments past a symbol (e.g. a typo'd
            # Modelica.Constants.pi.bogus) are unresolved, not valid.
            return i == len(parts) - 1
        return False
    return True


def test_no_dangling_modelica_references():
    tree = _merged_tree()

    refs = set()
    _collect_modelica_refs(tree, refs, set())

    # Vacuity guard: if the walker silently skips a node type (e.g. a future
    # pymoca.ast change renames a field), refs could shrink to ~empty and
    # this test would trivially pass. Assert known anchors are present.
    known_anchors = {
        "Modelica.Icons.Package",
        "Modelica.Constants.pi",
        "Modelica.Constants.T_zero",
        "Complex",
    }
    assert known_anchors <= refs, f"missing expected anchors: {known_anchors - refs}"
    # Vacuity floor, not an exact-content pin (vendored-file checksums already
    # cover exact content; this only guards against the walker collecting
    # ~nothing). 66 at time of writing.
    assert len(refs) >= 60, f"suspiciously few Modelica.*/Complex references found: {len(refs)}"

    unresolved = {r for r in refs if not _resolves(r, tree)}
    assert unresolved == {"Complex"}, (
        f"unresolved Modelica.*/Complex references: {sorted(unresolved)} "
        f"(only 'Complex' is an expected, intentional gap)"
    )


def test_dangling_reference_walker_detects_negative_control():
    # Exercises _resolves against the real merged library tree, which has
    # resolvable Modelica.* content -- an ad-hoc model with no Modelica
    # class would short-circuit at the "node is None" guard instead of
    # reaching the per-segment matching loop or its precondition check.
    tree = _merged_tree()

    # The walker must actually collect known real references, not silently
    # no-op (e.g. a future pymoca.ast field rename breaking the recursion).
    refs = set()
    _collect_modelica_refs(tree, refs, set())
    assert "Modelica.Icons.Package" in refs

    # A non-existent leaf under a real, resolvable package.
    assert not _resolves("Modelica.Icons.DoesNotExist", tree)

    # A reference that resolves through a constant symbol (Modelica.Constants.pi)
    # but has a trailing segment past it must NOT resolve: a symbol is only a
    # valid terminal when it's the last path segment.
    assert _resolves("Modelica.Constants.pi", tree)
    assert not _resolves("Modelica.Constants.pi.bogus", tree)

    # Single-segment ref: the root package itself resolves.
    assert _resolves("Modelica", tree)

    # Malformed input (not "Complex", doesn't start with "Modelica") is a
    # caller bug, not a valid unresolved reference -- must raise, not
    # silently return False.
    with pytest.raises(ValueError, match="expects a Modelica"):
        _resolves("", tree)


# ---------------------------------------------------------------------------
# 6. Vendored file content pinning
# ---------------------------------------------------------------------------

EXPECTED_SHA256 = {
    "Icons.mo": "a5e988fd8756b635d35adef2b4211fdd04422f0449d7d9cf199c61f111932884",
    "Units.mo": "d515d5e2c46cc2fbe29e5a50b684266843d44be9a08050713521af2207e3c55f",
    "SIunits.mo": "c68fc25497f37cd0de376288ba007d5c1d1d629c7f7c862e130d02c2fa32915a",
    "Constants.mo": "f5da93602fbd1f8434ad62def3f0bfda360847c7c25e067e8bfbfe7e8525d3d5",
}


@pytest.mark.parametrize("fname", VENDORED_FILES)
def test_vendored_file_checksums(fname):
    with open(os.path.join(_modelica_dir(), fname), "rb") as f:
        content = f.read()
    normalized = content.replace(b"\r\n", b"\n")  # stable across CRLF/LF checkouts
    actual = hashlib.sha256(normalized).hexdigest()
    assert actual == EXPECTED_SHA256[fname], (
        f"{fname} content changed (sha256 {actual} != pinned {EXPECTED_SHA256[fname]}); "
        f"update EXPECTED_SHA256 if this change is intentional"
    )


# ---------------------------------------------------------------------------
# 7. Cross-namespace unit consistency: Modelica.SIunits.* vs Modelica.Units.SI.*
# ---------------------------------------------------------------------------

# Differences observed between MSL 3.2.3 (SIunits) and MSL 4.0.0 (Units.SI)
# `unit=` strings for shared type names, beyond declaration-style differences
# (e.g. a type extending another SI type instead of restating unit= on Real,
# which resolve identically via transitive lookup). Currently empty: the
# transitive unit-string comparison found no differences between the two
# vendored namespaces.
KNOWN_UNIT_DIFFERENCES = frozenset()


def _direct_unit(cls):
    for ext in cls.extends:
        cm = ext.class_modification
        if cm is None:
            continue
        for arg in cm.arguments:
            val = arg.value
            if str(getattr(val, "component", "")) == "unit":
                mods = val.modifications
                if mods:
                    return mods[0].value
    return None


def _base_names(cls):
    return [str(ext.component) for ext in cls.extends]


def _resolve_unit(name, classes_by_name, seen=None):
    """Resolve a type's unit= string, following `extends` chains through
    other locally-declared SI types (MSL sometimes declares a type as an
    alias of another SI type rather than restating quantity=/unit= on Real
    directly). Tries every `extends` entry, not just the first -- Modelica
    permits multiple inheritance, and the unit-bearing ancestor need not be
    the first one listed."""
    if seen is None:
        seen = set()
    if name in seen or name not in classes_by_name:
        return None
    seen.add(name)
    cls = classes_by_name[name]
    direct = _direct_unit(cls)
    if direct is not None:
        return direct
    for base in _base_names(cls):
        resolved = _resolve_unit(base, classes_by_name, seen)
        if resolved is not None:
            return resolved
    return None


def _diff_units(siunits_units, si_units, shared):
    """Unit-string comparison for shared type names, called by both
    test_cross_namespace_unit_consistency and
    test_cross_namespace_unit_diff_detection_exercises_branch."""
    diffs = []
    for name in sorted(shared):
        a, b = siunits_units.get(name), si_units.get(name)
        if a is None or b is None:
            continue
        if a != b:
            diffs.append((name, a, b))
    return diffs


def _find_unit_diffs():
    si_types = _units_si()
    siunits_types = _siunits()

    si_units = {n: _resolve_unit(n, si_types) for n in si_types}
    siunits_units = {n: _resolve_unit(n, siunits_types) for n in siunits_types}

    shared = set(si_units) & set(siunits_units)
    diffs = _diff_units(siunits_units, si_units, shared)
    return shared, si_units, siunits_units, diffs


def test_cross_namespace_unit_consistency():
    shared, si_units, siunits_units, diffs = _find_unit_diffs()

    # ~498 shared type names between the two namespaces at time of writing.
    assert len(shared) >= 490, f"expected ~498 shared type names, found {len(shared)}"

    # Every shared type must resolve to a concrete unit on both sides
    # (guards against the resolver silently returning None and the diff
    # check below going vacuous).
    unresolved = {n for n in shared if si_units[n] is None or siunits_units[n] is None}
    assert not unresolved, f"could not resolve unit= for shared types: {sorted(unresolved)}"

    new_diffs = [(n, a, b) for (n, a, b) in diffs if (n, a, b) not in KNOWN_UNIT_DIFFERENCES]
    assert not new_diffs, (
        f"new, unexpected unit= differences between Modelica.SIunits.* and "
        f"Modelica.Units.SI.*: {new_diffs}"
    )


def test_cross_namespace_unit_diff_detection_exercises_branch():
    # Feeds _diff_units a synthetically mutated unit string, so a bug in the
    # comparison logic (e.g. `a != b` flipped to `a == b`) is caught here --
    # the real vendored data has zero differences, so
    # test_cross_namespace_unit_consistency never takes this branch.
    shared, si_units, siunits_units, _ = _find_unit_diffs()
    name = next(iter(shared))
    synthetic_si = dict(si_units)
    synthetic_si[name] = (synthetic_si[name] or "") + "_MISMATCH"

    diffs = _diff_units(siunits_units, synthetic_si, shared)
    assert (name, siunits_units[name], synthetic_si[name]) in diffs


def test_resolve_unit_follows_all_extends_entries():
    # _resolve_unit tries every `extends` entry, not just the first --
    # Modelica permits multiple inheritance, and the unit-bearing ancestor
    # need not be first.
    src = (
        "package Test\n"
        '  type Base = Real(final quantity="Length", final unit="m");\n'
        "  type NoUnitMixin = Real;\n"
        "  type Multi\n"
        "    extends NoUnitMixin;\n"
        "    extends Base;\n"
        "  end Multi;\n"
        "end Test;\n"
    )
    tree = pymoca.parser.parse(src, bypass_cache=True)
    classes = _walk_type_classes(tree.classes["Test"])
    assert _resolve_unit("Multi", classes) == "m"


def test_resolve_unit_unit_bearer_in_middle_of_three_extends():
    # Distinguishes "tries every entry" from "tries only the first/last
    # entry": the unit-bearing ancestor is neither first nor last here.
    src = (
        "package Test\n"
        "  type NoUnitA = Real;\n"
        '  type Base = Real(final quantity="Length", final unit="m");\n'
        "  type NoUnitB = Real;\n"
        "  type Multi\n"
        "    extends NoUnitA;\n"
        "    extends Base;\n"
        "    extends NoUnitB;\n"
        "  end Multi;\n"
        "end Test;\n"
    )
    tree = pymoca.parser.parse(src, bypass_cache=True)
    classes = _walk_type_classes(tree.classes["Test"])
    assert _resolve_unit("Multi", classes) == "m"


def test_resolve_unit_multi_hop_recursion():
    # The unit-bearing type is two hops away (Multi -> Mid -> Base), not a
    # direct extends target -- exercises the recursive branch, not just
    # single-hop lookahead across siblings.
    src = (
        "package Test\n"
        '  type Base = Real(final quantity="Length", final unit="m");\n'
        "  type Mid\n"
        "    extends Base;\n"
        "  end Mid;\n"
        "  type Multi\n"
        "    extends Mid;\n"
        "  end Multi;\n"
        "end Test;\n"
    )
    tree = pymoca.parser.parse(src, bypass_cache=True)
    classes = _walk_type_classes(tree.classes["Test"])
    assert _resolve_unit("Multi", classes) == "m"


def test_resolve_unit_returns_none_when_no_unit_anywhere():
    # A fully unit-less extends chain must resolve to None, not raise or
    # return a stale value from an unrelated branch.
    src = (
        "package Test\n"
        "  type NoUnitBase = Real;\n"
        "  type Multi\n"
        "    extends NoUnitBase;\n"
        "  end Multi;\n"
        "end Test;\n"
    )
    tree = pymoca.parser.parse(src, bypass_cache=True)
    classes = _walk_type_classes(tree.classes["Test"])
    assert _resolve_unit("Multi", classes) is None


def test_resolve_unit_cycle_terminates():
    # A extends B, B extends A: the `seen` guard must terminate the
    # recursion (returning None, since neither carries a direct unit)
    # rather than recursing until RecursionError.
    src = (
        "package Test\n"
        "  type A\n"
        "    extends B;\n"
        "  end A;\n"
        "  type B\n"
        "    extends A;\n"
        "  end B;\n"
        "end Test;\n"
    )
    tree = pymoca.parser.parse(src, bypass_cache=True)
    classes = _walk_type_classes(tree.classes["Test"])
    assert _resolve_unit("A", classes) is None
