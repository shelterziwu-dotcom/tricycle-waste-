import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../api.dart';
import '../../models.dart';
import '../../session.dart';
import '../../widgets/common.dart';

/// Follow one pickup: track the collector, approve a changed count, pay, rate.
class PickupDetailScreen extends StatefulWidget {
  const PickupDetailScreen({super.key, required this.pickupId});
  final int pickupId;

  @override
  State<PickupDetailScreen> createState() => _PickupDetailScreenState();
}

class _PickupDetailScreenState extends State<PickupDetailScreen> {
  Pickup? _p;
  LatLng? _collector;
  String? _collectorInfo;
  Timer? _timer;
  EventSocket? _socket;
  bool _busy = false;
  final _momo = TextEditingController();
  int _stars = 5;
  bool _rated = false;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 4), (_) => _refresh());
    _socket = session.api.events()
      ..stream.listen((e) {
        if (e['type'] == 'collector_location' && e['request_id'] == widget.pickupId) {
          setState(() => _collector = LatLng((e['lat'] as num).toDouble(), (e['lng'] as num).toDouble()));
        } else {
          _refresh();
        }
      });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _socket?.close();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final p = Pickup.fromJson(Map<String, dynamic>.from(await session.api.get('/pickups/${widget.pickupId}') as Map));
      LatLng? collector;
      String? info;
      if (p.status == 'accepted' || p.status == 'awaiting_approval') {
        final t = Map<String, dynamic>.from(await session.api.get('/pickups/${widget.pickupId}/track') as Map);
        if (t['lat'] != null) collector = LatLng((t['lat'] as num).toDouble(), (t['lng'] as num).toDouble());
        info = '${t['collector_name']} · ${t['plate_number']}'
            '${t['distance_km'] != null ? ' · ${t['distance_km']} km away' : ''}';
      }
      if (mounted) {
        setState(() {
          _p = p;
          _collector = collector ?? _collector;
          _collectorInfo = info;
        });
      }
    } catch (_) {}
  }

  Future<void> _act(String path, [Object? body, String? done]) async {
    setState(() => _busy = true);
    try {
      await session.api.post('/pickups/${widget.pickupId}/$path', body);
      if (mounted && done != null) showMessage(context, done);
      await _refresh();
    } on ApiException catch (e) {
      if (path == 'rate' && e.status == 409) {
        setState(() => _rated = true);
      } else if (mounted) {
        showMessage(context, e, error: true);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _p;
    return Scaffold(
      appBar: AppBar(title: Text('Pickup #${widget.pickupId}')),
      body: p == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(padding: const EdgeInsets.all(16), children: [
              Row(children: [
                Expanded(child: Text(cedis(p.price), style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800, color: forest))),
                StatusChip(p.status),
              ]),
              const SizedBox(height: 4),
              Text('${p.rubbersText} · ${p.confirmedUnits ?? p.declaredUnits} load units · ${p.wasteType}'),
              const SizedBox(height: 16),
              _Steps(p.status),
              const SizedBox(height: 16),
              if (_collectorInfo != null) ...[
                Text(_collectorInfo!, style: const TextStyle(fontWeight: FontWeight.w700)),
                const SizedBox(height: 8),
              ],
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: SizedBox(
                  height: 220,
                  child: FlutterMap(
                    // Rebuilt once the collector's position is known, so both markers fit.
                    key: ValueKey(_collector != null),
                    options: fitPoints([LatLng(p.lat, p.lng), ?_collector]),
                    children: [
                      osmTiles(),
                      MarkerLayer(markers: [
                        pin(LatLng(p.lat, p.lng), label: 'You'),
                        if (_collector != null) pin(_collector!, color: forest, icon: Icons.pedal_bike, label: 'Collector'),
                      ]),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              ..._actions(p),
            ]),
    );
  }

  List<Widget> _actions(Pickup p) {
    switch (p.status) {
      case 'searching':
      case 'offered':
      case 'accepted':
        return [
          if (p.status != 'accepted')
            const Text('We are offering your pickup to the nearest collector with space on their tricycle.'),
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: _busy ? null : () => _act('cancel', null, 'Pickup cancelled'),
            child: const Text('Cancel pickup'),
          ),
        ];
      case 'awaiting_approval':
        return [
          Card(
            color: const Color(0xFFFBECC8),
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('The collector counted different rubbers',
                    style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16)),
                const SizedBox(height: 6),
                Text('You declared ${p.declaredUnits} units (${cedis(p.quotedPrice)}). '
                    'The collector counted ${p.confirmedUnits} units: ${p.rubbersText}.'),
                const SizedBox(height: 6),
                Text('New price: ${cedis(p.proposedPrice ?? 0)}', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18)),
              ]),
            ),
          ),
          const SizedBox(height: 12),
          FilledButton(onPressed: _busy ? null : () => _act('approve', null, 'New price approved'),
              child: const Text('Approve new price')),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _busy ? null : () => _act('reject', null, 'Pickup cancelled'),
              child: const Text('Reject and cancel')),
        ];
      case 'collected':
        return [
          const Text('Your waste has been collected. Please pay the collector.',
              style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          TextField(controller: _momo, keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: 'Mobile money number')),
          const SizedBox(height: 10),
          FilledButton.icon(
            onPressed: _busy ? null : () => _act('pay', {'method': 'momo', 'phone': _momo.text.trim()}, 'Payment received'),
            icon: const Icon(Icons.phone_android),
            label: Text('Pay ${cedis(p.price)} by mobile money'),
          ),
          const SizedBox(height: 8),
          OutlinedButton(onPressed: _busy ? null : () => _act('pay', {'method': 'cash'}, 'Cash payment recorded'),
              child: const Text('I paid cash')),
          const SizedBox(height: 6),
          Text('Test mode: no real money is moved.', style: TextStyle(color: Colors.grey.shade700)),
        ];
      case 'paid':
        return [
          const Text('Thank you! How was the service?', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
          const SizedBox(height: 8),
          if (_rated)
            const Text('Thanks for your rating.', style: TextStyle(color: leaf, fontWeight: FontWeight.w700))
          else ...[
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              for (var i = 1; i <= 5; i++)
                IconButton(
                  onPressed: () => setState(() => _stars = i),
                  icon: Icon(i <= _stars ? Icons.star : Icons.star_border, color: amber, size: 36),
                  tooltip: '$i stars',
                ),
            ]),
            FilledButton(
              onPressed: _busy
                  ? null
                  : () async {
                      await _act('rate', {'stars': _stars}, 'Thanks for your rating');
                      if (mounted) setState(() => _rated = true);
                    },
              child: const Text('Submit rating'),
            ),
          ],
        ];
      default:
        return [];
    }
  }
}

class _Steps extends StatelessWidget {
  const _Steps(this.status);
  final String status;

  static const _steps = ['Booked', 'Collector on the way', 'Collected', 'Paid'];

  int get _current => switch (status) {
        'searching' || 'offered' => 0,
        'accepted' || 'awaiting_approval' => 1,
        'collected' => 2,
        'paid' => 3,
        _ => -1,
      };

  @override
  Widget build(BuildContext context) {
    if (_current < 0) return const SizedBox.shrink();
    return Row(children: [
      for (var i = 0; i < _steps.length; i++)
        Expanded(
          child: Column(children: [
            CircleAvatar(
              radius: 13,
              backgroundColor: i <= _current ? leaf : const Color(0xFFDDDBD2),
              child: Icon(i < _current ? Icons.check : Icons.circle, size: i < _current ? 16 : 8, color: Colors.white),
            ),
            const SizedBox(height: 4),
            Text(_steps[i], textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12, fontWeight: i == _current ? FontWeight.w800 : FontWeight.w400)),
          ]),
        ),
    ]);
  }
}
