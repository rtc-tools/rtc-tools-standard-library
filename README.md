Subset of Modelica Standard Library that is required in rtc-tools and parsable by pymoca>=0.11,<0.12
(the version tested in CI; pymoca no longer declares Modelica as a builtin
type as of https://github.com/pymoca/pymoca/commit/cf6d6a3b259983afe6e9d43c079da33901f17e34).

`Modelica/Icons.mo` is vendored alongside `Modelica/Units.mo` and
`Modelica/SIunits.mo` because both extend several `Modelica.Icons.*` classes
that pymoca no longer resolves on its own.

`Modelica/Constants.mo` is a minimal subset (only `pi` and `T_zero`, the two
constants referenced by `Units.mo`/`SIunits.mo`) of the upstream package, not
a verbatim vendor — the full upstream `Constants.mo` additionally depends on
`Modelica.Math` and `ModelicaServices`, which are out of scope for this
library.

`Units.mo` and `SIunits.mo` also declare Complex-typed records (e.g.
`ComplexCurrent`) that extend the standalone `Complex` operator record.
That type is not vendored here: with pymoca 0.11.2, constructing any
`Complex` value (even independent of this library) raises a
`RecursionError` in the casadi backend's flattening step, so vendoring it
would not make those types usable. Fully-qualified and locally-imported
function calls (e.g. `Modelica.Units.Conversions.to_deg(...)`) were also
observed to fail with the casadi backend independent of this library's
content. Both are pymoca/casadi-backend limitations, not gaps in the
vendored `.mo` files.

## Included files

| File | MSL version | Namespace |
|---|---|---|
| `Modelica/Units.mo` | 4.0.0 | `Modelica.Units.*` |
| `Modelica/SIunits.mo` | 3.2.3 | `Modelica.SIunits.*` (deprecated, kept for backwards-compatibility with models that have not yet migrated) |
| `Modelica/Icons.mo` | 4.0.0 | `Modelica.Icons.*` (vendored dependency of `Units.mo` and `SIunits.mo`) |
| `Modelica/Constants.mo` | — | `Modelica.Constants.*` (minimal subset: `pi`, `T_zero` only; see above) |
