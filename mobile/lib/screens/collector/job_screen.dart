import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../location.dart';
import '../../models.dart';
import '../../session.dart';
import '../../widgets/common.dart';

/// One accepted job: find the house, count the rubbers, take a photo, confirm.
class JobScreen extends StatefulWidget {
  const JobScreen({super.key, required this.job, this.here});
  final Pickup job;
  final LatLng? here;

  @override
  State<JobScreen> createState() => _JobScreenState();
}

class _JobScreenState extends State<JobScreen> {
  List<RubberSize> _sizes = [];
  final Map<String, int> _counts = {};
  String? _photoUrl;
  bool _busy = false;
  LatLng? _here;

  @override
  void initState() {
    super.initState();
    _here = widget.here;
    for (final i in widget.job.items) {
      _counts[i.sizeCode] = i.quantityDeclared;
    }
    session.api.get('/rubber-sizes').then((list) {
      if (!mounted) return;
      setState(() => _sizes =
          (list as List).map((e) => RubberSize.fromJson(Map<String, dynamic>.from(e as Map))).toList());
    });
    currentLocation().then((p) {
      if (p != null && mounted) setState(() => _here = p);
    });
  }

  int get _units => _sizes.fold(0, (sum, s) => sum + s.loadUnits * (_counts[s.code] ?? 0));

  Future<void> _collect() async {
    setState(() => _busy = true);
    try {
      final r = await session.api.post('/collector/jobs/${widget.job.id}/collect', {
        'items': _counts.entries.where((e) => e.value > 0).map((e) => {'size_code': e.key, 'quantity': e.value}).toList(),
        'photo_url': _photoUrl,
      });
      final status = (r as Map)['status'];
      if (!mounted) return;
      showMessage(context, status == 'collected'
          ? 'Collected. Load added to your tricycle.'
          : 'The count changed. Waiting for the customer to approve the new price.');
      Navigator.pop(context);
    } catch (e) {
      if (mounted) showMessage(context, e, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final job = widget.job;
    final home = LatLng(job.lat, job.lng);
    final canCollect = job.status == 'accepted';
    final distance = _here == null ? null : metresBetween(_here!, home);
    return Scaffold(
      appBar: AppBar(title: Text('Job #${job.id}')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Row(children: [
          Expanded(child: Text(cedis(job.price), style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: forest))),
          StatusChip(job.status),
        ]),
        Text('Customer declared: ${job.rubbersText} (${job.declaredUnits} units, ${job.wasteType})'),
        if (job.address != null) Text('Directions: ${job.address}', style: const TextStyle(fontWeight: FontWeight.w600)),
        if (distance != null)
          Text(distance < 1000 ? '${distance.round()} m away' : '${(distance / 1000).toStringAsFixed(1)} km away'),
        const SizedBox(height: 12),
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: SizedBox(
            height: 220,
            child: FlutterMap(
              key: ValueKey(_here != null),
              options: fitPoints([home, ?_here]),
              children: [
                osmTiles(),
                MarkerLayer(markers: [
                  pin(home, label: 'Pickup'),
                  if (_here != null) pin(_here!, color: forest, icon: Icons.pedal_bike, label: 'You'),
                ]),
              ],
            ),
          ),
        ),
        if (canCollect) ...[
          const SectionTitle('Count the rubbers you are taking'),
          Card(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              child: Column(children: [
                for (final s in _sizes)
                  RubberStepper(size: s, count: _counts[s.code] ?? 0, onChanged: (v) => setState(() => _counts[s.code] = v)),
              ]),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _units == job.declaredUnits
                ? '$_units units, same as declared.'
                : '$_units units, declared ${job.declaredUnits}. The customer will be asked to approve a new price.',
            style: TextStyle(fontWeight: FontWeight.w700, color: _units == job.declaredUnits ? forest : Colors.brown.shade700),
          ),
          const SizedBox(height: 12),
          PhotoField(label: 'Photo of the rubbers (required)', onUploaded: (url) => setState(() => _photoUrl = url)),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy || _photoUrl == null || _units == 0 ? null : _collect,
            child: Text(_photoUrl == null ? 'Take a photo first' : 'Confirm collection'),
          ),
        ] else if (job.status == 'awaiting_approval')
          const Padding(
            padding: EdgeInsets.only(top: 16),
            child: Text('Waiting for the customer to approve the new count and price.'),
          )
        else if (job.status == 'collected')
          const Padding(
            padding: EdgeInsets.only(top: 16),
            child: Text('Collected. Waiting for payment. Your earnings are released after you empty '
                'your tricycle at an approved disposal site.'),
          ),
      ]),
    );
  }
}
