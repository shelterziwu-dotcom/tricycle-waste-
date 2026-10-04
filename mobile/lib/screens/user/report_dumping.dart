import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../location.dart';
import '../../session.dart';
import '../../widgets/common.dart';

class ReportDumpingScreen extends StatefulWidget {
  const ReportDumpingScreen({super.key});

  @override
  State<ReportDumpingScreen> createState() => _ReportDumpingScreenState();
}

class _ReportDumpingScreenState extends State<ReportDumpingScreen> {
  final _map = MapController();
  final _description = TextEditingController();
  LatLng _point = accraCentre;
  String? _photoUrl;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    currentLocation().then((here) {
      if (here != null && mounted) {
        setState(() => _point = here);
        moveMapSafely(_map, here, 17);
      }
    });
  }

  Future<void> _send() async {
    setState(() => _busy = true);
    try {
      await session.api.post('/dumping-reports', {
        'lat': _point.latitude,
        'lng': _point.longitude,
        'photo_url': _photoUrl,
        'description': _description.text.trim().isEmpty ? null : _description.text.trim(),
      });
      if (mounted) {
        showMessage(context, 'Report sent. Thank you for keeping the city clean.');
        Navigator.pop(context);
      }
    } catch (e) {
      if (mounted) showMessage(context, e, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Report illegal dumping')),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: SizedBox(
              height: 220,
              child: FlutterMap(
                mapController: _map,
                options: MapOptions(initialCenter: _point, initialZoom: 15, onTap: (_, p) => setState(() => _point = p)),
                children: [osmTiles(), MarkerLayer(markers: [pin(_point, color: const Color(0xFF8E44AD), icon: Icons.report)])],
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text('Tap the map if the dump site is somewhere else.', style: TextStyle(color: Colors.grey.shade700)),
          const SizedBox(height: 16),
          PhotoField(label: 'Photo of the dumping (required)', onUploaded: (url) => setState(() => _photoUrl = url)),
          const SizedBox(height: 12),
          TextField(controller: _description, maxLines: 3,
              decoration: const InputDecoration(labelText: 'What did you see? (optional)')),
          const SizedBox(height: 20),
          FilledButton(onPressed: _busy || _photoUrl == null ? null : _send,
              child: Text(_photoUrl == null ? 'Add a photo first' : 'Send report')),
        ]),
      );
}
