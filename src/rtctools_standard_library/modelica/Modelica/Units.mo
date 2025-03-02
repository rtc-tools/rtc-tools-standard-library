within Modelica.Units;

package SI "SI units"

  type VolumeFlowRate = Real(
    final quantity="VolumeFlowRate",
    final unit="m3/s");
    
  type MassFlowRate = Real (quantity="MassFlowRate", final unit="kg/s");
  type Position = Real (final quantity="Length", final unit="m");
  type Density = Real (
        final quantity="Density",
        final unit="kg/m3",
        displayUnit="g/cm3",
        min=0.0);
  type Stress = Real (final unit="Pa");
  type Distance = Real (final quantity="Length", final unit="m", min=0);
  type Duration = Real (final quantity="Time", final unit="s");
  type Angle = Real (
        final quantity="Angle",
        final unit="rad",
        displayUnit="deg");
  type Area = Real (final quantity="Area", final unit="m2");
end SI;
