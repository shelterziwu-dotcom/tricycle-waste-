import 'package:flutter/material.dart';

import '../session.dart';
import '../widgets/common.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _phone = TextEditingController();
  final _password = TextEditingController();
  bool _busy = false;

  Future<void> _login() async {
    setState(() => _busy = true);
    try {
      final r = await session.api.post('/auth/login', {'phone': _phone.text.trim(), 'password': _password.text});
      await session.signedIn(Map<String, dynamic>.from(r as Map));
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
            const SizedBox(height: 8),
            const Text('TriCycle Waste', textAlign: TextAlign.center,
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: forest)),
            const Text('Waste pickup by tricycle, priced by your rubbers', textAlign: TextAlign.center),
            const SizedBox(height: 32),
            TextField(controller: _phone, keyboardType: TextInputType.phone,
                decoration: const InputDecoration(labelText: 'Phone number')),
            const SizedBox(height: 12),
            TextField(controller: _password, obscureText: true, onSubmitted: (_) => _login(),
                decoration: const InputDecoration(labelText: 'Password')),
            const SizedBox(height: 20),
            FilledButton(onPressed: _busy ? null : _login, child: Text(_busy ? 'Signing in…' : 'Sign in')),
            const SizedBox(height: 12),
            OutlinedButton(
              onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const RegisterScreen())),
              child: const Text('Create an account'),
            ),
            const SizedBox(height: 24),
            TextButton(onPressed: session.editServer, child: Text('Server: ${session.serverUrl} (change)')),
          ]),
        ),
      );
}

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  bool _collector = false;
  bool _busy = false;
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _password = TextEditingController();
  final _idNumber = TextEditingController();
  final _plate = TextEditingController();

  String? _problem() {
    if (_name.text.trim().length < 2) return 'Enter your full name';
    if (_phone.text.trim().length < 9) return 'Enter a valid phone number';
    if (_password.text.length < 6) return 'Password must have at least 6 characters';
    if (_collector && _idNumber.text.trim().length < 3) return 'Enter your Ghana Card number';
    if (_collector && _plate.text.trim().length < 3) return 'Enter your tricycle plate number';
    return null;
  }

  Future<void> _register() async {
    final problem = _problem();
    if (problem != null) {
      showMessage(context, problem, error: true);
      return;
    }
    setState(() => _busy = true);
    try {
      final body = {
        'name': _name.text.trim(),
        'phone': _phone.text.trim(),
        'password': _password.text,
        if (_collector) 'id_number': _idNumber.text.trim(),
        if (_collector) 'plate_number': _plate.text.trim(),
      };
      final r = await session.api.post(_collector ? '/auth/register-collector' : '/auth/register', body);
      await session.signedIn(Map<String, dynamic>.from(r as Map));
      if (mounted) Navigator.pop(context);
    } catch (e) {
      if (mounted) showMessage(context, e, error: true);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Create an account')),
        body: ListView(padding: const EdgeInsets.all(20), children: [
          SegmentedButton<bool>(
            segments: const [
              ButtonSegment(value: false, icon: Icon(Icons.home_outlined), label: Text('Household / shop')),
              ButtonSegment(value: true, icon: Icon(Icons.pedal_bike), label: Text('Tricycle collector')),
            ],
            selected: {_collector},
            onSelectionChanged: (s) => setState(() => _collector = s.first),
          ),
          const SizedBox(height: 20),
          TextField(controller: _name, decoration: const InputDecoration(labelText: 'Full name')),
          const SizedBox(height: 12),
          TextField(controller: _phone, keyboardType: TextInputType.phone,
              decoration: const InputDecoration(labelText: 'Phone number')),
          const SizedBox(height: 12),
          TextField(controller: _password, obscureText: true,
              decoration: const InputDecoration(labelText: 'Password (at least 6 characters)')),
          if (_collector) ...[
            const SizedBox(height: 12),
            TextField(controller: _idNumber, decoration: const InputDecoration(labelText: 'Ghana Card number')),
            const SizedBox(height: 12),
            TextField(controller: _plate, textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(labelText: 'Tricycle plate number')),
            const SizedBox(height: 8),
            Text('An administrator will verify your details and measure your tricycle before you can take jobs.',
                style: TextStyle(color: Colors.grey.shade700)),
          ],
          const SizedBox(height: 24),
          FilledButton(onPressed: _busy ? null : _register, child: Text(_busy ? 'Creating…' : 'Create account')),
        ]),
      );
}
