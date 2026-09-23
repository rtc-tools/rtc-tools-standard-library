within Modelica;
package Constants
  "Minimal subset of Modelica.Constants: only the constants referenced by the vendored SIunits.mo and Units.mo (pi, T_zero). Not a verbatim vendor of the upstream package, which additionally depends on Modelica.Math and ModelicaServices."
  extends Modelica.Icons.Package;

  final constant Real pi=3.14159265358979323846;

  final constant Real T_zero=-273.15
    "Absolute zero temperature, in degC";

  annotation (Documentation(info="<html>
<p>
This package provides the subset of Modelica.Constants (MSL) actually used by
the vendored Modelica.SIunits and Modelica.Units.SI packages in this library:
the mathematical constant <strong>pi</strong> and the physical constant
<strong>T_zero</strong> (absolute zero, in degC).
</p>
<p>
Licensed by the Modelica Association under the 3-Clause BSD License.
</p>
</html>"));
end Constants;
