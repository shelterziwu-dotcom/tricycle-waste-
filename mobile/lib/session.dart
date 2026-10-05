import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';

/// Who is logged in and which server the app talks to. Saved on the phone.
class Session extends ChangeNotifier {
  // Android emulator reaches the computer at 10.0.2.2. A real phone needs the
  // computer's Wi-Fi address, e.g. http://192.168.1.20:8000 (shown by start.bat).
  static const defaultServer = kIsWeb ? 'http://localhost:8000' : 'http://10.0.2.2:8000';

  bool loaded = false;
  bool serverConfirmed = false;
  String serverUrl = defaultServer;
  String? token;
  String? role;
  String? name;

  late final Api api = Api(serverUrl);

  bool get loggedIn => token != null;

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    serverUrl = p.getString('server_url') ?? defaultServer;
    serverConfirmed = p.getBool('server_confirmed') ?? false;
    // The browser version served by the backend at /app talks to that same server.
    if (kIsWeb && Uri.base.path.startsWith('/app')) {
      serverUrl = Uri.base.origin;
      serverConfirmed = true;
    }
    token = p.getString('token');
    role = p.getString('role');
    name = p.getString('name');
    api
      ..baseUrl = serverUrl
      ..token = token;
    loaded = true;
    notifyListeners();
  }

  Future<void> setServer(String url) async {
    serverUrl = url.trim().replaceAll(RegExp(r'/+$'), '');
    serverConfirmed = true;
    api.baseUrl = serverUrl;
    final p = await SharedPreferences.getInstance();
    await p.setString('server_url', serverUrl);
    await p.setBool('server_confirmed', true);
    notifyListeners();
  }

  void editServer() {
    serverConfirmed = false;
    notifyListeners();
  }

  Future<void> signedIn(Map<String, dynamic> tokenResponse) async {
    token = tokenResponse['token'] as String;
    role = tokenResponse['role'] as String;
    name = tokenResponse['name'] as String;
    api.token = token;
    final p = await SharedPreferences.getInstance();
    await p.setString('token', token!);
    await p.setString('role', role!);
    await p.setString('name', name!);
    notifyListeners();
  }

  Future<void> logout() async {
    token = role = name = null;
    api.token = null;
    final p = await SharedPreferences.getInstance();
    await p.remove('token');
    await p.remove('role');
    await p.remove('name');
    notifyListeners();
  }
}

/// One session for the whole app.
final session = Session();
