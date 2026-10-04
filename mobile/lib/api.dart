import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

/// An error message from the server, ready to show to the user.
class ApiException implements Exception {
  ApiException(this.message, [this.status]);
  final String message;
  final int? status;

  @override
  String toString() => message;
}

/// Talks to the TriCycle Waste backend (the same API the admin dashboard uses).
class Api {
  Api(this.baseUrl, {this.token});

  String baseUrl;
  String? token;

  Uri _uri(String path) => Uri.parse('${baseUrl.replaceAll(RegExp(r'/+$'), '')}$path');

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Future<dynamic> get(String path) => _send(() => http.get(_uri(path), headers: _headers));

  Future<dynamic> post(String path, [Object? body]) => _send(
      () => http.post(_uri(path), headers: _headers, body: body == null ? null : jsonEncode(body)));

  Future<dynamic> _send(Future<http.Response> Function() request) async {
    final http.Response r;
    try {
      r = await request().timeout(const Duration(seconds: 15));
    } on TimeoutException {
      throw ApiException('The server did not answer. Check that start.bat is running.');
    } catch (_) {
      throw ApiException('Cannot reach the server at $baseUrl. Check the address and that the phone '
          'is on the same Wi-Fi as the computer.');
    }
    return _decode(r);
  }

  dynamic _decode(http.Response r) {
    dynamic body;
    if (r.bodyBytes.isNotEmpty) {
      try {
        body = jsonDecode(utf8.decode(r.bodyBytes));
      } catch (_) {
        body = null;
      }
    }
    if (r.statusCode >= 400) {
      final detail = body is Map ? body['detail'] : null;
      final message = detail is String
          ? detail
          : detail is List
              ? detail.map((e) => e is Map ? e['msg'] : e.toString()).join(', ')
              : 'Request failed (${r.statusCode})';
      throw ApiException(message, r.statusCode);
    }
    return body;
  }

  /// Uploads a photo and returns the URL to send as `photo_url`.
  Future<String> uploadPhoto(List<int> bytes, String filename) async {
    final name = filename.toLowerCase();
    final type = name.endsWith('.png')
        ? MediaType('image', 'png')
        : name.endsWith('.webp')
            ? MediaType('image', 'webp')
            : MediaType('image', 'jpeg');
    final request = http.MultipartRequest('POST', _uri('/uploads'))
      ..files.add(http.MultipartFile.fromBytes('file', bytes, filename: filename, contentType: type));
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    final http.Response r;
    try {
      r = await http.Response.fromStream(await request.send().timeout(const Duration(seconds: 60)));
    } catch (_) {
      throw ApiException('Photo upload failed. Check your connection and try again.');
    }
    return (_decode(r) as Map)['url'] as String;
  }

  /// Full URL for a path returned by the server (e.g. an uploaded photo).
  String absolute(String path) => path.startsWith('http') ? path : _uri(path).toString();

  /// Live events from the server: job offers, status changes, collector location.
  EventSocket events() {
    final wsBase = baseUrl.replaceFirst(RegExp(r'^http'), 'ws').replaceAll(RegExp(r'/+$'), '');
    return EventSocket(Uri.parse('$wsBase/ws?token=$token'));
  }
}

class EventSocket {
  EventSocket(Uri uri) {
    try {
      _channel = WebSocketChannel.connect(uri);
      // If live updates are unavailable the screens still refresh on a timer.
      _channel!.ready.then((_) {}, onError: (_) {});
      _ping = Timer.periodic(const Duration(seconds: 25), (_) => _channel?.sink.add('ping'));
    } catch (_) {
      _channel = null;
    }
  }

  WebSocketChannel? _channel;
  Timer? _ping;

  /// Each event is a map with a 'type' key, e.g. {'type': 'job_offer', 'request_id': 3}.
  Stream<Map<String, dynamic>> get stream {
    final channel = _channel;
    if (channel == null) return const Stream.empty();
    return channel.stream
        .map((data) {
          try {
            return Map<String, dynamic>.from(jsonDecode(data as String) as Map);
          } catch (_) {
            return <String, dynamic>{};
          }
        })
        .where((e) => e.isNotEmpty)
        .handleError((_) {});
  }

  void close() {
    _ping?.cancel();
    _channel?.sink.close();
  }
}
