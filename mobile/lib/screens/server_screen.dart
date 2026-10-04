import 'package:flutter/material.dart';

import '../api.dart';
import '../session.dart';
import '../widgets/common.dart';

/// First-run screen: where is the backend running?
class ServerScreen extends StatefulWidget {
  const ServerScreen({super.key});

  @override
  State<ServerScreen> createState() => _ServerScreenState();
}

class _ServerScreenState extends State<ServerScreen> {
  late final _url = TextEditingController(text: session.serverUrl);
  bool _busy = false;

  Future<void> _connect() async {
    setState(() => _busy = true);
    try {
      await Api(_url.text.trim()).get('/health');
      await session.setServer(_url.text);
    } catch (e) {
      if (mounted) showMessage(context, e, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: ListView(padding: const EdgeInsets.all(24), children: [
            const SizedBox(height: 24),
            const Icon(Icons.recycling, size: 64, color: forest),
            const SizedBox(height: 12),
            const Text('TriCycle Waste', textAlign: TextAlign.center,
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: forest)),
            const SizedBox(height: 24),
            const Text('Server address', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            TextField(controller: _url, keyboardType: TextInputType.url, autocorrect: false,
                decoration: const InputDecoration(hintText: 'http://192.168.1.20:8000')),
            const SizedBox(height: 8),
            Text(
              '• Android emulator on the same computer: http://10.0.2.2:8000\n'
              '• Real phone: connect to the same Wi-Fi as the computer and use the computer\'s address, '
              'e.g. http://192.168.1.20:8000 (run ipconfig on the computer to find it)',
              style: TextStyle(color: Colors.grey.shade700, height: 1.5),
            ),
            const SizedBox(height: 24),
            FilledButton(onPressed: _busy ? null : _connect, child: Text(_busy ? 'Connecting…' : 'Connect')),
          ]),
        ),
      );
}
