import 'dart:async';

import 'package:flutter/material.dart';
import 'package:latlong2/latlong.dart';

import '../../api.dart';
import '../../location.dart';
import '../../models.dart';
import '../../session.dart';
import '../../widgets/common.dart';
import 'disposal_screen.dart';
import 'job_screen.dart';

/// Collector home: go online, see the load meter, answer job offers, open jobs.
class CollectorHome extends StatefulWidget {
  const CollectorHome({super.key});

  @override
  State<CollectorHome> createState() => _CollectorHomeState();
}

class _CollectorHomeState extends State<CollectorHome> {
  bool _verified = true;
  bool _online = false;
  bool _busy = false;
  LoadInfo? _load;
  List<Pickup> _offers = [];
  List<Pickup> _jobs = [];
  LatLng? _here;
  Timer? _poll;
  Timer? _gps;
  Timer? _clock;
  EventSocket? _socket;

  @override
  void initState() {
    super.initState();
    _refresh();
    _poll = Timer.periodic(const Duration(seconds: 4), (_) => _refresh());
    _clock = Timer.periodic(const Duration(seconds: 1), (_) {
      if (_offers.isNotEmpty && mounted) setState(() {}); // offer countdown
    });
    _socket = session.api.events()..stream.listen((_) => _refresh());
  }

