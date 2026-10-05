import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'screens/collector/collector_home.dart';
import 'screens/login_screen.dart';
import 'screens/server_screen.dart';
import 'screens/user/user_home.dart';
import 'session.dart';
import 'widgets/common.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  session.load();
  runApp(const TriCycleApp());
}

class TriCycleApp extends StatelessWidget {
  const TriCycleApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'TriCycle Waste',
        theme: appTheme(),
        debugShowCheckedModeBanner: false,
        // In a laptop browser, show the app at phone width instead of stretching it.
        builder: (context, child) => kIsWeb
            ? ColoredBox(
                color: const Color(0xFF1E3A2B),
                child: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 460), child: child)),
              )
            : child!,
        home: ListenableBuilder(listenable: session, builder: (context, _) => _home()),
      );

  /// Chooses the first screen from what is saved on the phone.
  Widget _home() {
    if (!session.loaded) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    if (!session.serverConfirmed) return const ServerScreen();
    if (!session.loggedIn) return const LoginScreen();
    return switch (session.role) {
      'user' => const UserHome(),
      'collector' => const CollectorHome(),
      _ => const AdminNotice(),
    };
  }
}

class AdminNotice extends StatelessWidget {
  const AdminNotice({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('TriCycle Waste')),
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.dashboard_outlined, size: 64, color: forest),
            const SizedBox(height: 12),
            Text('Administrators use the web dashboard at ${session.serverUrl}/dashboard',
                textAlign: TextAlign.center, style: const TextStyle(fontSize: 16)),
            const SizedBox(height: 24),
            OutlinedButton(onPressed: session.logout, child: const Text('Sign out')),
          ]),
        ),
      );
}
