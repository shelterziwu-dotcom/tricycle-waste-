import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:image_picker/image_picker.dart';
import 'package:latlong2/latlong.dart';

import '../models.dart';
import '../session.dart';

// ---------- brand ----------
const forest = Color(0xFF1E3A2B);
const leaf = Color(0xFF5B9A3C);
const amber = Color(0xFFE0A526);
const danger = Color(0xFFC0392B);
const paper = Color(0xFFF0EFE9);

ThemeData appTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: forest, primary: forest, secondary: leaf, surface: Colors.white);
  return ThemeData(
    colorScheme: scheme,
    scaffoldBackgroundColor: paper,
    appBarTheme: const AppBarTheme(backgroundColor: forest, foregroundColor: Colors.white),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(50), textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(46))),
    cardTheme: const CardThemeData(color: Colors.white, elevation: 0.5, margin: EdgeInsets.zero),
    inputDecorationTheme: const InputDecorationTheme(border: OutlineInputBorder(), filled: true, fillColor: Colors.white),
  );
}

String cedis(num value) => 'GH₵ ${value.toStringAsFixed(2)}';

void showMessage(BuildContext context, Object message, {bool error = false}) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
    content: Text(message.toString()),
    backgroundColor: error ? danger : forest,
  ));
}

// ---------- pickup status ----------
const statusLabels = {
  'searching': 'Looking for a collector',
  'offered': 'Offered to a collector',
  'accepted': 'Collector on the way',
  'awaiting_approval': 'Check the new count',
  'collected': 'Collected – please pay',
  'paid': 'Completed',
  'cancelled': 'Cancelled',
};

Color statusColor(String status) => switch (status) {
      'searching' || 'offered' => const Color(0xFF2F6FB3),
      'accepted' => const Color(0xFF7A3FA0),
      'awaiting_approval' => amber,
      'collected' => leaf,
      'paid' => forest,
      _ => Colors.grey,
    };

class StatusChip extends StatelessWidget {
  const StatusChip(this.status, {super.key});
  final String status;

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(color: statusColor(status), borderRadius: BorderRadius.circular(20)),
        child: Text(statusLabels[status] ?? status,
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 12)),
      );
}

// ---------- tricycle load ----------
const loadLabels = {'empty': 'Empty', 'partly_loaded': 'Partly loaded', 'nearly_full': 'Nearly full', 'full': 'Full'};

Color loadColor(String status) => switch (status) {
      'partly_loaded' => leaf,
      'nearly_full' => amber,
      'full' => danger,
      _ => const Color(0xFF9FC48A),
    };

class LoadMeter extends StatelessWidget {
  const LoadMeter(this.load, {super.key});
  final LoadInfo load;

  @override
  Widget build(BuildContext context) {
    final color = loadColor(load.status);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Text(loadLabels[load.status] ?? load.status,
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800, color: load.status == 'full' ? danger : forest)),
        const Spacer(),
        Text('${load.loadUnits} / ${load.capacityUnits} units', style: const TextStyle(fontWeight: FontWeight.w600)),
      ]),
      const SizedBox(height: 8),
      ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: LinearProgressIndicator(
          value: (load.fillPercent / 100).clamp(0, 1).toDouble(),
          minHeight: 18,
          color: color,
          backgroundColor: const Color(0xFFE4E2DA),
        ),
      ),
      const SizedBox(height: 6),
      Text(
        '${load.fillPercent.toStringAsFixed(0)}% full · ${load.availableUnits} units free'
        '${load.reservedUnits > 0 ? ' · ${load.reservedUnits} reserved for accepted jobs' : ''}',
        style: TextStyle(color: Colors.grey.shade700),
      ),
    ]);
  }
}

