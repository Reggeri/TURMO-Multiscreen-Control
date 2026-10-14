using System;
using System.Collections.Generic;
using System.Security.Principal;
using System.Text.Json;
using System.Threading;
using LibreHardwareMonitor.Hardware;

class Program {
  static readonly JsonSerializerOptions JsonOptions = new() { PropertyNamingPolicy = JsonNamingPolicy.CamelCase };
  static void Main() {
    Console.OutputEncoding = System.Text.Encoding.UTF8;
    try {
      bool isAdmin = false;
      try {
        using var identity = WindowsIdentity.GetCurrent();
        isAdmin = new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
      } catch {}
      Console.Error.WriteLine("SensorBridge administrator: " + isAdmin);
      var computer = new Computer { IsCpuEnabled = true, IsGpuEnabled = true, IsMemoryEnabled = true, IsStorageEnabled = true, IsMotherboardEnabled = true };
      computer.Open();
      try {
      while (true) {
        try {
          var sensors = new List<object>();
          foreach (var hardware in computer.Hardware) {
            try { Collect(hardware, sensors); }
            catch (Exception ex) { Console.Error.WriteLine($"Sensor hardware warning ({hardware.Name}): {ex.Message}"); }
          }
          Console.WriteLine(JsonSerializer.Serialize(new { sensors }, JsonOptions));
        } catch (Exception ex) {
          Console.WriteLine(JsonSerializer.Serialize(new { error = ex.Message }));
        }
        Console.Out.Flush();
        Thread.Sleep(2000);
      }
      } finally { computer.Close(); }
    } catch (Exception ex) {
      Console.WriteLine(JsonSerializer.Serialize(new { error = "Initialization: " + ex.Message }));
      Console.Out.Flush();
    }
  }
  static void Collect(IHardware hw, List<object> sensors) {
    hw.Update();
    foreach (var sensor in hw.Sensors) {
      if (!sensor.Value.HasValue || float.IsNaN(sensor.Value.Value) || float.IsInfinity(sensor.Value.Value)) continue;
      sensors.Add(new {
        name = sensor.Name, identifier = sensor.Identifier.ToString(),
        type = sensor.SensorType.ToString(), value = sensor.Value.Value,
        hardwareName = hw.Name, hardwareType = hw.HardwareType.ToString()
      });
    }
    foreach (var child in hw.SubHardware) Collect(child, sensors);
  }
}
