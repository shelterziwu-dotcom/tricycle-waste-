import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';

/// Used when the phone cannot give a location (e.g. permission refused).
const accraCentre = LatLng(5.5800, -0.2050);

const _distance = Distance();

/// Distance in metres between two points.
double metresBetween(LatLng a, LatLng b) => _distance.as(LengthUnit.Meter, a, b);

/// The phone's current position, or null if location is off or not allowed.
Future<LatLng?> currentLocation() async {
  try {
    if (!await Geolocator.isLocationServiceEnabled()) return null;
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever) {
      return null;
    }
    final pos = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(accuracy: LocationAccuracy.high, timeLimit: Duration(seconds: 15)),
    );
    return LatLng(pos.latitude, pos.longitude);
  } catch (_) {
    return null;
  }
}