// ---------- rubber counter ----------
class RubberStepper extends StatelessWidget {
  const RubberStepper({super.key, required this.size, required this.count, required this.onChanged});
  final RubberSize size;
  final int count;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${size.name} · ${size.loadUnits} unit${size.loadUnits == 1 ? '' : 's'}',
                  style: const TextStyle(fontWeight: FontWeight.w700)),
              Text(size.description, style: TextStyle(color: Colors.grey.shade700, fontSize: 13)),
            ]),
          ),
          IconButton.filledTonal(
            onPressed: count > 0 ? () => onChanged(count - 1) : null,
            icon: const Icon(Icons.remove),
            tooltip: 'Fewer ${size.name.toLowerCase()}',
          ),
          SizedBox(
            width: 36,
            child: Text('$count', textAlign: TextAlign.center, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
          ),
          IconButton.filled(
            onPressed: count < 20 ? () => onChanged(count + 1) : null,
            icon: const Icon(Icons.add),
            tooltip: 'More ${size.name.toLowerCase()}',
          ),
        ]),
      );
}

// ---------- photo ----------
/// Takes or picks a photo and uploads it. Calls [onUploaded] with the photo URL.
class PhotoField extends StatefulWidget {
  const PhotoField({super.key, required this.label, required this.onUploaded});
  final String label;
  final ValueChanged<String?> onUploaded;

  @override
  State<PhotoField> createState() => _PhotoFieldState();
}

class _PhotoFieldState extends State<PhotoField> {
  Uint8List? _bytes;
  bool _busy = false;

  Future<void> _pick(ImageSource source) async {
    try {
      final file = await ImagePicker().pickImage(source: source, maxWidth: 1280, imageQuality: 70);
      if (file == null) return;
      final bytes = await file.readAsBytes();
      setState(() {
        _busy = true;
        _bytes = bytes;
      });
      final url = await session.api.uploadPhoto(bytes, file.name.isEmpty ? 'photo.jpg' : file.name);
      widget.onUploaded(url);
    } catch (e) {
      widget.onUploaded(null);
      setState(() => _bytes = null);
      if (mounted) showMessage(context, e, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Container(
                width: 72,
                height: 72,
                color: const Color(0xFFE4E2DA),
                child: _bytes == null
                    ? const Icon(Icons.photo_camera_outlined, color: forest)
                    : Image.memory(_bytes!, fit: BoxFit.cover),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(widget.label, style: const TextStyle(fontWeight: FontWeight.w700)),
                if (_busy) const Padding(padding: EdgeInsets.only(top: 6), child: LinearProgressIndicator()),
                if (!_busy && _bytes != null)
                  const Text('Photo added ✓', style: TextStyle(color: leaf, fontWeight: FontWeight.w600)),
                Wrap(spacing: 4, children: [
                  TextButton.icon(onPressed: _busy ? null : () => _pick(ImageSource.camera),
                      icon: const Icon(Icons.photo_camera), label: const Text('Camera')),
                  TextButton.icon(onPressed: _busy ? null : () => _pick(ImageSource.gallery),
                      icon: const Icon(Icons.photo_library), label: const Text('Gallery')),
                ]),
              ]),
            ),
          ]),
        ),
      );
}

// ---------- map ----------
TileLayer osmTiles() => TileLayer(
      urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
      userAgentPackageName: 'gh.edu.rmu.tricycle_waste',
    );

Marker pin(LatLng point, {Color color = danger, IconData icon = Icons.location_on, String? label}) => Marker(
      point: point,
      width: label == null ? 44 : 120,
      height: label == null ? 44 : 64,
      alignment: Alignment.topCenter,
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        if (label != null)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(10)),
            child: Text(label, style: const TextStyle(color: Colors.white, fontSize: 11, fontWeight: FontWeight.w700),
                overflow: TextOverflow.ellipsis),
          ),
        Icon(icon, color: color, size: 36),
      ]),
    );

/// Map options that show all [points] (e.g. the house and the collector).
MapOptions fitPoints(List<LatLng> points, {double zoom = 15}) => points.length < 2
    ? MapOptions(initialCenter: points.first, initialZoom: zoom)
    : MapOptions(
        initialCameraFit: CameraFit.coordinates(coordinates: points, padding: const EdgeInsets.fromLTRB(40, 70, 40, 30)),
      );

/// Moves a map, ignoring the error thrown if the map has not been drawn yet.
void moveMapSafely(MapController map, LatLng point, double zoom) {
  try {
    map.move(point, zoom);
  } catch (_) {}
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key});
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 20, bottom: 8),
        child: Text(text, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: forest)),
      );
}