  @override
  void dispose() {
    _poll?.cancel();
    _gps?.cancel();
    _clock?.cancel();
    _socket?.close();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final me = Map<String, dynamic>.from(await session.api.get('/auth/me') as Map);
      final c = Map<String, dynamic>.from(me['collector'] as Map);
      final results = await Future.wait([
        session.api.get('/collector/load'),
        session.api.get('/collector/offers'),
        session.api.get('/collector/jobs'),
      ]);
      if (!mounted) return;
      setState(() {
        _verified = c['verified'] as bool;
        _online = c['is_online'] as bool;
        _load = LoadInfo.fromJson(Map<String, dynamic>.from(results[0] as Map));
        _offers = _pickups(results[1]);
        _jobs = _pickups(results[2]);
      });
      if (_online && _gps == null) _startGps();
    } on ApiException catch (e) {
      if (e.status == 401) session.logout();
    } catch (_) {}
  }

  List<Pickup> _pickups(dynamic list) =>
      (list as List).map((e) => Pickup.fromJson(Map<String, dynamic>.from(e as Map))).toList();

  /// Sends the phone's position every 10 seconds while online, so users can track the tricycle.
  void _startGps() {
    _gps?.cancel();
    _gps = Timer.periodic(const Duration(seconds: 10), (_) async {
      final here = await currentLocation();
      if (here == null) return;
      _here = here;
      try {
        await session.api.post('/collector/location', {'lat': here.latitude, 'lng': here.longitude});
      } catch (_) {}
    });
  }

  Future<void> _setOnline(bool online) async {
    setState(() => _busy = true);
    try {
      if (online) {
        final here = await currentLocation();
        if (here == null) {
          throw ApiException('Turn on location and allow TriCycle Waste to use it, then try again.');
        }
        _here = here;
        await session.api.post('/collector/online', {'lat': here.latitude, 'lng': here.longitude});
        _startGps();
      } else {
        await session.api.post('/collector/offline');
        _gps?.cancel();
        _gps = null;
      }
      await _refresh();
    } catch (e) {
      if (mounted) showMessage(context, e, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _answer(Pickup offer, bool accept) async {
    try {
      await session.api.post('/collector/jobs/${offer.id}/${accept ? 'accept' : 'decline'}');
      if (mounted) showMessage(context, accept ? 'Job accepted. Head to the pickup.' : 'Job declined');
      await _refresh();
      if (accept && mounted) _openJob(offer.id);
    } catch (e) {
      if (mounted) showMessage(context, e, error: true);
      _refresh();
    }
  }

  Future<void> _openJob(int id) async {
    final job = _jobs.where((j) => j.id == id).firstOrNull ??
        Pickup.fromJson(Map<String, dynamic>.from(await session.api.get('/pickups/$id') as Map));
    if (!mounted) return;
    await Navigator.push(context, MaterialPageRoute(builder: (_) => JobScreen(job: job, here: _here)));
    _refresh();
  }

  Future<void> _openDisposal() async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) => const DisposalScreen()));
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final load = _load;
    return Scaffold(
      appBar: AppBar(
        title: const Text('TriCycle Waste · Collector'),
        actions: [IconButton(onPressed: session.logout, icon: const Icon(Icons.logout), tooltip: 'Sign out')],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          if (!_verified)
            const Card(
              color: Color(0xFFFBECC8),
              child: Padding(
                padding: EdgeInsets.all(14),
                child: Text('Your account is waiting for verification. An administrator will check your '
                    'Ghana Card and measure your tricycle before you can take jobs.'),
              ),
            ),
          Card(
            child: SwitchListTile(
              value: _online,
              onChanged: !_verified || _busy ? null : _setOnline,
              title: Text(_online ? 'You are online' : 'You are offline',
                  style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18)),
              subtitle: Text(_online ? 'You will receive job offers that fit your tricycle' : 'Go online to receive jobs'),
              activeThumbColor: leaf,
            ),
          ),
          const SectionTitle('Your tricycle'),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: load == null
                  ? const LinearProgressIndicator()
                  : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      LoadMeter(load),
                      if (load.needsDisposal) ...[
                        const SizedBox(height: 12),
                        Text(
                          load.status == 'full'
                              ? 'Your tricycle is full. You will get no new jobs until you empty it at an approved site.'
                              : 'Nearly full. You will only get small jobs. Empty it soon.',
                          style: TextStyle(color: load.status == 'full' ? danger : Colors.brown.shade700,
                              fontWeight: FontWeight.w600),
                        ),
                      ],
                      if (load.loadUnits > 0) ...[
                        const SizedBox(height: 12),
                        FilledButton.icon(
                          onPressed: _openDisposal,
                          style: load.status == 'full' ? FilledButton.styleFrom(backgroundColor: danger) : null,
                          icon: const Icon(Icons.delete_sweep),
                          label: Text(load.nearestSite != null
                              ? 'Go to ${load.nearestSite!.name}'
                              : 'Empty at a disposal site'),
                        ),
                      ],
                    ]),
            ),
          ),
          if (_offers.isNotEmpty) ...[
            const SectionTitle('New job offer'),
            for (final o in _offers) _OfferCard(o, onAnswer: (accept) => _answer(o, accept)),
          ],
          const SectionTitle('Your jobs'),
          if (_jobs.isEmpty)
            Text(_online ? 'No jobs yet. New offers appear here.' : 'Go online to get jobs.',
                style: TextStyle(color: Colors.grey.shade700)),
          for (final j in _jobs)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Card(
                child: ListTile(
                  onTap: () => _openJob(j.id),
                  title: Text('${j.rubbersText} · ${j.confirmedUnits ?? j.declaredUnits} units',
                      style: const TextStyle(fontWeight: FontWeight.w700)),
                  subtitle: Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Row(children: [StatusChip(j.status), const SizedBox(width: 8), Text(cedis(j.price))]),
                  ),
                  trailing: const Icon(Icons.chevron_right),
                ),
              ),
            ),
        ]),
      ),
    );
  }
}

class _OfferCard extends StatelessWidget {
  const _OfferCard(this.offer, {required this.onAnswer});
  final Pickup offer;
  final ValueChanged<bool> onAnswer;

  @override
  Widget build(BuildContext context) {
    final left = offer.offerExpiresAt?.difference(DateTime.now()).inSeconds ?? 0;
    return Card(
      color: const Color(0xFFE3EEDB),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(child: Text(cedis(offer.price), style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: forest))),
            Text(left > 0 ? '${left}s left' : 'Expiring…', style: const TextStyle(fontWeight: FontWeight.w700)),
          ]),
          Text('${offer.rubbersText} · ${offer.declaredUnits} load units · ${offer.wasteType}'),
          if (offer.address != null) Text(offer.address!, style: TextStyle(color: Colors.grey.shade700)),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(child: OutlinedButton(onPressed: () => onAnswer(false), child: const Text('Decline'))),
            const SizedBox(width: 12),
            Expanded(child: FilledButton(onPressed: () => onAnswer(true), child: const Text('Accept'))),
          ]),
        ]),
      ),
    );
  }
}
