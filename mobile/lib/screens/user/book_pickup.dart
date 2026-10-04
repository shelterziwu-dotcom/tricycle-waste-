import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../location.dart';
import '../../models.dart';
import '../../session.dart';
import '../../widgets/common.dart';
import 'pickup_detail.dart';

const wasteTypes = {
  'general': 'General',
  'organic': 'Organic / food',
  'recyclable': 'Recyclables (cheaper)',
  'bulky': 'Bulky items',
};

/// Book a pickup: where, what type of waste, how many rubbers of each size.
class BookPickupScreen extends StatefulWidget {
  const BookPickupScreen({super.key});

  @override
  State<BookPickupScreen> createState() => _BookPickupScreenState();
}

class _BookPickupScreenState extends State<BookPickupScreen> {
  final _map = MapController();
  final _address = TextEditingController();
  List<RubberSize> _sizes = [];
  final Map<String, int> _counts = {};
  String _wasteType = 'general';
  LatLng _point = accraCentre;
  bool _gotLocation = false;
  Quote? _quote;
  String? _quoteError;
  Timer? _debounce;
  bool _busy = false;

  int get _totalRubbers => _counts.values.fold(0, (a, b) => a + b);

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final sizes = await session.api.get('/rubber-sizes') as List;
      setState(() {
        _sizes = sizes.map((e) => RubberSize.fromJson(Map<String, dynamic>.from(e as Map))).toList();
        for (final s in _sizes) {
          _counts[s.code] = 0;
        }
      });
    } catch (e) {
      if (mounted) showMessage(context, e, error: true);
    }
    final here = await currentLocation();
    if (!mounted) return;
    if (here != null) {
      setState(() {
        _point = here;
        _gotLocation = true;
      });
      moveMapSafely(_map, here, 16);
    } else {
      showMessage(context, 'Could not get your location. Tap the map to place your pin.');
    }
  }

  void _changed() {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 350), _getQuote);
    setState(() {});
  }

  List<Map<String, Object>> get _items =>
      _counts.entries.where((e) => e.value > 0).map((e) => {'size_code': e.key, 'quantity': e.value}).toList();

  Map<String, Object?> get _body => {
        'lat': _point.latitude,
        'lng': _point.longitude,
        'waste_type': _wasteType,
        'items': _items,
        'address': _address.text.trim().isEmpty ? null : _address.text.trim(),
      };

  Future<void> _getQuote() async {
    if (_totalRubbers == 0) {
      setState(() => _quote = null);
      return;
    }
    try {
      final q = await session.api.post('/quote', _body);
      if (mounted) {
        setState(() {
          _quote = Quote.fromJson(Map<String, dynamic>.from(q as Map));
          _quoteError = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _quoteError = e.toString());
    }
  }

  Future<void> _book() async {
    setState(() => _busy = true);
    try {
      final r = await session.api.post('/pickups', _body);
      final id = (r as Map)['id'] as int;
      if (mounted) {
        Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => PickupDetailScreen(pickupId: id)));
      }
    } catch (e) {
      if (mounted) showMessage(context, e, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Book a pickup')),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          const Text('Pickup location', style: TextStyle(fontWeight: FontWeight.w800, color: forest, fontSize: 17)),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: SizedBox(
              height: 220,
              child: FlutterMap(
                mapController: _map,
                options: MapOptions(
                  initialCenter: _point,
                  initialZoom: 15,
                  onTap: (_, p) {
                    setState(() => _point = p);
                    _changed();
                  },
                ),
                children: [osmTiles(), MarkerLayer(markers: [pin(_point)])],
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(_gotLocation ? 'Your current location. Tap the map to move the pin.' : 'Tap the map to place your pin.',
              style: TextStyle(color: Colors.grey.shade700)),
          const SizedBox(height: 10),
          TextField(controller: _address, decoration: const InputDecoration(labelText: 'Landmark or directions (optional)')),
          const SectionTitle('Type of waste'),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final e in wasteTypes.entries)
              ChoiceChip(
                label: Text(e.value),
                selected: _wasteType == e.key,
                onSelected: (_) {
                  _wasteType = e.key;
                  _changed();
                },
              ),
          ]),
          const SectionTitle('How many rubbers?'),
          Card(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
              child: Column(children: [
                if (_sizes.isEmpty) const Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator()),
                for (final s in _sizes)
                  RubberStepper(
                    size: s,
                    count: _counts[s.code] ?? 0,
                    onChanged: (v) {
                      _counts[s.code] = v;
                      _changed();
                    },
                  ),
              ]),
            ),
          ),
          const SizedBox(height: 16),
          _PriceCard(quote: _quote, error: _quoteError, empty: _totalRubbers == 0),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _busy || _quote == null || _totalRubbers == 0 ? null : _book,
            child: Text(_quote == null ? 'Add your rubbers' : 'Book for ${cedis(_quote!.total)}'),
          ),
          const SizedBox(height: 24),
        ]),
      );
}

class _PriceCard extends StatelessWidget {
  const _PriceCard({required this.quote, required this.error, required this.empty});
  final Quote? quote;
  final String? error;
  final bool empty;

  @override
  Widget build(BuildContext context) {
    final q = quote;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: forest, borderRadius: BorderRadius.circular(14)),
      child: DefaultTextStyle(
        style: const TextStyle(color: Colors.white, height: 1.5),
        child: empty || q == null
            ? Text(error ?? 'Add rubbers to see the price.')
            : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('YOUR PRICE', style: TextStyle(letterSpacing: 1.2, fontSize: 12, color: Color(0xFF9FC48A))),
                Text(cedis(q.total), style: const TextStyle(fontSize: 34, fontWeight: FontWeight.w800)),
                Text('${q.totalUnits} load units'),
                Text('Base fee ${cedis(q.baseFee)} + rubbers ${cedis(q.unitsCharge)} + distance ${cedis(q.distanceCharge)}',
                    style: const TextStyle(fontSize: 13, color: Color(0xFFDCE6DE))),
                const SizedBox(height: 6),
                Text(
                  q.collectorsAvailable > 0
                      ? '${q.collectorsAvailable} collector${q.collectorsAvailable == 1 ? '' : 's'} with space nearby'
                          '${q.distanceKm != null ? ' · nearest ${q.distanceKm!.toStringAsFixed(1)} km' : ''}'
                      : 'No collector with space nearby right now. You can still book; we will match you when one is free.',
                  style: const TextStyle(fontSize: 13, color: Color(0xFFDCE6DE)),
                ),
              ]),
      ),
    );
  }
}
