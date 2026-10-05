import 'package:http/http.dart' as http;

import 'auth_service.dart';

/// Session transport for non-billing API requests. Redirects never carry tokens.
class FeatureHttpClient extends http.BaseClient {
  FeatureHttpClient({
    required this.baseUri,
    required this.auth,
    required TokenPair tokens,
    http.Client? client,
    this.onSessionExpired,
  }) : _tokens = tokens,
       _epoch = auth.generation,
       _client = client ?? http.Client();

  final Uri baseUri;
  final AuthRepository auth;
  final void Function()? onSessionExpired;
  final http.Client _client;
  final int _epoch;
  TokenPair _tokens;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final uri = request.url;
    final prefix = baseUri.path.endsWith('/')
        ? baseUri.path
        : '${baseUri.path}/';
    if (uri.origin != baseUri.origin ||
        !uri.path.startsWith(prefix) ||
        uri.userInfo.isNotEmpty) {
      throw http.ClientException('Request is outside the configured API.', uri);
    }
    final bytes = await request.finalize().toBytes();
    Future<http.StreamedResponse> attempt(String token) {
      if (auth.generation != _epoch)
        throw const AuthException('Session ended.');
      final copy = http.Request(request.method, uri)
        ..headers.addAll(request.headers)
        ..headers['Authorization'] = 'Bearer $token'
        ..followRedirects = false
        ..bodyBytes = bytes;
      return _client.send(copy);
    }

    final sent = _tokens.access;
    final response = await attempt(sent);
    if (response.statusCode != 401 || _tokens.refresh.isEmpty) return response;
    await response.stream.drain<void>();
    if (auth.generation != _epoch) throw const AuthException('Session ended.');
    if (_tokens.access == sent) {
      try {
        _tokens = await auth.refresh(_tokens.refresh);
      } on AuthException catch (error) {
        if (error.status == 401 || error.status == 403)
          onSessionExpired?.call();
        rethrow;
      }
    }
    return attempt(_tokens.access);
  }

  @override
  void close() => _client.close();
}
