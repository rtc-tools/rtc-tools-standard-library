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
That type is not vendored here. Constructing any `Complex` value (e.g.
`Complex(1.0, 2.0)`) raises `pymoca.ast.ClassNotFoundError: Could not find
class 'Complex'`.

Function calls into `Modelica.Units.Conversions.*` behave differently
depending on call form, observed with pymoca 0.11.2 (casadi 3.7.2 and
3.8.1): equation-form calls (e.g. `equation x =
Modelica.Units.Conversions.to_deg(1.0);`) resolve successfully.
Declaration-binding-form calls raise `Unknown function <first segment>` —
`Modelica.Units.Conversions.to_deg(1.0)` gives `Unknown function Modelica`,
an unqualified local function call gives `Unknown function <that name>`.
Separately, `casadi>=3.8.0` breaks any division operation under pymoca
0.11.2 (`AttributeError: 'MX' object has no attribute '__div__'`), which is
why CI pins `casadi<3.8.0`.

## Included files

| File | MSL version | Namespace |
|---|---|---|
| `Modelica/Units.mo` | 4.0.0 | `Modelica.Units.*` |
| `Modelica/SIunits.mo` | 3.2.3 | `Modelica.SIunits.*`, verbatim from the `maint/3.2.3` branch of `modelica/ModelicaStandardLibrary` (deprecated, kept for backwards-compatibility with models that have not yet migrated) |
| `Modelica/Icons.mo` | 4.0.0 | `Modelica.Icons.*` (vendored dependency of `Units.mo` and `SIunits.mo`) |
| `Modelica/Constants.mo` | — | `Modelica.Constants.*` (minimal subset: `pi`, `T_zero` only; see above) |
