Subset of Modelica Standard Library (https://github.com/modelica/ModelicaStandardLibrary, 4.0.0) that is
 * required in rtc-tools
 * parsable by pymoca>=0.10.0 (which no longer declares Modelica as a builtin type, see https://github.com/pymoca/pymoca/commit/cf6d6a3b259983afe6e9d43c079da33901f17e34 )

`Modelica/Icons.mo` is vendored alongside `Modelica/Units.mo` because `Units.mo`
extends several `Modelica.Icons.*` classes that pymoca no longer resolves on
its own.
