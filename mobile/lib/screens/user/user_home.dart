import 'dart:async';

import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../api.dart';
import '../../models.dart';
import '../../session.dart';
import '../../widgets/common.dart';
import 'book_pickup.dart';
import 'pickup_detail.dart';
import 'report_dumping.dart';

class UserHome extends StatefulWidget {
  const UserHome({super.key});

  @override
  State<UserHome> createState() => _UserHomeState();
}

class _UserHomeState extends State<UserHome> {
  List<Pickup> _pickups = [];
  int _points = 0;
  bool _loading = true;
  Timer? _timer;
  EventSocket? _socket;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 6), (_) => _refresh());
    _socket = session.api.events()..stream.listen((_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _socket?.close();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final results = await Future.wait([session.api.get('/pickups'), session.api.get('/auth/me')]);
      if (!mounted) return;
      setState(() {
        _pickups = (results[0] as List).map((e) => Pickup.fromJson(Map<String, dynamic>.from(e as Map))).toList();
        _points = (results[1] as Map)['reward_points'] as int;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (e.status == 401) session.logout();
    } catch (_) {}
  }

  Future<void> _open(Widget screen) async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) => screen));
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final active = _pickups.where((p) => p.isActive).toList();
    final past = _pickups.where((p) => !p.isActive).toList();
    return Scaffold(
      appBar: AppBar(
        title: const Text('TriCycle Waste'),
        actions: [IconButton(onPressed: session.logout, icon: const Icon(Icons.logout), tooltip: 'Sign out')],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          Text('Hello, ${session.name?.split(' ').first ?? ''}',
              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: forest)),
          const SizedBox(height: 4),
          Row(children: [
            const Icon(Icons.stars, color: amber, size: 20),
            const SizedBox(width: 4),
            Text('$_points reward points from recycling'),
          ]),
          const SizedBox(height: 16),
          if (_loading) const LinearProgressIndicator(),
          if (active.isNotEmpty) ...[
            const SectionTitle('Your pickup'),
            for (final p in active) _PickupCard(p, onTap: () => _open(PickupDetailScreen(pickupId: p.id))),
          ] else
            FilledButton.icon(
              onPressed: () => _open(const BookPickupScreen()),
              icon: const Icon(Icons.add_circle_outline),
              label: const Text('Book a pickup'),
            ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: () => _open(const ReportDumpingScreen()),
            icon: const Icon(Icons.report_outlined),
            label: const Text('Report illegal dumping'),
          ),
          if (past.isNotEmpty) ...[
            const SectionTitle('Past pickups'),
            for (final p in past) _PickupCard(p, onTap: () => _open(PickupDetailScreen(pickupId: p.id))),
          ],
        ]),
      ),
    );
  }
}

class _PickupCard extends StatelessWidget {
  const _PickupCard(this.p, {required this.onTap});
  final Pickup p;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Card(
          child: ListTile(
            onTap: onTap,
            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            title: Row(children: [
              Expanded(child: Text(cedis(p.price), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18))),
              StatusChip(p.status),
            ]),
            subtitle: Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('${p.rubbersText} · ${p.confirmedUnits ?? p.declaredUnits} units · '
                  '${DateFormat('d MMM, HH:mm').format(p.createdAt)}'),
            ),
            trailing: const Icon(Icons.chevron_right),
          ),
        ),
      );
}
