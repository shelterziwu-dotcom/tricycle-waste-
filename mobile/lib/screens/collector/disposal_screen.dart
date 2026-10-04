import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../location.dart';
import '../../models.dart';
import '../../session.dart';
import '../../widgets/common.dart';

/// Empty the tricycle: check in from inside an approved disposal site with a photo.
class DisposalScreen extends StatefulWidget {
  const DisposalScreen({super.key});

  @override
  State<DisposalScreen> createState() => _DisposalScreenState();
}

class _DisposalScreenState extends State<DisposalScreen> {
  final _map = MapController();
  List<DisposalSite> _sites = [];
  DisposalSite? _selected;
  LatLng? _here;
  String? _photoUrl;
  bool _busy = false;
  bool _locating = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final here = await currentLocation();
    final query = here == null ? '' : '?lat=${here.latitude}&lng=${here.longitude}';
    try {
      final list = await session.api.get('/disposal-sites$query') as List;
      if (!mounted) return;
      setState(() {
        _here = here;
        _locating = false;
        _sites = list.map((e) => DisposalSite.fromJson(Map<String, dynamic>.from(e as Map))).toList();
        _selected = _sites.isEmpty ? null : _sites.first;
      });
      if (_selected != null) moveMapSafely(_map, LatLng(_selected!.lat, _selected!.lng), 14);
    } catch (e) {
      if (mounted) showMessage(context, e, error: true);
    }
  }

  String _distanceTo(DisposalSite s) {
    if (_here == null) return '';
    final m = metresBetween(_here!, LatLng(s.lat, s.lng));
    return m < 1000 ? '${m.round()} m away' : '${(m / 1000).toStringAsFixed(1)} km away';
  }

  Future<void> _checkIn() async {
    final site = _selected;
    if (site == null) return;
    setState(() => _busy = true);
    try {
      final here = await currentLocation();
      if (here == null) throw Exception('Turn on location so we can confirm you are at the site.');
      _here = here;
      final r = Map<String, dynamic>.from(await session.api.post('/collector/disposal-checkin', {
        'site_id': site.id,
        'lat': here.latitude,
        'lng': here.longitude,
        'photo_url': _photoUrl,
      }) as Map);
      if (!mounted) return;
      final verified = r['verified'] as bool;
      await showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          icon: Icon(verified ? Icons.verified : Icons.location_off, color: verified ? leaf : danger, size: 48),
          title: Text(verified ? 'Disposal verified' : 'Not at the site yet'),
          content: Text(verified
              ? '${r['units_disposed']} units emptied at ${site.name}. Your tricycle is empty and '
                  'earnings for ${r['jobs_released']} job(s) are released.'
              : r['message'] as String),
          actions: [TextButton(onPressed: () => Navigator.pop(context), child: const Text('OK'))],
        ),
      );
      if (verified && mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) showMessage(context, e.toString().replaceFirst('Exception: ', ''), error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Empty your tricycle')),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          const Text('Go to an approved site. Your load is only reset, and your earnings released, '
              'when you check in from inside the site.'),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: SizedBox(
              height: 240,
              child: FlutterMap(
                mapController: _map,
                options: const MapOptions(initialCenter: accraCentre, initialZoom: 12),
                children: [
                  osmTiles(),
                  CircleLayer(circles: [
                    for (final s in _sites)
                      CircleMarker(
                        point: LatLng(s.lat, s.lng),
                        radius: s.radiusM,
                        useRadiusInMeter: true,
                        color: (s == _selected ? leaf : forest).withValues(alpha: 0.2),
                        borderColor: s == _selected ? leaf : forest,
                        borderStrokeWidth: 2,
                      ),
                  ]),
                  MarkerLayer(markers: [
                    if (_here != null) pin(_here!, color: forest, icon: Icons.pedal_bike, label: 'You'),
                  ]),
                ],
              ),
            ),
          ),
          const SectionTitle('Approved sites'),
          if (_locating) const LinearProgressIndicator(),
          RadioGroup<int>(
            groupValue: _selected?.id,
            onChanged: (id) {
              final s = _sites.firstWhere((x) => x.id == id);
              setState(() => _selected = s);
              moveMapSafely(_map, LatLng(s.lat, s.lng), 15);
            },
            child: Column(children: [
              for (final s in _sites)
                Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: RadioListTile<int>(
                    value: s.id,
                    title: Text(s.name, style: const TextStyle(fontWeight: FontWeight.w700)),
                    subtitle: Text([_distanceTo(s), 'check-in radius ${s.radiusM.round()} m']
                        .where((t) => t.isNotEmpty)
                        .join(' · ')),
                  ),
                ),
            ]),
          ),
          const SizedBox(height: 8),
          PhotoField(label: 'Photo of the drop-off (required)', onUploaded: (url) => setState(() => _photoUrl = url)),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _busy || _photoUrl == null || _selected == null ? null : _checkIn,
            icon: const Icon(Icons.where_to_vote),
            label: Text(_busy ? 'Checking your location…' : 'Check in at this site'),
          ),
        ]),
      );
}
